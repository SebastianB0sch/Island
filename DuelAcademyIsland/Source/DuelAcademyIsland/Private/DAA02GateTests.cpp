// Duel Academy Island - A02 Gate 3 scale tests.
//
// Two deterministic, process-level suites share this file:
//
//   -DASaveFuzz[=N]      default N=10,000 random valid state save/load
//                        round-trips, plus corruption/recovery and
//                        version/migration fuzz.
//   -DASaveFuzzSeed=S    optional fuzz seed (default 0x5A02F022).
//   -DATwelveMonthTest   day-by-day 12-month calendar/profile simulation
//                        with save/load at month boundaries and random days.
//
// Both mirror the runtime context pattern used by DAProfileSelfTest.cpp: the
// subsystems are created explicitly and the save subsystem is driven through
// SaveNamedSlotWithContext/LoadNamedSlotWithContext. No UWorld/PIE is required.
// Console equivalents: da.SaveFuzz and da.TwelveMonthTest.

#include "DAA02GateTests.h"
#include "DACalendarSubsystem.h"
#include "DADeckLogic.h"
#include "DAEconomyTypes.h"
#include "DAInventorySubsystem.h"
#include "DAProfileSubsystem.h"
#include "DASaveGame.h"
#include "DASettings.h"
#include "DuelAcademyIsland.h"

#include "Containers/Ticker.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/UnrealMemory.h"
#include "Kismet/GameplayStatics.h"
#include "Math/RandomStream.h"
#include "Misc/CommandLine.h"
#include "Misc/Crc.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/StrongObjectPtr.h"

namespace
{
	const TCHAR* const FuzzSlotPrefix = TEXT("DASaveFuzz_Slot");
	const TCHAR* const FuzzCorruptSlot = TEXT("DASaveFuzz_Corrupt");
	const TCHAR* const FuzzMigrationSlot = TEXT("DASaveFuzz_Migrate");
	const TCHAR* const TwelveMonthSlot = TEXT("DATwelveMonth_Slot");

	constexpr int32 DefaultSaveFuzzCount = 10000;
	constexpr int32 DefaultSaveFuzzSeed = 0x5A02F022;
	constexpr int32 DefaultTwelveMonthSeed = 0x00012A02;
	constexpr int32 MaxSaveFuzzCount = 1000000;

	/** Mirror of the 16-byte trailer in DASaveGame.cpp. Keep in sync. */
	constexpr uint32 RawSaveMagic = 0x53415044; // "DAPS"
	constexpr uint32 RawSaveFormatVersion = 1;

	struct FDARawSaveTrailer
	{
		uint32 Magic = 0;
		uint32 FormatVersion = 0;
		uint32 ArchiveSize = 0;
		uint32 ArchiveCrc = 0;
	};

	static_assert(sizeof(FDARawSaveTrailer) == 16, "Raw save trailer must stay 16 bytes");

	struct FDATestReport
	{
		int32 Checks = 0;
		int32 Failures = 0;
		int32 LoggedFailures = 0;

		bool Check(bool bCondition, const FString& Label, bool bLogPass = true)
		{
			++Checks;
			if (bCondition)
			{
				if (bLogPass)
				{
					UE_LOG(LogDuelAcademyIsland, Log, TEXT("[PASS] %s"), *Label);
				}
				return true;
			}
			Fail(Label);
			return false;
		}

		void Quiet(bool bCondition, const FString& Label)
		{
			++Checks;
			if (!bCondition)
			{
				Fail(Label);
			}
		}

		void Fail(const FString& Label)
		{
			++Failures;
			if (LoggedFailures < 200)
			{
				++LoggedFailures;
				UE_LOG(LogDuelAcademyIsland, Error, TEXT("[FAIL] %s"), *Label);
			}
		}
	};

	struct FDADeepCompare
	{
		FDATestReport& Report;
		FString Prefix;

		FDADeepCompare(FDATestReport& InReport, const FString& InPrefix)
			: Report(InReport), Prefix(InPrefix)
		{
		}

		void Int(const FString& Field, int32 Actual, int32 Expected)
		{
			++Report.Checks;
			if (Actual != Expected)
			{
				Report.Fail(FString::Printf(TEXT("%s.%s (expected %d, got %d)"), *Prefix, *Field, Expected, Actual));
			}
		}

		void Bool(const FString& Field, bool bActual, bool bExpected)
		{
			++Report.Checks;
			if (bActual != bExpected)
			{
				Report.Fail(FString::Printf(TEXT("%s.%s (expected %s, got %s)"), *Prefix, *Field,
					bExpected ? TEXT("true") : TEXT("false"), bActual ? TEXT("true") : TEXT("false")));
			}
		}

		void Str(const FString& Field, const FString& Actual, const FString& Expected)
		{
			++Report.Checks;
			if (!Actual.Equals(Expected, ESearchCase::CaseSensitive))
			{
				Report.Fail(FString::Printf(TEXT("%s.%s (expected '%s', got '%s')"), *Prefix, *Field, *Expected, *Actual));
			}
		}

		void Double(const FString& Field, double Actual, double Expected, double Tolerance = 1.0e-6)
		{
			++Report.Checks;
			if (!FMath::IsFinite(Actual) || FMath::Abs(Actual - Expected) > Tolerance)
			{
				Report.Fail(FString::Printf(TEXT("%s.%s (expected %.9f, got %.9f)"), *Prefix, *Field, Expected, Actual));
			}
		}

		void StrArray(const FString& Field, const TArray<FString>& Actual, const TArray<FString>& Expected)
		{
			++Report.Checks;
			if (Actual.Num() != Expected.Num())
			{
				Report.Fail(FString::Printf(TEXT("%s.%s count (expected %d, got %d)"), *Prefix, *Field, Expected.Num(), Actual.Num()));
				return;
			}
			for (int32 Index = 0; Index < Expected.Num(); ++Index)
			{
				++Report.Checks;
				if (!Actual[Index].Equals(Expected[Index], ESearchCase::CaseSensitive))
				{
					Report.Fail(FString::Printf(TEXT("%s.%s[%d] (expected '%s', got '%s')"),
						*Prefix, *Field, Index, *Expected[Index], *Actual[Index]));
				}
			}
		}

		void IntArray(const FString& Field, const TArray<int32>& Actual, const TArray<int32>& Expected)
		{
			++Report.Checks;
			if (Actual.Num() != Expected.Num())
			{
				Report.Fail(FString::Printf(TEXT("%s.%s count (expected %d, got %d)"), *Prefix, *Field, Expected.Num(), Actual.Num()));
				return;
			}
			for (int32 Index = 0; Index < Expected.Num(); ++Index)
			{
				++Report.Checks;
				if (Actual[Index] != Expected[Index])
				{
					Report.Fail(FString::Printf(TEXT("%s.%s[%d] (expected %d, got %d)"),
						*Prefix, *Field, Index, Expected[Index], Actual[Index]));
				}
			}
		}

		void BoolMap(const FString& Field, const TMap<FString, bool>& Actual, const TMap<FString, bool>& Expected)
		{
			TArray<FString> ActualKeys;
			TArray<FString> ExpectedKeys;
			Actual.GetKeys(ActualKeys);
			Expected.GetKeys(ExpectedKeys);
			++Report.Checks;
			if (ActualKeys.Num() != ExpectedKeys.Num())
			{
				Report.Fail(FString::Printf(TEXT("%s.%s count (expected %d, got %d)"), *Prefix, *Field, ExpectedKeys.Num(), ActualKeys.Num()));
			}
			for (const FString& Key : ExpectedKeys)
			{
				++Report.Checks;
				const bool* ActualValue = Actual.Find(Key);
				const bool* ExpectedValue = Expected.Find(Key);
				if (!ActualValue || !ExpectedValue || *ActualValue != *ExpectedValue)
				{
					Report.Fail(FString::Printf(TEXT("%s.%s['%s'] mismatch"), *Prefix, *Field, *Key));
				}
			}
			for (const FString& Key : ActualKeys)
			{
				if (!Expected.Contains(Key))
				{
					++Report.Checks;
					Report.Fail(FString::Printf(TEXT("%s.%s['%s'] is unexpected"), *Prefix, *Field, *Key));
				}
			}
		}

		void IntMap(const FString& Field, const TMap<FString, int32>& Actual, const TMap<FString, int32>& Expected)
		{
			TArray<FString> ActualKeys;
			TArray<FString> ExpectedKeys;
			Actual.GetKeys(ActualKeys);
			Expected.GetKeys(ExpectedKeys);
			++Report.Checks;
			if (ActualKeys.Num() != ExpectedKeys.Num())
			{
				Report.Fail(FString::Printf(TEXT("%s.%s count (expected %d, got %d)"), *Prefix, *Field, ExpectedKeys.Num(), ActualKeys.Num()));
			}
			for (const FString& Key : ExpectedKeys)
			{
				++Report.Checks;
				const int32* ActualValue = Actual.Find(Key);
				const int32* ExpectedValue = Expected.Find(Key);
				if (!ActualValue || !ExpectedValue || *ActualValue != *ExpectedValue)
				{
					Report.Fail(FString::Printf(TEXT("%s.%s['%s'] mismatch"), *Prefix, *Field, *Key));
				}
			}
			for (const FString& Key : ActualKeys)
			{
				if (!Expected.Contains(Key))
				{
					++Report.Checks;
					Report.Fail(FString::Printf(TEXT("%s.%s['%s'] is unexpected"), *Prefix, *Field, *Key));
				}
			}
		}

		void StringMap(const FString& Field, const TMap<FString, FString>& Actual, const TMap<FString, FString>& Expected)
		{
			TArray<FString> ActualKeys;
			TArray<FString> ExpectedKeys;
			Actual.GetKeys(ActualKeys);
			Expected.GetKeys(ExpectedKeys);
			++Report.Checks;
			if (ActualKeys.Num() != ExpectedKeys.Num())
			{
				Report.Fail(FString::Printf(TEXT("%s.%s count (expected %d, got %d)"), *Prefix, *Field, ExpectedKeys.Num(), ActualKeys.Num()));
			}
			for (const FString& Key : ExpectedKeys)
			{
				++Report.Checks;
				const FString* ActualValue = Actual.Find(Key);
				const FString* ExpectedValue = Expected.Find(Key);
				if (!ActualValue || !ExpectedValue || !ActualValue->Equals(*ExpectedValue, ESearchCase::CaseSensitive))
				{
					Report.Fail(FString::Printf(TEXT("%s.%s['%s'] mismatch"), *Prefix, *Field, *Key));
				}
			}
			for (const FString& Key : ActualKeys)
			{
				if (!Expected.Contains(Key))
				{
					++Report.Checks;
					Report.Fail(FString::Printf(TEXT("%s.%s['%s'] is unexpected"), *Prefix, *Field, *Key));
				}
			}
		}

		void Emails(const TMap<FString, FDAEmailState>& Actual, const TMap<FString, FDAEmailState>& Expected)
		{
			TArray<FString> ActualKeys;
			TArray<FString> ExpectedKeys;
			Actual.GetKeys(ActualKeys);
			Expected.GetKeys(ExpectedKeys);
			++Report.Checks;
			if (ActualKeys.Num() != ExpectedKeys.Num())
			{
				Report.Fail(FString::Printf(TEXT("%s.emails count (expected %d, got %d)"), *Prefix, ExpectedKeys.Num(), ActualKeys.Num()));
			}
			for (const FString& Key : ExpectedKeys)
			{
				const FDAEmailState* ActualState = Actual.Find(Key);
				const FDAEmailState* ExpectedState = Expected.Find(Key);
				++Report.Checks;
				if (!ActualState || !ExpectedState)
				{
					Report.Fail(FString::Printf(TEXT("%s.emails['%s'] missing"), *Prefix, *Key));
					continue;
				}
				Bool(FString::Printf(TEXT("emails['%s'].unlocked"), *Key), ActualState->bUnlocked, ExpectedState->bUnlocked);
				StrArray(FString::Printf(TEXT("emails['%s'].read"), *Key), ActualState->ReadIds, ExpectedState->ReadIds);
				StrArray(FString::Printf(TEXT("emails['%s'].requests"), *Key), ActualState->PendingDuelRequests, ExpectedState->PendingDuelRequests);
			}
			for (const FString& Key : ActualKeys)
			{
				if (!Expected.Contains(Key))
				{
					++Report.Checks;
					Report.Fail(FString::Printf(TEXT("%s.emails['%s'] is unexpected"), *Prefix, *Key));
				}
			}
		}

		void Inventory(const FDAEInventorySaveData& Actual, const FDAEInventorySaveData& Expected)
		{
			Int(TEXT("inventory.version"), Actual.Version, Expected.Version);
			Int(TEXT("inventory.max_owned_copies"), Actual.MaxOwnedCopies, Expected.MaxOwnedCopies);

			TArray<int32> ActualKeys;
			TArray<int32> ExpectedKeys;
			Actual.Counts.GetKeys(ActualKeys);
			Expected.Counts.GetKeys(ExpectedKeys);
			++Report.Checks;
			if (ActualKeys.Num() != ExpectedKeys.Num())
			{
				Report.Fail(FString::Printf(TEXT("%s.inventory.counts count (expected %d, got %d)"), *Prefix, ExpectedKeys.Num(), ActualKeys.Num()));
			}
			for (const int32 Key : ExpectedKeys)
			{
				++Report.Checks;
				const int32* ActualValue = Actual.Counts.Find(Key);
				const int32* ExpectedValue = Expected.Counts.Find(Key);
				if (!ActualValue || !ExpectedValue || *ActualValue != *ExpectedValue)
				{
					Report.Fail(FString::Printf(TEXT("%s.inventory.counts[%d] mismatch"), *Prefix, Key));
				}
			}
			for (const int32 Key : ActualKeys)
			{
				if (!Expected.Counts.Contains(Key))
				{
					++Report.Checks;
					Report.Fail(FString::Printf(TEXT("%s.inventory.counts[%d] is unexpected"), *Prefix, Key));
				}
			}

			++Report.Checks;
			if (Actual.PendingAnte.Num() != Expected.PendingAnte.Num())
			{
				Report.Fail(FString::Printf(TEXT("%s.inventory.pending_ante count (expected %d, got %d)"),
					*Prefix, Expected.PendingAnte.Num(), Actual.PendingAnte.Num()));
				return;
			}
			for (int32 Index = 0; Index < Expected.PendingAnte.Num(); ++Index)
			{
				const FDAEAnteRecord& A = Actual.PendingAnte[Index];
				const FDAEAnteRecord& E = Expected.PendingAnte[Index];
				Int(FString::Printf(TEXT("inventory.pending_ante[%d].card_id"), Index), A.CardId, E.CardId);
				Str(FString::Printf(TEXT("inventory.pending_ante[%d].duel_id"), Index), A.DuelId, E.DuelId);
				Str(FString::Printf(TEXT("inventory.pending_ante[%d].source"), Index), A.Source, E.Source);
			}
		}

		void Decks(const FDAEDeckSaveData& Actual, const FDAEDeckSaveData& Expected)
		{
			Int(TEXT("decks.version"), Actual.Version, Expected.Version);
			Str(TEXT("decks.active_deck_id"), Actual.ActiveDeckId, Expected.ActiveDeckId);
			++Report.Checks;
			if (Actual.Decks.Num() != Expected.Decks.Num())
			{
				Report.Fail(FString::Printf(TEXT("%s.decks count (expected %d, got %d)"), *Prefix, Expected.Decks.Num(), Actual.Decks.Num()));
				return;
			}
			for (int32 Index = 0; Index < Expected.Decks.Num(); ++Index)
			{
				const FDAEDeck& A = Actual.Decks[Index];
				const FDAEDeck& E = Expected.Decks[Index];
				const FString Base = FString::Printf(TEXT("decks[%d]"), Index);
				Str(Base + TEXT(".id"), A.Id, E.Id);
				Str(Base + TEXT(".name"), A.Name, E.Name);
				IntArray(Base + TEXT(".main"), A.Main, E.Main);
				IntArray(Base + TEXT(".extra"), A.Extra, E.Extra);
				Bool(Base + TEXT(".starter"), A.bStarter, E.bStarter);
				Bool(Base + TEXT(".player_deck"), A.bPlayerDeck, E.bPlayerDeck);
			}
		}
	};

	struct FDASaveSnapshot
	{
		FString PlayerName;
		FString Gender;
		FString Title;
		FString TemporaryTitle;
		EDADorm Dorm = EDADorm::Slifer;
		int32 DP = 0;
		int32 TemporaryTitleDays = 0;
		double PlaytimeSeconds = 0.0;
		bool bInitialized = false;
		TMap<FString, bool> Flags;
		TMap<FString, int32> Counters;
		TMap<FString, FDAEmailState> Emails;

		int32 Year = 1;
		int32 MonthIndex = 0;
		int32 MonthNumber = 10;
		int32 Day = 7;
		int32 Hour = 8;
		int32 AbsoluteDay = 0;
		EDADayPeriod Period = EDADayPeriod::AM;
		EDADayOfWeek Weekday = EDADayOfWeek::Saturday;

		EDAAnimationSpeed AnimationSpeed = EDAAnimationSpeed::Normal;
		bool bConfirmActivation = true;
		EDATextSpeed TextSpeed = EDATextSpeed::Normal;
		float BgmVolume = 0.8f;
		float SfxVolume = 0.8f;
		bool bSubtitles = true;
		FString LanguageKey = TEXT("en");
		TMap<FString, FString> Controls;

		FDAEInventorySaveData Inventory;
		FDAEDeckSaveData Decks;
	};

	struct FDAGateContext
	{
		TStrongObjectPtr<UGameInstance> GameInstance;
		UDAProfileSubsystem* Profile = nullptr;
		UDACalendarSubsystem* Calendar = nullptr;
		UDASettings* Settings = nullptr;
		UDASaveSubsystem* Save = nullptr;
		UDAInventorySubsystem* Inventory = nullptr;
		UDADeckLogic* Decks = nullptr;

		FDAGateContext()
			: GameInstance(NewObject<UGameInstance>(GetTransientPackage()))
		{
			Profile = NewObject<UDAProfileSubsystem>(GameInstance.Get());
			Calendar = NewObject<UDACalendarSubsystem>(GameInstance.Get());
			Settings = NewObject<UDASettings>(GameInstance.Get());
			Save = NewObject<UDASaveSubsystem>(GameInstance.Get());
			Inventory = NewObject<UDAInventorySubsystem>(GameInstance.Get());
			Decks = NewObject<UDADeckLogic>(GameInstance.Get());

			Settings->ResetToDefaults();
			Calendar->LoadCalendarData();

			Save->RegisterPayloadProvider(Inventory);
			Save->RegisterPayloadProvider(Decks);
			Profile->SetInventoryProvider(Inventory);
			Profile->SetDeckProvider(Decks);
		}
	};

	FDASaveSnapshot CaptureSnapshot(const FDAGateContext& Context)
	{
		FDASaveSnapshot Snapshot;
		Snapshot.PlayerName = Context.Profile->GetPlayerName();
		Snapshot.Gender = Context.Profile->GetGender();
		Snapshot.Title = Context.Profile->GetTitle();
		Snapshot.TemporaryTitle = Context.Profile->GetTemporaryTitle();
		Snapshot.Dorm = Context.Profile->GetDorm();
		Snapshot.DP = Context.Profile->GetDP();
		Snapshot.TemporaryTitleDays = Context.Profile->GetTemporaryTitleDaysRemaining();
		Snapshot.PlaytimeSeconds = Context.Profile->GetPlaytimeSeconds();
		Snapshot.bInitialized = Context.Profile->IsInitialized();
		Snapshot.Flags = Context.Profile->GetFlags();
		Snapshot.Counters = Context.Profile->GetCounters();
		Snapshot.Emails = Context.Profile->GetEmails();

		Snapshot.Year = Context.Calendar->GetYear();
		Snapshot.MonthIndex = Context.Calendar->GetMonthIndex();
		Snapshot.MonthNumber = Context.Calendar->GetMonthNumber();
		Snapshot.Day = Context.Calendar->GetDay();
		Snapshot.Hour = Context.Calendar->GetHour();
		Snapshot.AbsoluteDay = Context.Calendar->GetAbsoluteDay();
		Snapshot.Period = Context.Calendar->GetPeriod();
		Snapshot.Weekday = Context.Calendar->GetWeekday();

		Snapshot.AnimationSpeed = Context.Settings->GetAnimationSpeed();
		Snapshot.bConfirmActivation = Context.Settings->GetConfirmActivation();
		Snapshot.TextSpeed = Context.Settings->GetTextSpeed();
		Snapshot.BgmVolume = Context.Settings->GetBgmVolume();
		Snapshot.SfxVolume = Context.Settings->GetSfxVolume();
		Snapshot.bSubtitles = Context.Settings->GetSubtitles();
		Snapshot.LanguageKey = Context.Settings->GetLanguageKey();
		Snapshot.Controls = Context.Settings->GetControls();

		Snapshot.Inventory = Context.Inventory->GetSaveData();
		Snapshot.Decks = Context.Decks->GetSaveData();
		return Snapshot;
	}

	void CompareSnapshot(FDATestReport& Report, const FDASaveSnapshot& Expected, const FDAGateContext& Context, const FString& Label)
	{
		FDADeepCompare Compare(Report, Label);

		Compare.Str(TEXT("profile.name"), Context.Profile->GetPlayerName(), Expected.PlayerName);
		Compare.Str(TEXT("profile.gender"), Context.Profile->GetGender(), Expected.Gender);
		Compare.Str(TEXT("profile.title"), Context.Profile->GetTitle(), Expected.Title);
		Compare.Str(TEXT("profile.temporary_title"), Context.Profile->GetTemporaryTitle(), Expected.TemporaryTitle);
		Compare.Int(TEXT("profile.dorm"), static_cast<int32>(Context.Profile->GetDorm()), static_cast<int32>(Expected.Dorm));
		Compare.Int(TEXT("profile.dp"), Context.Profile->GetDP(), Expected.DP);
		Compare.Int(TEXT("profile.temporary_title_days"), Context.Profile->GetTemporaryTitleDaysRemaining(), Expected.TemporaryTitleDays);
		Compare.Double(TEXT("profile.playtime_seconds"), Context.Profile->GetPlaytimeSeconds(), Expected.PlaytimeSeconds, 1.0e-6);
		Compare.Bool(TEXT("profile.initialized"), Context.Profile->IsInitialized(), Expected.bInitialized);
		Compare.BoolMap(TEXT("flags"), Context.Profile->GetFlags(), Expected.Flags);
		Compare.IntMap(TEXT("counters"), Context.Profile->GetCounters(), Expected.Counters);
		Compare.Emails(Context.Profile->GetEmails(), Expected.Emails);

		Compare.Int(TEXT("calendar.year"), Context.Calendar->GetYear(), Expected.Year);
		Compare.Int(TEXT("calendar.month_index"), Context.Calendar->GetMonthIndex(), Expected.MonthIndex);
		Compare.Int(TEXT("calendar.month_number"), Context.Calendar->GetMonthNumber(), Expected.MonthNumber);
		Compare.Int(TEXT("calendar.day"), Context.Calendar->GetDay(), Expected.Day);
		Compare.Int(TEXT("calendar.hour"), Context.Calendar->GetHour(), Expected.Hour);
		Compare.Int(TEXT("calendar.absolute_day"), Context.Calendar->GetAbsoluteDay(), Expected.AbsoluteDay);
		Compare.Int(TEXT("calendar.period"), static_cast<int32>(Context.Calendar->GetPeriod()), static_cast<int32>(Expected.Period));
		Compare.Int(TEXT("calendar.weekday"), static_cast<int32>(Context.Calendar->GetWeekday()), static_cast<int32>(Expected.Weekday));

		Compare.Int(TEXT("settings.animation_speed"), static_cast<int32>(Context.Settings->GetAnimationSpeed()), static_cast<int32>(Expected.AnimationSpeed));
		Compare.Bool(TEXT("settings.confirm_activation"), Context.Settings->GetConfirmActivation(), Expected.bConfirmActivation);
		Compare.Int(TEXT("settings.text_speed"), static_cast<int32>(Context.Settings->GetTextSpeed()), static_cast<int32>(Expected.TextSpeed));
		Compare.Double(TEXT("settings.bgm_volume"), Context.Settings->GetBgmVolume(), Expected.BgmVolume, 1.0e-6);
		Compare.Double(TEXT("settings.sfx_volume"), Context.Settings->GetSfxVolume(), Expected.SfxVolume, 1.0e-6);
		Compare.Bool(TEXT("settings.subtitles"), Context.Settings->GetSubtitles(), Expected.bSubtitles);
		Compare.Str(TEXT("settings.language"), Context.Settings->GetLanguageKey(), Expected.LanguageKey);
		Compare.StringMap(TEXT("settings.controls"), Context.Settings->GetControls(), Expected.Controls);

		Compare.Inventory(Context.Inventory->GetSaveData(), Expected.Inventory);
		Compare.Decks(Context.Decks->GetSaveData(), Expected.Decks);
	}

	// ------------------------------------------------------------------ random state

	int32 RandRange(FRandomStream& Stream, int32 Min, int32 Max)
	{
		if (Max <= Min)
		{
			return Min;
		}
		return Stream.RandRange(Min, Max);
	}

	FString RandomToken(FRandomStream& Stream, const TCHAR* Prefix, int32 MinLength, int32 MaxLength)
	{
		static const FString Pool = TEXT("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-");
		FString Out = Prefix;
		const int32 Length = RandRange(Stream, MinLength, MaxLength);
		for (int32 Index = 0; Index < Length; ++Index)
		{
			Out.AppendChar(Pool[Stream.RandRange(0, Pool.Len() - 1)]);
		}
		return Out;
	}

	FString RandomName(FRandomStream& Stream)
	{
		static const TCHAR* const Names[] = {
			TEXT("Fuzz Duelist"),
			TEXT("Jaden \"The King\" Yuki"),
			TEXT("Back\\slash"),
			TEXT("Line\nBreak"),
			TEXT("Aster Phoenix"),
			TEXT("Alexis Rhodes"),
			TEXT("Chazz Princeton"),
			TEXT("Zane Truesdale"),
			TEXT("Syrus Truesdale"),
			TEXT("Bastion Misawa")
		};
		FString Name = Names[Stream.RandRange(0, static_cast<int32>(UE_ARRAY_COUNT(Names)) - 1)];
		if (Stream.RandRange(0, 1) == 1)
		{
			Name += FString::Printf(TEXT(" %s"), *RandomToken(Stream, TEXT(""), 2, 10));
		}
		return Name.TrimStartAndEnd();
	}

	FString RandomTitle(FRandomStream& Stream)
	{
		static const TCHAR* const Titles[] = {
			TEXT("Apprentice Duelist"),
			TEXT("Rookie Duelist"),
			TEXT("Occult Duelist"),
			TEXT("Dropout Boy"),
			TEXT("King of Games"),
			TEXT("Quote \"Title\""),
			TEXT("Back\\slash Title")
		};
		return FString(Titles[Stream.RandRange(0, static_cast<int32>(UE_ARRAY_COUNT(Titles)) - 1)]).TrimStartAndEnd();
	}

	FString RandomLanguage(FRandomStream& Stream)
	{
		static const TCHAR* const Languages[] = { TEXT("en"), TEXT("fr"), TEXT("de"), TEXT("es"), TEXT("ja"), TEXT("pt-BR") };
		return Languages[Stream.RandRange(0, static_cast<int32>(UE_ARRAY_COUNT(Languages)) - 1)];
	}

	void GenerateRandomInventory(FDAGateContext& Context, FRandomStream& Stream)
	{
		FDAEInventorySaveData Data;
		Data.Version = 1;
		Data.MaxOwnedCopies = RandRange(Stream, 1, 99);

		TSet<int32> CardIds;
		const int32 CountEntries = RandRange(Stream, 0, 10);
		for (int32 Index = 0; Index < CountEntries; ++Index)
		{
			const int32 CardId = RandRange(Stream, 1, 1200);
			if (CardIds.Contains(CardId))
			{
				continue;
			}
			CardIds.Add(CardId);
			Data.Counts.Add(CardId, RandRange(Stream, 1, 99));
		}

		const int32 AnteEntries = RandRange(Stream, 0, 3);
		for (int32 Index = 0; Index < AnteEntries; ++Index)
		{
			FDAEAnteRecord Record;
			Record.CardId = RandRange(Stream, 1, 1200);
			Record.DuelId = RandomToken(Stream, TEXT("duel_"), 2, 10);
			Record.Source = RandomToken(Stream, TEXT("source_"), 2, 10);
			Data.PendingAnte.Add(Record);
		}

		FString Error;
		Context.Inventory->ApplySaveData(Data, Error);
	}

	void GenerateRandomDecks(FDAGateContext& Context, FRandomStream& Stream)
	{
		FDAEDeckSaveData Data;
		Data.Version = 1;
		const int32 DeckCount = RandRange(Stream, 1, 4);
		for (int32 Index = 0; Index < DeckCount; ++Index)
		{
			FDAEDeck Deck;
			Deck.Id = FString::Printf(TEXT("deck_%d_%s"), Index, *RandomToken(Stream, TEXT(""), 2, 8));
			Deck.Name = FString::Printf(TEXT("Deck %d %s"), Index, *RandomToken(Stream, TEXT(""), 2, 8));
			Deck.bPlayerDeck = true;
			Deck.bStarter = Stream.RandRange(0, 1) == 1;

			const int32 MainCount = RandRange(Stream, 0, 12);
			for (int32 Card = 0; Card < MainCount; ++Card)
			{
				Deck.Main.Add(RandRange(Stream, 1, 1200));
			}
			const int32 ExtraCount = RandRange(Stream, 0, 5);
			for (int32 Card = 0; Card < ExtraCount; ++Card)
			{
				Deck.Extra.Add(RandRange(Stream, 1, 1200));
			}
			Data.Decks.Add(Deck);
		}

		Data.ActiveDeckId = Stream.RandRange(0, 3) == 0
			? FString()
			: Data.Decks[Stream.RandRange(0, Data.Decks.Num() - 1)].Id;

		FString Error;
		Context.Decks->ApplySaveData(Data, Error);
	}

	void GenerateRandomState(FDAGateContext& Context, FRandomStream& Stream)
	{
		Context.Profile->InitializeNewGame(RandomName(Stream));
		Context.Profile->SpendDP(Context.Profile->GetDP());

		const int32 TargetDP = Stream.RandRange(0, 49) == 0
			? TNumericLimits<int32>::Max()
			: RandRange(Stream, 0, 1000000000);
		Context.Profile->AwardDP(TargetDP);

		Context.Profile->SetGender(Stream.RandRange(0, 3) == 0
			? FString()
			: RandomToken(Stream, TEXT(""), 3, 12));
		Context.Profile->SetDorm(static_cast<EDADorm>(Stream.RandRange(0, 3)));
		Context.Profile->SetTitle(RandomTitle(Stream));

		if (Stream.RandRange(0, 2) == 0)
		{
			Context.Profile->SetTemporaryTitle(RandomTitle(Stream), RandRange(Stream, 1, 365));
			Context.Profile->SetTitle(RandomTitle(Stream));
		}
		Context.Profile->AddPlaytime(Stream.FRandRange(0.0f, 1000000.0f));

		const int32 FlagCount = RandRange(Stream, 0, 20);
		for (int32 Index = 0; Index < FlagCount; ++Index)
		{
			const FString Key = FString::Printf(TEXT("flag_%d_%s"), Index, *RandomToken(Stream, TEXT(""), 2, 8));
			Context.Profile->SetFlag(Key, Stream.RandRange(0, 1) == 1);
		}

		const int32 CounterCount = RandRange(Stream, 0, 20);
		for (int32 Index = 0; Index < CounterCount; ++Index)
		{
			const FString Key = FString::Printf(TEXT("counter_%d_%s"), Index, *RandomToken(Stream, TEXT(""), 2, 8));
			const int32 Value = Stream.RandRange(0, 20) == 0
				? TNumericLimits<int32>::Max()
				: RandRange(Stream, 0, 1000000);
			Context.Profile->SetCounter(Key, Value);
		}

		const int32 ContactCount = RandRange(Stream, 0, 8);
		for (int32 Index = 0; Index < ContactCount; ++Index)
		{
			const FString Contact = FString::Printf(TEXT("contact_%d"), Index);
			const bool bUnlocked = Stream.RandRange(0, 1) == 1;
			if (bUnlocked)
			{
				Context.Profile->UnlockEmail(Contact);
				const int32 ReadCount = RandRange(Stream, 0, 4);
				for (int32 ReadIndex = 0; ReadIndex < ReadCount; ++ReadIndex)
				{
					Context.Profile->MarkEmailRead(Contact, FString::Printf(TEXT("msg_%d"), ReadIndex));
				}
			}
			const int32 RequestCount = RandRange(Stream, 0, 4);
			for (int32 RequestIndex = 0; RequestIndex < RequestCount; ++RequestIndex)
			{
				Context.Profile->AddDuelRequest(Contact, FString::Printf(TEXT("req_%d"), RequestIndex));
			}
		}

		const int32 Year = RandRange(Stream, 1, 6);
		const int32 MonthIndex = RandRange(Stream, 0, 11);
		const int32 Day = RandRange(Stream, 1, Context.Calendar->GetDaysInMonth(Year, MonthIndex));
		const EDADayPeriod Period = static_cast<EDADayPeriod>(Stream.RandRange(0, 2));
		Context.Calendar->SetDate(Year, MonthIndex, Day, Period);

		Context.Settings->ResetToDefaults();
		Context.Settings->SetAnimationSpeed(static_cast<EDAAnimationSpeed>(Stream.RandRange(0, 2)));
		Context.Settings->SetConfirmActivation(Stream.RandRange(0, 1) == 1);
		Context.Settings->SetTextSpeed(static_cast<EDATextSpeed>(Stream.RandRange(0, 3)));
		Context.Settings->SetBgmVolume(Stream.FRandRange(0.0f, 1.0f));
		Context.Settings->SetSfxVolume(Stream.FRandRange(0.0f, 1.0f));
		Context.Settings->SetSubtitles(Stream.RandRange(0, 1) == 1);
		Context.Settings->SetLanguageKey(RandomLanguage(Stream));

		static const TCHAR* const Actions[] = { TEXT("Interact"), TEXT("Jump"), TEXT("Pause"), TEXT("CustomAction") };
		static const TCHAR* const Keys[] = { TEXT("E"), TEXT("F"), TEXT("Q"), TEXT("R"), TEXT("Space"), TEXT("Mouse") };
		const int32 ControlCount = RandRange(Stream, 0, 6);
		for (int32 Index = 0; Index < ControlCount; ++Index)
		{
			const TCHAR* Action = Actions[Stream.RandRange(0, static_cast<int32>(UE_ARRAY_COUNT(Actions)) - 1)];
			Context.Settings->SetControl(Action, Keys[Stream.RandRange(0, static_cast<int32>(UE_ARRAY_COUNT(Keys)) - 1)]);
		}

		GenerateRandomInventory(Context, Stream);
		GenerateRandomDecks(Context, Stream);
	}

	void PoisonContext(FDAGateContext& Context)
	{
		Context.Profile->InitializeNewGame(TEXT("Poison State"));
		Context.Profile->SetDorm(EDADorm::White);
		Context.Profile->SetTitle(TEXT("Poison Title"));
		Context.Profile->SetFlag(TEXT("__poison"), true);
		Context.Profile->SetCounter(TEXT("__poison"), 1);
		Context.Profile->UnlockEmail(TEXT("__poison"));
		Context.Profile->AddPlaytime(1.0);

		Context.Calendar->SetDate(1, 0, 1, EDADayPeriod::AM);
		Context.Settings->ResetToDefaults();
		Context.Settings->SetBgmVolume(0.01f);
		Context.Settings->SetSfxVolume(0.02f);
		Context.Settings->SetControl(TEXT("Interact"), TEXT("P"));

		FString Error;
		FDAEInventorySaveData PoisonInventory;
		PoisonInventory.Version = 1;
		PoisonInventory.MaxOwnedCopies = 1;
		PoisonInventory.Counts.Add(1, 1);
		Context.Inventory->ApplySaveData(PoisonInventory, Error);

		FDAEDeckSaveData PoisonDecks;
		PoisonDecks.Version = 1;
		FDAEDeck PoisonDeck;
		PoisonDeck.Id = TEXT("poison_deck");
		PoisonDeck.Name = TEXT("Poison Deck");
		PoisonDeck.bPlayerDeck = true;
		PoisonDecks.Decks.Add(PoisonDeck);
		PoisonDecks.ActiveDeckId = PoisonDeck.Id;
		Context.Decks->ApplySaveData(PoisonDecks, Error);
	}

	// ------------------------------------------------------------------ save file helpers

	bool WriteRawSaveFile(FDAGateContext& Context, const FString& SlotName, const FString& Json, int32 WrapperVersion, FString& OutError)
	{
		OutError.Reset();
		if (!Context.Save->DeleteNamedSlot(SlotName, OutError))
		{
			return false;
		}

		UDASaveGame* SaveObject = NewObject<UDASaveGame>();
		SaveObject->Version = WrapperVersion;
		SaveObject->JsonPayload = Json;
		SaveObject->PayloadHash = static_cast<int32>(FCrc::StrCrc32(*Json));

		TArray<uint8> Archive;
		if (!UGameplayStatics::SaveGameToMemory(SaveObject, Archive) || Archive.Num() == 0)
		{
			OutError = TEXT("Raw save archive could not be built.");
			return false;
		}

		TArray<uint8> FileBytes = Archive;
		FDARawSaveTrailer Trailer;
		Trailer.Magic = RawSaveMagic;
		Trailer.FormatVersion = RawSaveFormatVersion;
		Trailer.ArchiveSize = static_cast<uint32>(Archive.Num());
		Trailer.ArchiveCrc = FCrc::MemCrc32(Archive.GetData(), Archive.Num());
		const int32 Offset = FileBytes.Num();
		FileBytes.AddUninitialized(static_cast<int32>(sizeof(FDARawSaveTrailer)));
		FMemory::Memcpy(FileBytes.GetData() + Offset, &Trailer, sizeof(FDARawSaveTrailer));

		const FString Path = UDASaveSubsystem::GetSaveFilePath(SlotName);
		IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
		if (!FFileHelper::SaveArrayToFile(FileBytes, *Path))
		{
			OutError = FString::Printf(TEXT("Could not write raw save file %s."), *Path);
			return false;
		}
		return true;
	}

	int64 GetSaveFileSize(const FString& SlotName)
	{
		return IFileManager::Get().FileSize(*UDASaveSubsystem::GetSaveFilePath(SlotName));
	}

	int32 FuzzSlotIndexForIteration(int32 Iteration)
	{
		return Iteration % UDASaveSubsystem::NumSlots;
	}

	FString FuzzSlotNameForIndex(int32 SlotIndex)
	{
		return FString::Printf(TEXT("%s%d"), FuzzSlotPrefix, SlotIndex);
	}

	bool SaveRoundTripCase(FDAGateContext& Context, FDATestReport& Report, FRandomStream& Stream, int32 Iteration, int32& InOutMaxSize)
	{
		GenerateRandomState(Context, Stream);
		const FDASaveSnapshot Expected = CaptureSnapshot(Context);

		const int32 LogicalSlot = FuzzSlotIndexForIteration(Iteration);
		const FString SlotName = FuzzSlotNameForIndex(LogicalSlot);
		FString Error;
		if (!Context.Save->SaveNamedSlotWithContext(SlotName, LogicalSlot, Context.Profile, Context.Calendar, Context.Settings, Error))
		{
			Report.Fail(FString::Printf(TEXT("DASaveFuzz save failed at iteration %d: %s"), Iteration, *Error));
			return false;
		}

		const int64 FileSize = GetSaveFileSize(SlotName);
		if (FileSize > InOutMaxSize)
		{
			InOutMaxSize = static_cast<int32>(FileSize);
		}

		const FDASaveSlotInfo Info = Context.Save->GetSlotInfo(SlotName, LogicalSlot);
		FDADeepCompare InfoCompare(Report, FString::Printf(TEXT("roundtrip[%d].slot_info"), Iteration));
		InfoCompare.Bool(TEXT("exists"), Info.bExists, true);
		InfoCompare.Bool(TEXT("corrupt"), Info.bCorrupt, false);
		InfoCompare.Bool(TEXT("using_backup"), Info.bUsingBackup, false);
		InfoCompare.Bool(TEXT("autosave"), Info.bIsAutosave, LogicalSlot == UDASaveSubsystem::AutosaveSlotIndex);
		InfoCompare.Int(TEXT("slot_index"), Info.SlotIndex, LogicalSlot);
		InfoCompare.Str(TEXT("slot_name"), Info.SlotName, SlotName);
		InfoCompare.Str(TEXT("name"), Info.PlayerName, Expected.PlayerName);
		InfoCompare.Str(TEXT("title"), Info.Title, Expected.Title);
		InfoCompare.Int(TEXT("dorm"), static_cast<int32>(Info.Dorm), static_cast<int32>(Expected.Dorm));
		InfoCompare.Int(TEXT("dp"), Info.DP, Expected.DP);
		InfoCompare.Int(TEXT("year"), Info.Year, Expected.Year);
		InfoCompare.Int(TEXT("month_index"), Info.MonthIndex, Expected.MonthIndex);
		InfoCompare.Int(TEXT("day"), Info.Day, Expected.Day);
		InfoCompare.Int(TEXT("period"), static_cast<int32>(Info.Period), static_cast<int32>(Expected.Period));
		InfoCompare.Double(TEXT("playtime"), Info.PlaytimeSeconds, Expected.PlaytimeSeconds, 1.0e-6);
		InfoCompare.Int(TEXT("version"), Info.Version, UDASaveSubsystem::CurrentVersion);
		InfoCompare.Bool(TEXT("saved_at_present"), !Info.SavedAtUtc.IsEmpty(), true);

		PoisonContext(Context);
		bool bRecovered = true;
		if (!Context.Save->LoadNamedSlotWithContext(SlotName, Context.Profile, Context.Calendar, Context.Settings, Error, &bRecovered))
		{
			Report.Fail(FString::Printf(TEXT("DASaveFuzz load failed at iteration %d: %s"), Iteration, *Error));
			return false;
		}
		Report.Quiet(!bRecovered, FString::Printf(TEXT("roundtrip[%d] clean load used the backup"), Iteration));
		CompareSnapshot(Report, Expected, Context, FString::Printf(TEXT("roundtrip[%d]"), Iteration));
		return true;
	}

	const TCHAR* CorruptionModeName(int32 Mode)
	{
		switch (Mode)
		{
		case 0: return TEXT("flip");
		case 1: return TEXT("truncate");
		case 2: return TEXT("duplicate");
		case 3: return TEXT("reorder");
		case 4: return TEXT("append");
		default: return TEXT("unknown");
		}
	}

	void CorruptBytes(TArray<uint8>& Bytes, int32 Mode, FRandomStream& Stream)
	{
		const TArray<uint8> Original = Bytes;
		if (Bytes.Num() == 0)
		{
			Bytes.Add(0xFF);
			return;
		}

		switch (Mode)
		{
		case 0: // flip
		{
			const int32 Count = FMath::Min(RandRange(Stream, 1, 8), Bytes.Num());
			for (int32 Index = 0; Index < Count; ++Index)
			{
				const int32 Offset = RandRange(Stream, 0, Bytes.Num() - 1);
				Bytes[Offset] = static_cast<uint8>(Bytes[Offset] ^ (1u << RandRange(Stream, 0, 7)));
			}
			break;
		}
		case 1: // truncate
		{
			Bytes.SetNum(RandRange(Stream, 0, Bytes.Num() - 1));
			break;
		}
		case 2: // duplicate a chunk at a random offset
		{
			const int32 Source = RandRange(Stream, 0, Bytes.Num() - 1);
			const int32 Length = FMath::Min(RandRange(Stream, 1, 32), Bytes.Num() - Source);
			const int32 Target = RandRange(Stream, 0, Bytes.Num());
			TArray<uint8> Chunk;
			Chunk.Append(Bytes.GetData() + Source, Length);
			for (int32 Index = Chunk.Num() - 1; Index >= 0; --Index)
			{
				Bytes.Insert(Chunk[Index], Target);
			}
			break;
		}
		case 3: // reorder: swap two bytes and reverse a small run
		{
			const int32 First = RandRange(Stream, 0, Bytes.Num() - 1);
			const int32 Second = RandRange(Stream, 0, Bytes.Num() - 1);
			const uint8 Temp = Bytes[First];
			Bytes[First] = Bytes[Second];
			Bytes[Second] = Temp;

			const int32 RunStart = RandRange(Stream, 0, Bytes.Num() - 1);
			const int32 RunLength = FMath::Min(RandRange(Stream, 1, 16), Bytes.Num() - RunStart);
			for (int32 Index = 0; Index < RunLength / 2; ++Index)
			{
				const int32 A = RunStart + Index;
				const int32 B = RunStart + RunLength - 1 - Index;
				const uint8 Swap = Bytes[A];
				Bytes[A] = Bytes[B];
				Bytes[B] = Swap;
			}
			break;
		}
		case 4: // append garbage
		default:
		{
			const int32 Count = RandRange(Stream, 1, 32);
			for (int32 Index = 0; Index < Count; ++Index)
			{
				Bytes.Add(static_cast<uint8>(RandRange(Stream, 0, 255)));
			}
			break;
		}
		}

		// Some byte-level operations can be no-ops (for example swapping equal
		// bytes). Guarantee a real change so the corruption case is meaningful.
		if (Bytes == Original)
		{
			Bytes[RandRange(Stream, 0, Bytes.Num() - 1)] ^= 0x01;
		}
	}

	bool CorruptionCase(FDAGateContext& Context, FDATestReport& Report, FRandomStream& Stream, int32 CaseIndex, int32& InOutMaxSize)
	{
		const FString SlotName = FString::Printf(TEXT("%s_%d"), FuzzCorruptSlot, CaseIndex % 4);
		FString Error;
		Context.Save->DeleteNamedSlot(SlotName, Error);

		GenerateRandomState(Context, Stream);
		const FDASaveSnapshot StateA = CaptureSnapshot(Context);
		if (!Context.Save->SaveNamedSlotWithContext(SlotName, 2, Context.Profile, Context.Calendar, Context.Settings, Error))
		{
			Report.Fail(FString::Printf(TEXT("corruption[%d] could not write state A: %s"), CaseIndex, *Error));
			return false;
		}

		GenerateRandomState(Context, Stream);
		if (!Context.Save->SaveNamedSlotWithContext(SlotName, 2, Context.Profile, Context.Calendar, Context.Settings, Error))
		{
			Report.Fail(FString::Printf(TEXT("corruption[%d] could not write state B: %s"), CaseIndex, *Error));
			return false;
		}

		const int64 FileSize = GetSaveFileSize(SlotName);
		if (FileSize > InOutMaxSize)
		{
			InOutMaxSize = static_cast<int32>(FileSize);
		}

		const FString PrimaryPath = UDASaveSubsystem::GetSaveFilePath(SlotName);
		TArray<uint8> Bytes;
		if (!FFileHelper::LoadFileToArray(Bytes, *PrimaryPath))
		{
			Report.Fail(FString::Printf(TEXT("corruption[%d] could not read primary bytes"), CaseIndex));
			return false;
		}

		const int32 Mode = CaseIndex % 5;
		CorruptBytes(Bytes, Mode, Stream);
		if (!FFileHelper::SaveArrayToFile(Bytes, *PrimaryPath))
		{
			Report.Fail(FString::Printf(TEXT("corruption[%d] could not write corrupted primary"), CaseIndex));
			return false;
		}

		PoisonContext(Context);
		bool bRecovered = false;
		const bool bLoaded = Context.Save->LoadNamedSlotWithContext(
			SlotName, Context.Profile, Context.Calendar, Context.Settings, Error, &bRecovered);
		Report.Quiet(bLoaded, FString::Printf(TEXT("corruption[%d] mode=%s should recover (%s)"),
			CaseIndex, CorruptionModeName(Mode), *Error));
		if (bLoaded)
		{
			Report.Quiet(bRecovered, FString::Printf(TEXT("corruption[%d] mode=%s did not report backup recovery"),
				CaseIndex, CorruptionModeName(Mode)));
			CompareSnapshot(Report, StateA, Context, FString::Printf(TEXT("corruption[%d].recovered"), CaseIndex));
		}

		const FString BackupPath = UDASaveSubsystem::GetSaveFilePath(SlotName + TEXT("_backup"));
		TArray<uint8> BackupBytes;
		if (FFileHelper::LoadFileToArray(BackupBytes, *BackupPath))
		{
			CorruptBytes(BackupBytes, (Mode + 2) % 5, Stream);
			FFileHelper::SaveArrayToFile(BackupBytes, *BackupPath);
		}

		PoisonContext(Context);
		Error.Reset();
		const bool bLoadedBoth = Context.Save->LoadNamedSlotWithContext(
			SlotName, Context.Profile, Context.Calendar, Context.Settings, Error);
		Report.Quiet(!bLoadedBoth, FString::Printf(TEXT("corruption[%d] mode=%s double corruption should be rejected"),
			CaseIndex, CorruptionModeName(Mode)));
		if (!bLoadedBoth)
		{
			Report.Quiet(!Error.IsEmpty(), FString::Printf(TEXT("corruption[%d] rejection has no error text"), CaseIndex));
		}

		const FDASaveSlotInfo Info = Context.Save->GetSlotInfo(SlotName, 2);
		Report.Quiet(Info.bCorrupt, FString::Printf(TEXT("corruption[%d] double corruption not flagged corrupt"), CaseIndex));
		Report.Quiet(IFileManager::Get().FileExists(*PrimaryPath) && IFileManager::Get().FileExists(*BackupPath),
			FString::Printf(TEXT("corruption[%d] failed load deleted a save file"), CaseIndex));

		Context.Save->DeleteNamedSlot(SlotName, Error);
		return true;
	}

	// ------------------------------------------------------------------ migration helpers

	struct FDALegacyCase
	{
		FString Json;
		FString Name;
		FString DormKey;
		FString Title;
		FString Gender;
		FString Period;
		int32 DP = 0;
		int32 Year = 1;
		int32 MonthNumber = 10;
		int32 MonthIndex = 0;
		int32 Day = 7;
		double PlaytimeSeconds = 0.0;
		bool bIncludeVersion = false;
		TMap<FString, bool> ExpectedFlags;
		TMap<FString, int32> ExpectedCounters;
	};

	FDALegacyCase MakeLegacyCase(FRandomStream& Stream, int32 CaseIndex)
	{
		FDALegacyCase Case;
		Case.Name = Stream.RandRange(0, 19) == 0 ? FString() : RandomName(Stream);
		static const TCHAR* const DormKeys[] = { TEXT("Slifer"), TEXT("Ra Yellow"), TEXT("Obelisk Blue"), TEXT("White") };
		Case.DormKey = DormKeys[Stream.RandRange(0, static_cast<int32>(UE_ARRAY_COUNT(DormKeys)) - 1)];
		Case.Title = Stream.RandRange(0, 9) == 0 ? FString() : RandomTitle(Stream);
		Case.Gender = Stream.RandRange(0, 4) == 0 ? FString() : RandomToken(Stream, TEXT(""), 3, 12);
		Case.DP = RandRange(Stream, 0, 1000000000);
		Case.Year = RandRange(Stream, 1, 6);
		Case.MonthNumber = RandRange(Stream, 1, 12);
		Case.MonthIndex = ((Case.MonthNumber - 10) % 12 + 12) % 12;
		Case.Day = RandRange(Stream, 1, 28);
		Case.PlaytimeSeconds = static_cast<double>(RandRange(Stream, 0, 999999)) + 0.125;
		static const TCHAR* const Periods[] = { TEXT("AM"), TEXT("PM"), TEXT("Night") };
		Case.Period = Periods[Stream.RandRange(0, static_cast<int32>(UE_ARRAY_COUNT(Periods)) - 1)];
		Case.bIncludeVersion = CaseIndex % 3 == 0;

		TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
		if (Case.bIncludeVersion)
		{
			Root->SetNumberField(TEXT("version"), 0);
		}
		Root->SetStringField(TEXT("name"), Case.Name);
		Root->SetStringField(TEXT("dorm"), Case.DormKey);
		Root->SetStringField(TEXT("title"), Case.Title);
		if (!Case.Gender.IsEmpty())
		{
			Root->SetStringField(TEXT("gender"), Case.Gender);
		}
		Root->SetNumberField(TEXT("dp"), Case.DP);
		Root->SetNumberField(TEXT("playtime_seconds"), Case.PlaytimeSeconds);
		Root->SetNumberField(TEXT("month"), Case.MonthNumber);
		Root->SetNumberField(TEXT("year"), Case.Year);
		Root->SetNumberField(TEXT("day"), Case.Day);
		Root->SetStringField(TEXT("period"), Case.Period);

		TSharedPtr<FJsonObject> Flags = MakeShared<FJsonObject>();
		const int32 FlagCount = RandRange(Stream, 0, 8);
		for (int32 Index = 0; Index < FlagCount; ++Index)
		{
			const FString Key = FString::Printf(TEXT("legacy_flag_%d"), Index);
			const bool bValue = Stream.RandRange(0, 1) == 1;
			Flags->SetBoolField(Key, bValue);
			if (bValue)
			{
				Case.ExpectedFlags.Add(Key, true);
			}
		}
		Root->SetObjectField(TEXT("flags"), Flags);

		TSharedPtr<FJsonObject> Counters = MakeShared<FJsonObject>();
		static const TCHAR* const LegacyCounters[][2] = {
			{ TEXT("wins"), TEXT("wins_total") },
			{ TEXT("duels"), TEXT("duels_total") },
			{ TEXT("timed"), TEXT("timed_clears") },
			{ TEXT("written"), TEXT("written_correct") },
			{ TEXT("events"), TEXT("story_events_cleared") },
			{ TEXT("cards"), TEXT("cards_owned") }
		};
		for (int32 Index = 0; Index < static_cast<int32>(UE_ARRAY_COUNT(LegacyCounters)); ++Index)
		{
			if (Stream.RandRange(0, 1) == 0)
			{
				const int32 Value = RandRange(Stream, 0, 1000000);
				Counters->SetNumberField(LegacyCounters[Index][0], Value);
				const FString NewName = LegacyCounters[Index][1];
				if (!Case.ExpectedCounters.Contains(NewName))
				{
					Case.ExpectedCounters.Add(NewName, Value);
				}
			}
		}
		const int32 NewCounterCount = RandRange(Stream, 0, 4);
		for (int32 Index = 0; Index < NewCounterCount; ++Index)
		{
			const FString Key = FString::Printf(TEXT("legacy_new_%d"), Index);
			const int32 Value = RandRange(Stream, 0, 1000000);
			Counters->SetNumberField(Key, Value);
			Case.ExpectedCounters.Add(Key, Value);
		}
		const int32 CustomCounterCount = RandRange(Stream, 0, 3);
		for (int32 Index = 0; Index < CustomCounterCount; ++Index)
		{
			const FString Key = FString::Printf(TEXT("legacy_custom_%d"), Index);
			const int32 Value = RandRange(Stream, 0, 1000000);
			Counters->SetNumberField(Key, Value);
			Case.ExpectedCounters.Add(Key, Value);
		}
		Root->SetObjectField(TEXT("counters"), Counters);

		FString Json;
		const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
		FJsonSerializer::Serialize(Root.ToSharedRef(), Writer);
		Case.Json = Json;
		return Case;
	}

	FString ExpectedLegacyName(const FDALegacyCase& Case)
	{
		return Case.Name.IsEmpty() ? FString(TEXT("New Student")) : Case.Name;
	}

	FString ExpectedLegacyTitle(const FDALegacyCase& Case)
	{
		return Case.Title.IsEmpty() ? FString(TEXT("Apprentice Duelist")) : Case.Title;
	}

	FString ExpectedLegacyGender(const FDALegacyCase& Case)
	{
		return Case.Gender.IsEmpty() ? FString(TEXT("unspecified")) : Case.Gender;
	}

	EDADayPeriod LegacyPeriod(const FString& Value)
	{
		if (Value.Equals(TEXT("PM"), ESearchCase::IgnoreCase))
		{
			return EDADayPeriod::PM;
		}
		if (Value.Equals(TEXT("Night"), ESearchCase::IgnoreCase))
		{
			return EDADayPeriod::Night;
		}
		return EDADayPeriod::AM;
	}

	void CheckMigratedLegacyJson(FDAGateContext& Context, FDATestReport& Report, const FDALegacyCase& Case, int32 CaseIndex)
	{
		FString Migrated = Case.Json;
		FString Error;
		if (!Context.Save->MigrateJson(Migrated, 0, Error))
		{
			Report.Fail(FString::Printf(TEXT("migration[%d] MigrateJson failed: %s"), CaseIndex, *Error));
			return;
		}

		Report.Quiet(Context.Save->GetVersionFromJson(Migrated) == UDASaveSubsystem::CurrentVersion,
			FString::Printf(TEXT("migration[%d] version is not %d"), CaseIndex, UDASaveSubsystem::CurrentVersion));

		TSharedPtr<FJsonObject> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Migrated);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			Report.Fail(FString::Printf(TEXT("migration[%d] migrated JSON does not parse"), CaseIndex));
			return;
		}

		const TSharedPtr<FJsonObject>* Profile = nullptr;
		Root->TryGetObjectField(TEXT("profile"), Profile);
		Report.Quiet(Profile && Profile->IsValid(), FString::Printf(TEXT("migration[%d] has no profile object"), CaseIndex));
		if (Profile && Profile->IsValid())
		{
			FString Name;
			FString DormKey;
			FString Title;
			FString Gender;
			int32 DP = 0;
			double Playtime = 0.0;
			(*Profile)->TryGetStringField(TEXT("name"), Name);
			(*Profile)->TryGetStringField(TEXT("dorm"), DormKey);
			(*Profile)->TryGetStringField(TEXT("title"), Title);
			(*Profile)->TryGetStringField(TEXT("gender"), Gender);
			(*Profile)->TryGetNumberField(TEXT("dp"), DP);
			(*Profile)->TryGetNumberField(TEXT("playtime_seconds"), Playtime);

			Report.Quiet(Name.Equals(ExpectedLegacyName(Case), ESearchCase::CaseSensitive),
				FString::Printf(TEXT("migration[%d] name mismatch"), CaseIndex));
			Report.Quiet(DormKey.Equals(Case.DormKey, ESearchCase::CaseSensitive),
				FString::Printf(TEXT("migration[%d] dorm mismatch"), CaseIndex));
			Report.Quiet(Title.Equals(ExpectedLegacyTitle(Case), ESearchCase::CaseSensitive),
				FString::Printf(TEXT("migration[%d] title mismatch"), CaseIndex));
			Report.Quiet(Gender.Equals(ExpectedLegacyGender(Case), ESearchCase::CaseSensitive),
				FString::Printf(TEXT("migration[%d] gender mismatch"), CaseIndex));
			Report.Quiet(DP == Case.DP, FString::Printf(TEXT("migration[%d] dp mismatch"), CaseIndex));
			Report.Quiet(FMath::Abs(Playtime - Case.PlaytimeSeconds) <= 1.0e-6,
				FString::Printf(TEXT("migration[%d] playtime lost fractional precision"), CaseIndex));
		}

		const TSharedPtr<FJsonObject>* Calendar = nullptr;
		Root->TryGetObjectField(TEXT("calendar"), Calendar);
		Report.Quiet(Calendar && Calendar->IsValid(), FString::Printf(TEXT("migration[%d] has no calendar object"), CaseIndex));
		if (Calendar && Calendar->IsValid())
		{
			int32 Year = 0;
			int32 MonthIndex = -1;
			int32 Day = 0;
			FString Period;
			(*Calendar)->TryGetNumberField(TEXT("year"), Year);
			(*Calendar)->TryGetNumberField(TEXT("month_index"), MonthIndex);
			(*Calendar)->TryGetNumberField(TEXT("day"), Day);
			(*Calendar)->TryGetStringField(TEXT("period"), Period);
			Report.Quiet(Year == Case.Year, FString::Printf(TEXT("migration[%d] calendar year mismatch"), CaseIndex));
			Report.Quiet(MonthIndex == Case.MonthIndex, FString::Printf(TEXT("migration[%d] calendar month mismatch"), CaseIndex));
			Report.Quiet(Day == Case.Day, FString::Printf(TEXT("migration[%d] calendar day mismatch"), CaseIndex));
			Report.Quiet(Period.Equals(Case.Period, ESearchCase::IgnoreCase),
				FString::Printf(TEXT("migration[%d] calendar period mismatch"), CaseIndex));
		}

		const TSharedPtr<FJsonObject>* Meta = nullptr;
		Root->TryGetObjectField(TEXT("meta"), Meta);
		Report.Quiet(Meta && Meta->IsValid(), FString::Printf(TEXT("migration[%d] has no meta object"), CaseIndex));
		if (Meta && Meta->IsValid())
		{
			FString MetaName;
			FString MetaPeriod;
			int32 MetaDP = 0;
			int32 MetaYear = 0;
			int32 MetaMonthIndex = -1;
			int32 MetaDay = 0;
			double MetaPlaytime = 0.0;
			(*Meta)->TryGetStringField(TEXT("name"), MetaName);
			(*Meta)->TryGetStringField(TEXT("period"), MetaPeriod);
			(*Meta)->TryGetNumberField(TEXT("dp"), MetaDP);
			(*Meta)->TryGetNumberField(TEXT("year"), MetaYear);
			(*Meta)->TryGetNumberField(TEXT("month_index"), MetaMonthIndex);
			(*Meta)->TryGetNumberField(TEXT("day"), MetaDay);
			(*Meta)->TryGetNumberField(TEXT("playtime_seconds"), MetaPlaytime);
			Report.Quiet(MetaName.Equals(ExpectedLegacyName(Case), ESearchCase::CaseSensitive),
				FString::Printf(TEXT("migration[%d] meta name mismatch"), CaseIndex));
			Report.Quiet(MetaDP == Case.DP, FString::Printf(TEXT("migration[%d] meta dp mismatch"), CaseIndex));
			Report.Quiet(MetaYear == Case.Year, FString::Printf(TEXT("migration[%d] meta year mismatch"), CaseIndex));
			Report.Quiet(MetaMonthIndex == Case.MonthIndex, FString::Printf(TEXT("migration[%d] meta month mismatch"), CaseIndex));
			Report.Quiet(MetaDay == Case.Day, FString::Printf(TEXT("migration[%d] meta day mismatch"), CaseIndex));
			Report.Quiet(MetaPeriod.Equals(Case.Period, ESearchCase::IgnoreCase),
				FString::Printf(TEXT("migration[%d] meta period mismatch"), CaseIndex));
			Report.Quiet(FMath::Abs(MetaPlaytime - Case.PlaytimeSeconds) <= 1.0e-6,
				FString::Printf(TEXT("migration[%d] meta playtime mismatch"), CaseIndex));
		}

		const TSharedPtr<FJsonObject>* Settings = nullptr;
		Root->TryGetObjectField(TEXT("settings"), Settings);
		Report.Quiet(Settings && Settings->IsValid(), FString::Printf(TEXT("migration[%d] has no settings object"), CaseIndex));

		const TSharedPtr<FJsonObject>* Flags = nullptr;
		Root->TryGetObjectField(TEXT("flags"), Flags);
		if (Flags && Flags->IsValid())
		{
			for (const TPair<FString, bool>& Pair : Case.ExpectedFlags)
			{
				bool bValue = false;
				Report.Quiet((*Flags)->TryGetBoolField(Pair.Key, bValue) && bValue,
					FString::Printf(TEXT("migration[%d] flag '%s' lost"), CaseIndex, *Pair.Key));
			}
		}

		const TSharedPtr<FJsonObject>* Counters = nullptr;
		Root->TryGetObjectField(TEXT("counters"), Counters);
		if (Counters && Counters->IsValid())
		{
			for (const TPair<FString, int32>& Pair : Case.ExpectedCounters)
			{
				int32 Value = -1;
				Report.Quiet((*Counters)->TryGetNumberField(Pair.Key, Value) && Value == Pair.Value,
					FString::Printf(TEXT("migration[%d] counter '%s' mismatch"), CaseIndex, *Pair.Key));
			}
		}

		FString Again = Migrated;
		FString IdempotentError;
		if (!Context.Save->MigrateJson(Again, UDASaveSubsystem::CurrentVersion, IdempotentError))
		{
			Report.Fail(FString::Printf(TEXT("migration[%d] second migration failed: %s"), CaseIndex, *IdempotentError));
		}
		else
		{
			Report.Quiet(Again.Equals(Migrated, ESearchCase::CaseSensitive),
				FString::Printf(TEXT("migration[%d] is not idempotent"), CaseIndex));
		}
	}

	void CheckLegacyLoadedState(FDAGateContext& Context, FDATestReport& Report, const FDALegacyCase& Case, int32 CaseIndex)
	{
		const FString Label = FString::Printf(TEXT("migration[%d].loaded"), CaseIndex);
		FDADeepCompare Compare(Report, Label);
		Compare.Str(TEXT("profile.name"), Context.Profile->GetPlayerName(), ExpectedLegacyName(Case));
		Compare.Str(TEXT("profile.title"), Context.Profile->GetTitle(), ExpectedLegacyTitle(Case));
		Compare.Str(TEXT("profile.gender"), Context.Profile->GetGender(), ExpectedLegacyGender(Case));
		Compare.Int(TEXT("profile.dorm"), static_cast<int32>(Context.Profile->GetDorm()),
			static_cast<int32>(DuelAcademyProfile::ParseDorm(Case.DormKey)));
		Compare.Int(TEXT("profile.dp"), Context.Profile->GetDP(), Case.DP);
		Compare.Double(TEXT("profile.playtime"), Context.Profile->GetPlaytimeSeconds(), Case.PlaytimeSeconds, 1.0e-6);
		Compare.Bool(TEXT("profile.initialized"), Context.Profile->IsInitialized(), true);
		Compare.BoolMap(TEXT("flags"), Context.Profile->GetFlags(), Case.ExpectedFlags);
		Compare.IntMap(TEXT("counters"), Context.Profile->GetCounters(), Case.ExpectedCounters);
		Report.Quiet(Context.Profile->GetEmails().Num() == 0,
			FString::Printf(TEXT("%s.emails (expected empty)"), *Label));

		Compare.Int(TEXT("calendar.year"), Context.Calendar->GetYear(), Case.Year);
		Compare.Int(TEXT("calendar.month_index"), Context.Calendar->GetMonthIndex(), Case.MonthIndex);
		Compare.Int(TEXT("calendar.day"), Context.Calendar->GetDay(), Case.Day);
		Compare.Int(TEXT("calendar.period"), static_cast<int32>(Context.Calendar->GetPeriod()),
			static_cast<int32>(LegacyPeriod(Case.Period)));
		Compare.Int(TEXT("calendar.weekday"), static_cast<int32>(Context.Calendar->GetWeekday()),
			static_cast<int32>(Context.Calendar->GetWeekdayForDate(Case.Year, Case.MonthIndex, Case.Day)));
	}

	void CheckDefaultSettings(FDAGateContext& Context, FDATestReport& Report, int32 CaseIndex)
	{
		const FString Label = FString::Printf(TEXT("migration[%d].settings"), CaseIndex);
		FDADeepCompare Compare(Report, Label);
		Compare.Int(TEXT("animation_speed"), static_cast<int32>(Context.Settings->GetAnimationSpeed()), static_cast<int32>(EDAAnimationSpeed::Normal));
		Compare.Bool(TEXT("confirm_activation"), Context.Settings->GetConfirmActivation(), true);
		Compare.Int(TEXT("text_speed"), static_cast<int32>(Context.Settings->GetTextSpeed()), static_cast<int32>(EDATextSpeed::Normal));
		Compare.Double(TEXT("bgm_volume"), Context.Settings->GetBgmVolume(), 0.8, 1.0e-6);
		Compare.Double(TEXT("sfx_volume"), Context.Settings->GetSfxVolume(), 0.8, 1.0e-6);
		Compare.Bool(TEXT("subtitles"), Context.Settings->GetSubtitles(), true);
		Compare.Str(TEXT("language"), Context.Settings->GetLanguageKey(), TEXT("en"));
		Compare.Str(TEXT("control.interact"), Context.Settings->GetControl(TEXT("Interact")), TEXT("E"));
	}

	bool MigrationCase(FDAGateContext& Context, FDATestReport& Report, FRandomStream& Stream, int32 CaseIndex)
	{
		const FDALegacyCase Case = MakeLegacyCase(Stream, CaseIndex);
		CheckMigratedLegacyJson(Context, Report, Case, CaseIndex);

		// Alternate wrapper versions. A payload that explicitly says version 0
		// must migrate even when the wrapper was written as version 1 (the
		// v0-JSON/v1-wrapper regression). Missing version information with a
		// version-1 wrapper is ambiguous and must be rejected cleanly.
		const int32 WrapperVersion = CaseIndex % 2;
		const bool bRawShouldLoad = Case.bIncludeVersion || WrapperVersion == 0;

		FString Error;
		if (!WriteRawSaveFile(Context, FuzzMigrationSlot, Case.Json, WrapperVersion, Error))
		{
			Report.Fail(FString::Printf(TEXT("migration[%d] raw file write failed: %s"), CaseIndex, *Error));
			return false;
		}

		PoisonContext(Context);
		bool bRecovered = true;
		const bool bLoaded = Context.Save->LoadNamedSlotWithContext(
			FuzzMigrationSlot, Context.Profile, Context.Calendar, Context.Settings, Error, &bRecovered);
		if (bRawShouldLoad)
		{
			Report.Quiet(bLoaded, FString::Printf(TEXT("migration[%d] raw v0 file load failed: %s"), CaseIndex, *Error));
			if (bLoaded)
			{
				Report.Quiet(!bRecovered, FString::Printf(TEXT("migration[%d] raw v0 load used backup"), CaseIndex));
				CheckLegacyLoadedState(Context, Report, Case, CaseIndex);
				CheckDefaultSettings(Context, Report, CaseIndex);

				const FDASaveSlotInfo Info = Context.Save->GetSlotInfo(FuzzMigrationSlot, 2);
				Report.Quiet(Info.Version == UDASaveSubsystem::CurrentVersion,
					FString::Printf(TEXT("migration[%d] slot metadata version mismatch"), CaseIndex));
				Report.Quiet(Info.PlayerName.Equals(ExpectedLegacyName(Case), ESearchCase::CaseSensitive),
					FString::Printf(TEXT("migration[%d] slot metadata name mismatch"), CaseIndex));
				Report.Quiet(FMath::Abs(Info.PlaytimeSeconds - Case.PlaytimeSeconds) <= 1.0e-6,
					FString::Printf(TEXT("migration[%d] slot metadata playtime mismatch"), CaseIndex));
				Report.Quiet(Info.Year == Case.Year && Info.MonthIndex == Case.MonthIndex && Info.Day == Case.Day,
					FString::Printf(TEXT("migration[%d] slot metadata date mismatch"), CaseIndex));
			}
		}
		else
		{
			Report.Quiet(!bLoaded, FString::Printf(TEXT("migration[%d] version-less v0 file should be rejected"), CaseIndex));
			Report.Quiet(!Error.IsEmpty(), FString::Printf(TEXT("migration[%d] rejection has no error text"), CaseIndex));
		}

		Context.Save->DeleteNamedSlot(FuzzMigrationSlot, Error);

		FString FutureJson = TEXT("{\"version\":99,\"profile\":{\"name\":\"Future\"}}");
		FString FutureError;
		Report.Quiet(!Context.Save->MigrateJson(FutureJson, 99, FutureError),
			FString::Printf(TEXT("migration[%d] future version was accepted"), CaseIndex));
		FString InvalidJson = TEXT("{not json");
		Report.Quiet(!Context.Save->MigrateJson(InvalidJson, 0, FutureError),
			FString::Printf(TEXT("migration[%d] invalid JSON was accepted"), CaseIndex));

		// Periodically exercise the file-level future-version rejection too.
		if (CaseIndex % 7 == 0)
		{
			if (WriteRawSaveFile(Context, FuzzMigrationSlot, FutureJson, UDASaveSubsystem::CurrentVersion, Error))
			{
				PoisonContext(Context);
				Error.Reset();
				const bool bFutureLoaded = Context.Save->LoadNamedSlotWithContext(
					FuzzMigrationSlot, Context.Profile, Context.Calendar, Context.Settings, Error);
				Report.Quiet(!bFutureLoaded, FString::Printf(TEXT("migration[%d] future payload file was accepted"), CaseIndex));
				Report.Quiet(!Error.IsEmpty(), FString::Printf(TEXT("migration[%d] future payload rejection has no error"), CaseIndex));
			}
			Context.Save->DeleteNamedSlot(FuzzMigrationSlot, Error);
		}
		return true;
	}

	// ------------------------------------------------------------------ fuzz driver

	void LogBatch(FDATestReport& Report, const TCHAR* Phase, int32 BatchIndex, int32 BatchCount, int32 Items, int32 FailuresBefore)
	{
		const int32 BatchFailures = Report.Failures - FailuresBefore;
		if (BatchFailures == 0)
		{
			UE_LOG(LogDuelAcademyIsland, Log,
				TEXT("[PASS] DASaveFuzz %s batch %d/%d: %d case(s), 0 failure(s)"),
				Phase, BatchIndex + 1, BatchCount, Items);
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Error,
				TEXT("[FAIL] DASaveFuzz %s batch %d/%d: %d case(s), %d failure(s)"),
				Phase, BatchIndex + 1, BatchCount, Items, BatchFailures);
		}
	}

	bool RunSaveFuzz(int32 RequestedCount, int32 Seed)
	{
		const int32 Count = FMath::Clamp(RequestedCount, 1, MaxSaveFuzzCount);
		const int32 CorruptionCases = FMath::Max(100, Count / 10);
		const int32 MigrationCases = FMath::Max(50, Count / 50);

		UE_LOG(LogDuelAcademyIsland, Display,
			TEXT("=== DASaveFuzz: %d states, %d corruption cases, %d migration cases, seed 0x%08X ==="),
			Count, CorruptionCases, MigrationCases, static_cast<uint32>(Seed));

		FDATestReport Report;
		FDAGateContext Context;
		FRandomStream Stream(Seed);
		int32 MaxSaveSize = 0;

		Report.Check(UDASaveSubsystem::NumSlots == 4, TEXT("DASaveFuzz: four save slots are declared"));
		Report.Check(UDASaveSubsystem::AutosaveSlotIndex == 0, TEXT("DASaveFuzz: slot 0 is the autosave"));
		Report.Check(UDASaveSubsystem::IsValidSlotIndex(0) && UDASaveSubsystem::IsValidSlotIndex(3),
			TEXT("DASaveFuzz: slots 0..3 are valid"));
		Report.Check(!UDASaveSubsystem::IsValidSlotIndex(-1) && !UDASaveSubsystem::IsValidSlotIndex(4),
			TEXT("DASaveFuzz: out-of-range slots are rejected"));
		Report.Check(Context.Calendar->LoadCalendarData(), TEXT("DASaveFuzz: calendar.json loads"));

		FString Error;
		for (int32 Slot = 0; Slot < UDASaveSubsystem::NumSlots; ++Slot)
		{
			Context.Save->DeleteNamedSlot(FuzzSlotNameForIndex(Slot), Error);
		}
		for (int32 Slot = 0; Slot < 4; ++Slot)
		{
			Context.Save->DeleteNamedSlot(FString::Printf(TEXT("%s_%d"), FuzzCorruptSlot, Slot), Error);
		}
		Context.Save->DeleteNamedSlot(FuzzMigrationSlot, Error);

		const int32 RoundTripBatches = FMath::Clamp((Count + 999) / 1000, 1, 10);
		for (int32 Batch = 0; Batch < RoundTripBatches; ++Batch)
		{
			const int32 Start = static_cast<int32>((static_cast<int64>(Batch) * Count) / RoundTripBatches);
			const int32 End = static_cast<int32>((static_cast<int64>(Batch + 1) * Count) / RoundTripBatches);
			const int32 FailuresBefore = Report.Failures;
			for (int32 Iteration = Start; Iteration < End; ++Iteration)
			{
				SaveRoundTripCase(Context, Report, Stream, Iteration, MaxSaveSize);
			}
			LogBatch(Report, TEXT("roundtrip"), Batch, RoundTripBatches, End - Start, FailuresBefore);
		}

		const int32 CorruptionBatches = FMath::Clamp((CorruptionCases + 99) / 100, 1, 10);
		for (int32 Batch = 0; Batch < CorruptionBatches; ++Batch)
		{
			const int32 Start = static_cast<int32>((static_cast<int64>(Batch) * CorruptionCases) / CorruptionBatches);
			const int32 End = static_cast<int32>((static_cast<int64>(Batch + 1) * CorruptionCases) / CorruptionBatches);
			const int32 FailuresBefore = Report.Failures;
			for (int32 CaseIndex = Start; CaseIndex < End; ++CaseIndex)
			{
				CorruptionCase(Context, Report, Stream, CaseIndex, MaxSaveSize);
			}
			LogBatch(Report, TEXT("corruption"), Batch, CorruptionBatches, End - Start, FailuresBefore);
		}

		const int32 MigrationBatches = FMath::Clamp((MigrationCases + 99) / 100, 1, 10);
		for (int32 Batch = 0; Batch < MigrationBatches; ++Batch)
		{
			const int32 Start = static_cast<int32>((static_cast<int64>(Batch) * MigrationCases) / MigrationBatches);
			const int32 End = static_cast<int32>((static_cast<int64>(Batch + 1) * MigrationCases) / MigrationBatches);
			const int32 FailuresBefore = Report.Failures;
			for (int32 CaseIndex = Start; CaseIndex < End; ++CaseIndex)
			{
				MigrationCase(Context, Report, Stream, CaseIndex);
			}
			LogBatch(Report, TEXT("migration"), Batch, MigrationBatches, End - Start, FailuresBefore);
		}

		for (int32 Slot = 0; Slot < UDASaveSubsystem::NumSlots; ++Slot)
		{
			Context.Save->DeleteNamedSlot(FuzzSlotNameForIndex(Slot), Error);
		}
		for (int32 Slot = 0; Slot < 4; ++Slot)
		{
			Context.Save->DeleteNamedSlot(FString::Printf(TEXT("%s_%d"), FuzzCorruptSlot, Slot), Error);
		}
		Context.Save->DeleteNamedSlot(FuzzMigrationSlot, Error);

		UE_LOG(LogDuelAcademyIsland, Display,
			TEXT("=== DASaveFuzz summary: %d states, %d corruption cases, %d migration cases, %d checks, %d failure(s), seed 0x%08X, max save size %d bytes ==="),
			Count, CorruptionCases, MigrationCases, Report.Checks, Report.Failures,
			static_cast<uint32>(Seed), MaxSaveSize);

		if (Report.Failures > 0)
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("DASaveFuzz FAILED."));
			return false;
		}
		UE_LOG(LogDuelAcademyIsland, Display, TEXT("DASaveFuzz PASSED."));
		return true;
	}

	// ------------------------------------------------------------------ 12-month simulation

	FString MonthName(int32 MonthIndex)
	{
		static const TCHAR* const Names[12] = {
			TEXT("October"), TEXT("November"), TEXT("December"),
			TEXT("January"), TEXT("February"), TEXT("March"),
			TEXT("April"), TEXT("May"), TEXT("June"),
			TEXT("July"), TEXT("August"), TEXT("September")
		};
		return Names[FMath::Clamp(MonthIndex, 0, 11)];
	}

	bool SaveAndReloadTwelveMonth(FDAGateContext& Context, FDATestReport& Report, const FString& Label,
		int32& InOutSaves, int32& InOutLoads, int32& InOutMaxSize)
	{
		const FDASaveSnapshot Expected = CaptureSnapshot(Context);
		FString Error;
		if (!Context.Save->SaveNamedSlotWithContext(
			TwelveMonthSlot, 1, Context.Profile, Context.Calendar, Context.Settings, Error))
		{
			Report.Fail(FString::Printf(TEXT("%s save failed: %s"), *Label, *Error));
			return false;
		}
		++InOutSaves;

		const int64 FileSize = GetSaveFileSize(TwelveMonthSlot);
		if (FileSize > InOutMaxSize)
		{
			InOutMaxSize = static_cast<int32>(FileSize);
		}

		PoisonContext(Context);
		bool bRecovered = true;
		if (!Context.Save->LoadNamedSlotWithContext(
			TwelveMonthSlot, Context.Profile, Context.Calendar, Context.Settings, Error, &bRecovered))
		{
			Report.Fail(FString::Printf(TEXT("%s load failed: %s"), *Label, *Error));
			return false;
		}
		++InOutLoads;
		Report.Quiet(!bRecovered, FString::Printf(TEXT("%s clean load used the backup"), *Label));
		CompareSnapshot(Report, Expected, Context, Label);
		return true;
	}

	void AdvanceToNextDayAndCheck(FDAGateContext& Context, FDATestReport& Report,
		int32& InOutYear, int32& InOutMonthIndex, int32& InOutDay, int32& InOutAbsoluteDay)
	{
		const int32 ExpectedYear = InOutYear;
		const int32 ExpectedMonthIndex = InOutMonthIndex;
		const int32 ExpectedDay = InOutDay;
		const int32 DaysInMonth = Context.Calendar->GetDaysInMonth(ExpectedYear, ExpectedMonthIndex);

		int32 NextYear = ExpectedYear;
		int32 NextMonthIndex = ExpectedMonthIndex;
		int32 NextDay = ExpectedDay + 1;
		if (NextDay > DaysInMonth)
		{
			NextDay = 1;
			++NextMonthIndex;
			if (NextMonthIndex > 11)
			{
				NextMonthIndex = 0;
				++NextYear;
			}
		}

		Context.Calendar->AdvanceDay();
		++InOutAbsoluteDay;
		InOutYear = Context.Calendar->GetYear();
		InOutMonthIndex = Context.Calendar->GetMonthIndex();
		InOutDay = Context.Calendar->GetDay();

		Report.Quiet(InOutYear == NextYear, FString::Printf(TEXT("date rollover year (expected %d, got %d)"), NextYear, InOutYear));
		Report.Quiet(InOutMonthIndex == NextMonthIndex, FString::Printf(TEXT("date rollover month (expected %d, got %d)"), NextMonthIndex, InOutMonthIndex));
		Report.Quiet(InOutDay == NextDay, FString::Printf(TEXT("date rollover day (expected %d, got %d)"), NextDay, InOutDay));
		Report.Quiet(Context.Calendar->GetAbsoluteDay() == InOutAbsoluteDay,
			FString::Printf(TEXT("absolute day did not advance by one (expected %d, got %d)"), InOutAbsoluteDay, Context.Calendar->GetAbsoluteDay()));
		Report.Quiet(Context.Calendar->GetWeekday() == Context.Calendar->GetWeekdayForDate(InOutYear, InOutMonthIndex, InOutDay),
			TEXT("weekday does not match the computed weekday"));
	}

	bool RunTwelveMonthTest()
	{
		UE_LOG(LogDuelAcademyIsland, Display, TEXT("=== DATwelveMonthTest: 12 school months day by day (seed 0x%08X) ==="),
			static_cast<uint32>(DefaultTwelveMonthSeed));

		FDATestReport Report;
		FDAGateContext Context;
		FRandomStream Stream(DefaultTwelveMonthSeed);
		FString Error;

		Report.Check(Context.Calendar->LoadCalendarData(), TEXT("DATwelveMonthTest: calendar.json loads"));
		Context.Save->DeleteNamedSlot(TwelveMonthSlot, Error);

		// New game with a non-empty inventory/deck provider state so save/load
		// exercises the provider sections as well as the core profile.
		Context.Profile->InitializeNewGame(TEXT("Calendar Twelve Month"));
		Context.Calendar->SetDate(1, 0, 7, EDADayPeriod::AM);
		Context.Settings->ResetToDefaults();

		FDAEInventorySaveData Inventory;
		Inventory.Version = 1;
		Inventory.MaxOwnedCopies = 99;
		Inventory.Counts.Add(1, 2);
		Inventory.Counts.Add(2, 1);
		const bool bInventorySeeded = Context.Inventory->ApplySaveData(Inventory, Error);
		Report.Check(bInventorySeeded,
			FString::Printf(TEXT("DATwelveMonthTest: inventory seed (%s)"), *Error));

		FDAEDeckSaveData Decks;
		Decks.Version = 1;
		FDAEDeck Starter;
		Starter.Id = TEXT("twelve_month_deck");
		Starter.Name = TEXT("Twelve Month Deck");
		Starter.bPlayerDeck = true;
		Starter.Main.Add(1);
		Starter.Main.Add(2);
		Decks.Decks.Add(Starter);
		Decks.ActiveDeckId = Starter.Id;
		const bool bDecksSeeded = Context.Decks->ApplySaveData(Decks, Error);
		Report.Check(bDecksSeeded,
			FString::Printf(TEXT("DATwelveMonthTest: deck seed (%s)"), *Error));

		int32 Year = Context.Calendar->GetYear();
		int32 MonthIndex = Context.Calendar->GetMonthIndex();
		int32 Day = Context.Calendar->GetDay();
		int32 AbsoluteDay = Context.Calendar->GetAbsoluteDay();

		Report.Check(Year == 1 && MonthIndex == 0 && Day == 7 && Context.Calendar->GetPeriod() == EDADayPeriod::AM,
			TEXT("DATwelveMonthTest: starts Saturday, October 7, Year 1, AM"));
		Report.Check(Context.Calendar->GetWeekday() == EDADayOfWeek::Saturday,
			TEXT("DATwelveMonthTest: start weekday is Saturday"));
		Report.Check(Context.Calendar->GetMonthName(0) == TEXT("October")
			&& Context.Calendar->GetMonthShortName(0) == TEXT("Oct"),
			TEXT("DATwelveMonthTest: October month names"));

		const int32 StartAbsoluteDay = AbsoluteDay;
		TSet<int32> SeenAbsoluteDays;
		TSet<int32> SeenMonths;
		SeenMonths.Add(MonthIndex);
		int32 MonthBoundaries = 0;
		int32 DuplicateDayCount = 0;
		int32 SkippedMonthCount = 0;
		int32 NegativeCounterCount = 0;
		int32 Saves = 0;
		int32 Loads = 0;
		int32 MaxSaveSize = 0;
		int32 ExamDaysSeen = 0;
		int32 RandomSaveDays = 0;
		int32 DaysSimulated = 0;
		bool bAborted = false;

		// Seed the first month's story marker.
		Context.Profile->SetFlag(TEXT("story_month_0_reached"), true);

		UE_LOG(LogDuelAcademyIsland, Display,
			TEXT("[CHECKPOINT] Month 1/12 %s Year %d: days 1..%d, exam day %d, start day %d, DP %d"),
			*MonthName(MonthIndex), Year, Context.Calendar->GetDaysInMonth(Year, MonthIndex),
			Context.Calendar->GetExamDay(Year, MonthIndex), Day, Context.Profile->GetDP());

		for (int32 DayIndex = 0; DayIndex < 365 && !bAborted; ++DayIndex)
		{
			++DaysSimulated;
			const int32 CurrentYear = Context.Calendar->GetYear();
			const int32 CurrentMonth = Context.Calendar->GetMonthIndex();
			const int32 CurrentDay = Context.Calendar->GetDay();
			const int32 CurrentAbsolute = Context.Calendar->GetAbsoluteDay();
			const int32 DaysInMonth = Context.Calendar->GetDaysInMonth(CurrentYear, CurrentMonth);

			Report.Quiet(CurrentDay >= 1 && CurrentDay <= DaysInMonth,
				FString::Printf(TEXT("day %d is outside %s"), CurrentDay, *MonthName(CurrentMonth)));
			Report.Quiet(Context.Calendar->GetWeekday() == Context.Calendar->GetWeekdayForDate(CurrentYear, CurrentMonth, CurrentDay),
				TEXT("weekday does not match the computed date"));
			Report.Quiet(Context.Calendar->GetMonthNumber() == ((CurrentMonth + 9) % 12) + 1,
				TEXT("month number does not match month index"));
			Report.Quiet(CurrentAbsolute == StartAbsoluteDay + DayIndex,
				FString::Printf(TEXT("absolute day drift (expected %d, got %d)"), StartAbsoluteDay + DayIndex, CurrentAbsolute));

			if (SeenAbsoluteDays.Contains(CurrentAbsolute))
			{
				++DuplicateDayCount;
				Report.Fail(FString::Printf(TEXT("duplicate absolute day %d at day index %d"), CurrentAbsolute, DayIndex));
			}
			else
			{
				SeenAbsoluteDays.Add(CurrentAbsolute);
			}
			SeenMonths.Add(CurrentMonth);

			// Period rollover: AM -> PM -> Night -> next day AM.
			Report.Quiet(Context.Calendar->GetPeriod() == EDADayPeriod::AM, TEXT("day did not start in AM"));
			Report.Quiet(Context.Calendar->GetHour() == Context.Calendar->GetPeriodStartHour(EDADayPeriod::AM),
				TEXT("AM hour does not match period_hours"));
			Context.Calendar->AdvancePeriod();
			Report.Quiet(Context.Calendar->GetPeriod() == EDADayPeriod::PM, TEXT("AM did not advance to PM"));
			Report.Quiet(Context.Calendar->GetHour() == Context.Calendar->GetPeriodStartHour(EDADayPeriod::PM),
				TEXT("PM hour does not match period_hours"));
			Context.Calendar->AdvancePeriod();
			Report.Quiet(Context.Calendar->GetPeriod() == EDADayPeriod::Night, TEXT("PM did not advance to Night"));
			Report.Quiet(Context.Calendar->GetHour() == Context.Calendar->GetPeriodStartHour(EDADayPeriod::Night),
				TEXT("Night hour does not match period_hours"));

			// Daily progression and story markers.
			Context.Profile->AwardDP(7);
			if (DayIndex % 5 == 0)
			{
				Context.Profile->SpendDP(2);
			}
			Context.Profile->IncrementCounter(TEXT("days_simulated"), 1);

			if (CurrentDay == 15)
			{
				Context.Profile->SetFlag(FString::Printf(TEXT("birthday_%d"), CurrentMonth), true);
			}

			const bool bExamDay = Context.Calendar->IsExamDay();
			if (bExamDay)
			{
				++ExamDaysSeen;
				Context.Profile->SetFlag(FString::Printf(TEXT("exam_seen_%d_%d"), CurrentYear, CurrentMonth), true);
				Context.Profile->IncrementCounter(TEXT("exams_seen"), 1);
				Report.Quiet(Context.Calendar->GetWeekdayForDate(CurrentYear, CurrentMonth, CurrentDay) == Context.Calendar->GetExamWeekday(),
					FString::Printf(TEXT("exam day in %s is not a %s"), *MonthName(CurrentMonth),
						*Context.Calendar->GetWeekdayName(Context.Calendar->GetExamWeekday())));
			}
			else
			{
				Report.Quiet(!Context.Calendar->IsExamDayFor(CurrentYear, CurrentMonth, CurrentDay),
					FString::Printf(TEXT("non-exam day %d incorrectly reports as exam day"), CurrentDay));
			}

			for (const TPair<FString, int32>& Pair : Context.Profile->GetCounters())
			{
				if (Pair.Value < 0)
				{
					++NegativeCounterCount;
					Report.Fail(FString::Printf(TEXT("negative counter %s = %d"), *Pair.Key, Pair.Value));
				}
			}
			Report.Quiet(Context.Profile->GetDP() >= 0, TEXT("negative DP"));
			Report.Quiet(Context.Profile->GetPlaytimeSeconds() >= 0.0, TEXT("negative playtime"));

			const bool bMonthBoundary = CurrentDay == DaysInMonth;
			const bool bRandomSaveDay = Stream.RandRange(1, 100) <= 3;
			if (bExamDay || bMonthBoundary || bRandomSaveDay)
			{
				if (bRandomSaveDay && !bExamDay && !bMonthBoundary)
				{
					++RandomSaveDays;
				}
				if (!SaveAndReloadTwelveMonth(Context, Report,
					FString::Printf(TEXT("twelve[%s %d Year %d %s]"), *MonthName(CurrentMonth), CurrentDay, CurrentYear,
						*Context.Calendar->GetPeriodName(Context.Calendar->GetPeriod())),
					Saves, Loads, MaxSaveSize))
				{
					bAborted = true;
					break;
				}
			}

			const int32 BeforeAdvanceMonth = Context.Calendar->GetMonthIndex();
			const int32 BeforeAdvanceYear = Context.Calendar->GetYear();
			AdvanceToNextDayAndCheck(Context, Report, Year, MonthIndex, Day, AbsoluteDay);

			if (Context.Calendar->GetMonthIndex() != BeforeAdvanceMonth || Context.Calendar->GetYear() != BeforeAdvanceYear)
			{
				++MonthBoundaries;
				if (Context.Calendar->GetMonthIndex() != ((BeforeAdvanceMonth + 1) % 12))
				{
					++SkippedMonthCount;
					Report.Fail(FString::Printf(TEXT("month skip after %s: %d -> %d"),
						*MonthName(BeforeAdvanceMonth), BeforeAdvanceMonth, Context.Calendar->GetMonthIndex()));
				}
				Context.Profile->SetFlag(FString::Printf(TEXT("story_month_%d_reached"), Context.Calendar->GetMonthIndex()), true);

				const int32 EnteredMonth = Context.Calendar->GetMonthIndex();
				if (EnteredMonth <= 11 && MonthBoundaries <= 11)
				{
					UE_LOG(LogDuelAcademyIsland, Display,
						TEXT("[CHECKPOINT] Month %d/12 %s Year %d: days 1..%d, exam day %d, DP %d, counters %d, flags %d"),
						MonthBoundaries + 1, *MonthName(EnteredMonth), Context.Calendar->GetYear(),
						Context.Calendar->GetDaysInMonth(Context.Calendar->GetYear(), EnteredMonth),
						Context.Calendar->GetExamDay(Context.Calendar->GetYear(), EnteredMonth),
						Context.Profile->GetDP(), Context.Profile->GetCounters().Num(), Context.Profile->GetFlags().Num());
				}

				if (!SaveAndReloadTwelveMonth(Context, Report,
					FString::Printf(TEXT("twelve.boundary[%s Year %d]"), *MonthName(Context.Calendar->GetMonthIndex()), Context.Calendar->GetYear()),
					Saves, Loads, MaxSaveSize))
				{
					bAborted = true;
					break;
				}
			}
		}

		if (!bAborted)
		{
			Report.Check(Year == 2 && MonthIndex == 0 && Day == 7,
				FString::Printf(TEXT("DATwelveMonthTest: ended on October 7, Year 2 (got %s %d Year %d)"),
					*MonthName(MonthIndex), Day, Year));
			Report.Check(AbsoluteDay == StartAbsoluteDay + 365,
				FString::Printf(TEXT("DATwelveMonthTest: 365 absolute days advanced (expected %d, got %d)"),
					StartAbsoluteDay + 365, AbsoluteDay));

			Report.Check(MonthBoundaries == 12, FString::Printf(TEXT("DATwelveMonthTest: 12 month boundaries (got %d)"), MonthBoundaries));
			Report.Check(SkippedMonthCount == 0, FString::Printf(TEXT("DATwelveMonthTest: no skipped month (got %d)"), SkippedMonthCount));
			Report.Check(DuplicateDayCount == 0, FString::Printf(TEXT("DATwelveMonthTest: no duplicate day (got %d)"), DuplicateDayCount));
			Report.Check(NegativeCounterCount == 0, FString::Printf(TEXT("DATwelveMonthTest: no negative counter (got %d)"), NegativeCounterCount));
			Report.Check(SeenMonths.Num() == 12, FString::Printf(TEXT("DATwelveMonthTest: all 12 month indices visited (got %d)"), SeenMonths.Num()));

			int32 ExpectedExamDays = 0;
			for (int32 Month = 0; Month < 12; ++Month)
			{
				const int32 ExamDay = Context.Calendar->GetExamDay(1, Month);
				if (ExamDay >= (Month == 0 ? 7 : 1))
				{
					++ExpectedExamDays;
				}
			}
			// The simulation also covers October 1..6 of Year 2.
			if (Context.Calendar->GetExamDay(2, 0) <= 6)
			{
				++ExpectedExamDays;
			}
			Report.Check(ExamDaysSeen == ExpectedExamDays,
				FString::Printf(TEXT("DATwelveMonthTest: observed %d exam days (expected %d)"), ExamDaysSeen, ExpectedExamDays));

			for (int32 Month = 0; Month < 12; ++Month)
			{
				Report.Quiet(Context.Calendar->GetMonthName(Month) == MonthName(Month),
					FString::Printf(TEXT("month name mismatch for month %d"), Month));
				Report.Quiet(Context.Calendar->GetMonthShortName(Month).Len() == 3,
					FString::Printf(TEXT("month short name length mismatch for month %d"), Month));
				Report.Quiet(Context.Profile->GetFlag(FString::Printf(TEXT("story_month_%d_reached"), Month)),
					FString::Printf(TEXT("story flag for month %d was lost"), Month));
				Report.Quiet(Context.Profile->GetFlag(FString::Printf(TEXT("birthday_%d"), Month)),
					FString::Printf(TEXT("birthday marker for month %d was lost"), Month));

				const int32 ExamDay = Context.Calendar->GetExamDay(1, Month);
				if (ExamDay >= (Month == 0 ? 7 : 1))
				{
					Report.Quiet(Context.Profile->GetFlag(FString::Printf(TEXT("exam_seen_1_%d"), Month)),
						FString::Printf(TEXT("exam flag for month %d was lost"), Month));
				}
				Report.Quiet(ExamDay >= 1 && ExamDay <= Context.Calendar->GetDaysInMonth(1, Month),
					FString::Printf(TEXT("exam day out of range for month %d"), Month));
				Report.Quiet(Context.Calendar->GetWeekdayForDate(1, Month, ExamDay) == Context.Calendar->GetExamWeekday(),
					FString::Printf(TEXT("exam day is not the configured weekday for month %d"), Month));

				int32 NextExamYear = 0;
				int32 NextExamMonth = 0;
				int32 NextExamDay = 0;
				Context.Calendar->SetDate(1, Month, 1, EDADayPeriod::AM);
				Report.Quiet(Context.Calendar->GetNextExamDate(NextExamYear, NextExamMonth, NextExamDay),
					FString::Printf(TEXT("GetNextExamDate failed for month %d"), Month));
				Report.Quiet(NextExamYear == 1 && NextExamMonth == Month && NextExamDay == ExamDay,
					FString::Printf(TEXT("GetNextExamDate mismatch for month %d"), Month));
			}

			// Leap-year probe: school year 3 maps January..September to calendar
			// year 4, so February has 29 days.
			Report.Check(Context.Calendar->GetDaysInMonth(1, 4) == 28, TEXT("DATwelveMonthTest: Year 1 February has 28 days"));
			Report.Check(Context.Calendar->GetDaysInMonth(3, 4) == 29, TEXT("DATwelveMonthTest: Year 3 February has 29 days"));
			Context.Calendar->SetDate(3, 4, 1, EDADayPeriod::AM);
			int32 LeapYear = 3;
			int32 LeapMonth = 4;
			int32 LeapDay = 1;
			int32 LeapAbsolute = Context.Calendar->GetAbsoluteDay();
			for (int32 LeapIndex = 0; LeapIndex < 28; ++LeapIndex)
			{
				AdvanceToNextDayAndCheck(Context, Report, LeapYear, LeapMonth, LeapDay, LeapAbsolute);
			}
			Report.Check(LeapYear == 3 && LeapMonth == 4 && LeapDay == 29,
				FString::Printf(TEXT("DATwelveMonthTest: leap February reached day 29 (got %s %d)"),
					*MonthName(LeapMonth), LeapDay));
			AdvanceToNextDayAndCheck(Context, Report, LeapYear, LeapMonth, LeapDay, LeapAbsolute);
			Report.Check(LeapYear == 3 && LeapMonth == 5 && LeapDay == 1,
				FString::Printf(TEXT("DATwelveMonthTest: leap February rolls to March 1 (got %s %d)"),
					*MonthName(LeapMonth), LeapDay));

			// Overflow probes: DP/counters clamp at INT_MAX and never wrap negative.
			Context.Profile->AwardDP(TNumericLimits<int32>::Max());
			Report.Quiet(Context.Profile->GetDP() == TNumericLimits<int32>::Max(),
				TEXT("DATwelveMonthTest: DP overflow did not clamp to INT_MAX"));
			Context.Profile->IncrementCounter(TEXT("overflow_probe"), TNumericLimits<int32>::Max());
			Context.Profile->IncrementCounter(TEXT("overflow_probe"), 1);
			Report.Quiet(Context.Profile->GetCounter(TEXT("overflow_probe")) == TNumericLimits<int32>::Max(),
				TEXT("DATwelveMonthTest: counter overflow did not clamp to INT_MAX"));
		}

		Context.Save->DeleteNamedSlot(TwelveMonthSlot, Error);

		UE_LOG(LogDuelAcademyIsland, Display,
			TEXT("=== DATwelveMonthTest summary: %d days, %d months, %d saves, %d loads, %d random save days, %d exam days, %d checks, %d failure(s), max save size %d bytes ==="),
			DaysSimulated, SeenMonths.Num(), Saves, Loads, RandomSaveDays, ExamDaysSeen,
			Report.Checks, Report.Failures, MaxSaveSize);

		if (bAborted || Report.Failures > 0)
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("DATwelveMonthTest FAILED."));
			return false;
		}
		UE_LOG(LogDuelAcademyIsland, Display, TEXT("DATwelveMonthTest PASSED."));
		return true;
	}

	// ------------------------------------------------------------------ bootstrap

	bool ParseFuzzCount(int32& OutCount)
	{
		FString Value;
		if (FParse::Value(FCommandLine::Get(), TEXT("DASaveFuzz="), Value))
		{
			OutCount = FCString::Atoi(*Value);
			if (OutCount <= 0)
			{
				OutCount = DefaultSaveFuzzCount;
			}
			return true;
		}
		if (FParse::Param(FCommandLine::Get(), TEXT("DASaveFuzz")))
		{
			OutCount = DefaultSaveFuzzCount;
			return true;
		}
		return false;
	}

	int32 ParseFuzzSeed()
	{
		FString Value;
		if (FParse::Value(FCommandLine::Get(), TEXT("DASaveFuzzSeed="), Value))
		{
			return FCString::Atoi(*Value);
		}
		return DefaultSaveFuzzSeed;
	}

	void RunConsoleSaveFuzz(const TArray<FString>& Args, UWorld* World)
	{
		(void)World;
		const int32 Count = Args.Num() > 0 ? FCString::Atoi(*Args[0]) : DefaultSaveFuzzCount;
		const int32 Seed = Args.Num() > 1 ? FCString::Atoi(*Args[1]) : DefaultSaveFuzzSeed;
		RunSaveFuzz(Count, Seed);
	}

	void RunConsoleTwelveMonth(const TArray<FString>& Args, UWorld* World)
	{
		(void)Args;
		(void)World;
		RunTwelveMonthTest();
	}

	FAutoConsoleCommandWithWorldAndArgs GDAConsoleSaveFuzz(
		TEXT("da.SaveFuzz"),
		TEXT("Run the deterministic save/profile fuzz. Usage: da.SaveFuzz [count] [seed]"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&RunConsoleSaveFuzz));

	FAutoConsoleCommandWithWorldAndArgs GDAConsoleTwelveMonth(
		TEXT("da.TwelveMonthTest"),
		TEXT("Run the 12-month day-by-day calendar/profile simulation with save/load checks."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&RunConsoleTwelveMonth));
}

void UDAA02GateTestSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	bRunFuzz = ParseFuzzCount(FuzzCount);
	bRunTwelveMonth = FParse::Param(FCommandLine::Get(), TEXT("DATwelveMonthTest"));
	if (!bRunFuzz && !bRunTwelveMonth)
	{
		return;
	}

	FuzzSeed = ParseFuzzSeed();
	TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateUObject(this, &UDAA02GateTestSubsystem::Tick), 0.75f);
}

void UDAA02GateTestSubsystem::Deinitialize()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}
	Super::Deinitialize();
}

bool UDAA02GateTestSubsystem::Tick(float DeltaSeconds)
{
	(void)DeltaSeconds;
	bool bPassed = true;
	if (bRunFuzz)
	{
		bPassed = RunSaveFuzz(FuzzCount, FuzzSeed) && bPassed;
	}
	if (bRunTwelveMonth)
	{
		bPassed = RunTwelveMonthTest() && bPassed;
	}
	FPlatformMisc::RequestExitWithStatus(false, bPassed ? 0 : 1, TEXT("DAA02GateTests"));
	return false;
}
