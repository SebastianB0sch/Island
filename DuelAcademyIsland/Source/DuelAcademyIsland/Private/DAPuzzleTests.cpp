// Duel Academy Island - puzzle data automation tests.

#include "Misc/AutomationTest.h"

#include "DAPuzzleRuntime.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	bool PuzzleLoadJson(const FString& Path, TSharedPtr<FJsonObject>& OutObject)
	{
		FString Raw;
		if (!FFileHelper::LoadFileToString(Raw, *Path))
		{
			return false;
		}
		TSharedPtr<FJsonValue> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			return false;
		}
		OutObject = Root->AsObject();
		return OutObject.IsValid();
	}

	bool PuzzleCardExists(const TSet<int32>& CardIds, const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		int32 CardId = 0;
		return Object.IsValid() && Object->TryGetNumberField(Field, CardId) && CardIds.Contains(CardId);
	}

	void CheckPuzzleSide(FAutomationTestBase& Test, const TSharedPtr<FJsonObject>& Side, const TSet<int32>& CardIds, const FString& Label)
	{
		if (!Side.IsValid())
		{
			Test.AddError(FString::Printf(TEXT("%s: missing side"), *Label));
			return;
		}
		const TArray<TSharedPtr<FJsonValue>>* Field = nullptr;
		if (Side->TryGetArrayField(TEXT("field"), Field))
		{
			Test.TestTrue(FString::Printf(TEXT("%s: at most 5 monsters"), *Label), Field->Num() <= 5);
			for (const TSharedPtr<FJsonValue>& Value : *Field)
			{
				const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
				Test.TestTrue(FString::Printf(TEXT("%s: known monster"), *Label), PuzzleCardExists(CardIds, Entry, TEXT("card_id")));
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* Spells = nullptr;
		if (Side->TryGetArrayField(TEXT("spell_traps"), Spells))
		{
			Test.TestTrue(FString::Printf(TEXT("%s: at most 5 spell/traps"), *Label), Spells->Num() <= 5);
			for (const TSharedPtr<FJsonValue>& Value : *Spells)
			{
				const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
				Test.TestTrue(FString::Printf(TEXT("%s: known spell/trap"), *Label), PuzzleCardExists(CardIds, Entry, TEXT("card_id")));
			}
		}
		for (const TCHAR* Zone : { TEXT("hand"), TEXT("graveyard"), TEXT("deck"), TEXT("extra") })
		{
			const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
			if (Side->TryGetArrayField(Zone, Values))
			{
				for (const TSharedPtr<FJsonValue>& Value : *Values)
				{
					const int32 CardId = Value.IsValid() ? static_cast<int32>(Value->AsNumber()) : 0;
					Test.TestTrue(FString::Printf(TEXT("%s: known card in %s"), *Label, Zone), CardIds.Contains(CardId));
				}
			}
		}
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDAPuzzleDataTest, "DuelAcademy.Puzzles.Level1",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FDAPuzzleDataTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	TSet<int32> CardIds;
	{
		FString Raw;
		const FString CardsPath = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/cards.json"));
		if (!TestTrue(TEXT("cards.json loads"), FFileHelper::LoadFileToString(Raw, *CardsPath)))
		{
			return false;
		}
		TSharedPtr<FJsonValue> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
		const TArray<TSharedPtr<FJsonValue>>* RawCards = nullptr;
		if (FJsonSerializer::Deserialize(Reader, Root) && Root.IsValid() && Root->TryGetArray(RawCards))
		{
			for (const TSharedPtr<FJsonValue>& Value : *RawCards)
			{
				const TSharedPtr<FJsonObject> Card = Value.IsValid() ? Value->AsObject() : nullptr;
				int32 CardId = 0;
				if (Card.IsValid() && Card->TryGetNumberField(TEXT("id"), CardId))
				{
					CardIds.Add(CardId);
				}
			}
		}
	}
	TestTrue(TEXT("card database has cards"), CardIds.Num() >= 1200);

	TArray<FString> Files;
	IFileManager::Get().FindFiles(Files, *FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Puzzles"), TEXT("P*.json")), true, false);
	Files.Sort();
	TestEqual(TEXT("100 puzzle files exist"), Files.Num(), 100);

	TSet<FString> SeenIds;
	TMap<int32, int32> LevelCounts;
	for (const FString& File : Files)
	{
		TSharedPtr<FJsonObject> Puzzle;
		if (!TestTrue(FString::Printf(TEXT("puzzle loads: %s"), *File), PuzzleLoadJson(FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Puzzles"), File), Puzzle)))
		{
			continue;
		}

		FString Id;
		Puzzle->TryGetStringField(TEXT("id"), Id);
		TestFalse(FString::Printf(TEXT("%s: id is set"), *File), Id.IsEmpty());
		TestFalse(FString::Printf(TEXT("%s: id is unique"), *Id), SeenIds.Contains(Id));
		SeenIds.Add(Id);

		int32 Level = 0;
		Puzzle->TryGetNumberField(TEXT("level"), Level);
		TestTrue(FString::Printf(TEXT("%s: level is 1..5"), *Id), Level >= 1 && Level <= 5);
		LevelCounts.FindOrAdd(Level)++;

		int32 TimeLimit = 0;
		Puzzle->TryGetNumberField(TEXT("time_limit"), TimeLimit);
		TestTrue(FString::Printf(TEXT("%s: fair time limit"), *Id), TimeLimit >= 10);

		int32 TurnLimit = 0;
		Puzzle->TryGetNumberField(TEXT("turn_limit"), TurnLimit);
		TestEqual(FString::Printf(TEXT("%s: one-turn puzzle"), *Id), TurnLimit, 1);

		const TArray<TSharedPtr<FJsonValue>>* Solution = nullptr;
		TestTrue(FString::Printf(TEXT("%s: has solution"), *Id), Puzzle->TryGetArrayField(TEXT("solution"), Solution) && Solution->Num() > 0);

		const TSharedPtr<FJsonObject>* RewardObject = nullptr;
		int32 RewardDp = 0;
		if (Puzzle->TryGetObjectField(TEXT("reward"), RewardObject) && RewardObject)
		{
			(*RewardObject)->TryGetNumberField(TEXT("dp"), RewardDp);
		}
		TestTrue(FString::Printf(TEXT("%s: DP reward"), *Id), RewardDp > 0);

		const TSharedPtr<FJsonObject>* PlayerObject = nullptr;
		const TSharedPtr<FJsonObject>* OpponentObject = nullptr;
		Puzzle->TryGetObjectField(TEXT("player"), PlayerObject);
		Puzzle->TryGetObjectField(TEXT("opponent_state"), OpponentObject);
		TSharedPtr<FJsonObject> PlayerState;
		TSharedPtr<FJsonObject> OpponentState;
		if (PlayerObject)
		{
			PlayerState = *PlayerObject;
		}
		if (OpponentObject)
		{
			OpponentState = *OpponentObject;
		}
		CheckPuzzleSide(*this, PlayerState, CardIds, Id + TEXT(".player"));
		CheckPuzzleSide(*this, OpponentState, CardIds, Id + TEXT(".opponent"));

		if (Solution)
		{
			for (const TSharedPtr<FJsonValue>& StepValue : *Solution)
			{
				const TSharedPtr<FJsonObject> Step = StepValue.IsValid() ? StepValue->AsObject() : nullptr;
				FString Action;
				if (Step.IsValid())
				{
					Step->TryGetStringField(TEXT("action"), Action);
				}
				TestFalse(FString::Printf(TEXT("%s: solution action set"), *Id), Action.IsEmpty());
			}
		}
	}

	for (int32 Level = 1; Level <= 5; ++Level)
	{
		TestEqual(FString::Printf(TEXT("20 level-%d puzzle files exist"), Level),
			LevelCounts.FindRef(Level), 20);
	}
	TestEqual(TEXT("P001..P100 present"), SeenIds.Num(), 100);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDAPuzzleRuntimeLoaderTest, "DuelAcademy.Puzzles.RuntimeLoader",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FDAPuzzleRuntimeLoaderTest::RunTest(const FString& Parameters)
{
	(void)Parameters;

	const FString PuzzleDir = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Puzzles"));
	FString Error;

	// Loading must replace the caller's array, not append to it.
	TArray<FDAPuzzleDefinition> Puzzles;
	FDAPuzzleDefinition Stale;
	Stale.Id = TEXT("STALE");
	Puzzles.Add(Stale);
	if (!TestTrue(TEXT("puzzle directory loads through the runtime"),
			FDAPuzzleRuntime::LoadPuzzleDirectory(PuzzleDir, Puzzles, Error)))
	{
		AddError(Error);
		return false;
	}
	TestEqual(TEXT("all 100 puzzles load"), Puzzles.Num(), 100);
	TestEqual(TEXT("filename order starts at P001"), Puzzles[0].Id, FString(TEXT("P001")));
	TestEqual(TEXT("filename order ends at P100"), Puzzles.Last().Id, FString(TEXT("P100")));
	TestFalse(TEXT("pre-existing entries are cleared"),
		Puzzles.ContainsByPredicate([](const FDAPuzzleDefinition& Puzzle) { return Puzzle.Id == TEXT("STALE"); }));

	// Reloading into the same array is idempotent.
	TestTrue(TEXT("puzzle directory reloads"),
		FDAPuzzleRuntime::LoadPuzzleDirectory(PuzzleDir, Puzzles, Error));
	TestEqual(TEXT("reload does not duplicate puzzles"), Puzzles.Num(), 100);

	// ReplayById is a public entry point; it must not accept traversal.
	FDAPuzzleReplayResult ReplayResult;
	Error.Reset();
	TestFalse(TEXT("ReplayById rejects path traversal"),
		FDAPuzzleRuntime::ReplayById(nullptr, TEXT("../P001"), ReplayResult, Error));
	TestFalse(TEXT("ReplayById traversal error is reported"), Error.IsEmpty());
	Error.Reset();
	TestFalse(TEXT("ReplayById rejects embedded separators"),
		FDAPuzzleRuntime::ReplayById(nullptr, TEXT("P001/P002"), ReplayResult, Error));
	TestFalse(TEXT("ReplayById separator error is reported"), Error.IsEmpty());

	// The live timed path loads by id without composing paths itself.
	FDAPuzzleDefinition LoadedPuzzle;
	Error.Reset();
	TestTrue(TEXT("LoadPuzzleById loads the authored puzzle"),
		FDAPuzzleRuntime::LoadPuzzleById(TEXT("P001"), LoadedPuzzle, Error));
	TestEqual(TEXT("LoadPuzzleById preserves the puzzle id"), LoadedPuzzle.Id, FString(TEXT("P001")));
	Error.Reset();
	TestFalse(TEXT("LoadPuzzleById rejects a traversal id"),
		FDAPuzzleRuntime::LoadPuzzleById(TEXT("../P001"), LoadedPuzzle, Error));
	TestFalse(TEXT("LoadPuzzleById traversal error is reported"), Error.IsEmpty());
	Error.Reset();
	TestFalse(TEXT("LoadPuzzleById rejects an embedded extension"),
		FDAPuzzleRuntime::LoadPuzzleById(TEXT("P001.json"), LoadedPuzzle, Error));
	Error.Reset();
	TestFalse(TEXT("LoadPuzzleById reports a missing puzzle"),
		FDAPuzzleRuntime::LoadPuzzleById(TEXT("P999"), LoadedPuzzle, Error));
	TestTrue(TEXT("missing puzzle error names the file"), Error.Contains(TEXT("P999")));

	// BuildScenario is the boundary used by non-JSON callers.
	FDuelScenario Scenario;
	FDAPuzzleDefinition Invalid = Puzzles[0];
	Invalid.Id.Reset();
	TestFalse(TEXT("BuildScenario rejects an empty id"),
		FDAPuzzleRuntime::BuildScenario(Invalid, Scenario, Error));
	Invalid = Puzzles[0];
	Invalid.PlayerLp = 0;
	TestFalse(TEXT("BuildScenario rejects a zero life total"),
		FDAPuzzleRuntime::BuildScenario(Invalid, Scenario, Error));
	Invalid = Puzzles[0];
	Invalid.TurnLimit = 0;
	TestFalse(TEXT("BuildScenario rejects a zero turn limit"),
		FDAPuzzleRuntime::BuildScenario(Invalid, Scenario, Error));
	Invalid = Puzzles[0];
	Invalid.PlayerHand.Add(0);
	TestFalse(TEXT("BuildScenario rejects a zero card id"),
		FDAPuzzleRuntime::BuildScenario(Invalid, Scenario, Error));
	Invalid = Puzzles[0];
	if (Invalid.PlayerField.Num() == 0)
	{
		FDuelScenarioCard Card;
		Card.CardId = 1;
		Card.Zone = EDuelZone::Monster;
		Card.ZoneIndex = 0;
		Invalid.PlayerField.Add(Card);
	}
	Invalid.PlayerField[0].ZoneIndex = 7;
	TestFalse(TEXT("BuildScenario rejects an out-of-range field zone"),
		FDAPuzzleRuntime::BuildScenario(Invalid, Scenario, Error));
	Invalid = Puzzles[0];
	if (Invalid.PlayerField.Num() > 0)
	{
		Invalid.PlayerField[0].ZoneIndex = 0;
		FDuelScenarioCard Duplicate = Invalid.PlayerField[0];
		Invalid.PlayerField.Add(Duplicate);
	}
	TestFalse(TEXT("BuildScenario rejects duplicate field zones"),
		FDAPuzzleRuntime::BuildScenario(Invalid, Scenario, Error));

	// Malformed JSON files must be rejected with a useful error rather than
	// silently producing a default board.
	const FString TempDir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("CodeReviewPass2/PuzzleRuntimeAutomation"));
	IFileManager::Get().DeleteDirectory(*TempDir, false, true);
	if (!TestTrue(TEXT("puzzle test directory is created"), IFileManager::Get().MakeDirectory(*TempDir, true)))
	{
		return false;
	}

	FString BaseText;
	if (!TestTrue(TEXT("P001 is readable for malformed-file fixtures"),
			FFileHelper::LoadFileToString(BaseText, *FPaths::Combine(PuzzleDir, TEXT("P001.json")))))
	{
		IFileManager::Get().DeleteDirectory(*TempDir, false, true);
		return false;
	}
	auto WriteFixture = [&TempDir](const TCHAR* FileName, const FString& Text)
	{
		return FFileHelper::SaveStringToFile(Text, *FPaths::Combine(TempDir, FileName));
	};

	const FString Renamed = BaseText.Replace(TEXT("\"id\": \"P001\""), TEXT("\"id\": \"P900\""));
	TestTrue(TEXT("duplicate fixture A writes"), WriteFixture(TEXT("P900.json"), Renamed));
	TestTrue(TEXT("duplicate fixture B writes"), WriteFixture(TEXT("P901.json"), Renamed));
	TArray<FDAPuzzleDefinition> Duplicates;
	Error.Reset();
	TestFalse(TEXT("duplicate puzzle ids are rejected"),
		FDAPuzzleRuntime::LoadPuzzleDirectory(TempDir, Duplicates, Error));
	TestTrue(TEXT("duplicate error names the problem"), Error.Contains(TEXT("Duplicate")));
	TestEqual(TEXT("failed directory load leaves no partial results"), Duplicates.Num(), 0);

	IFileManager::Get().DeleteDirectory(*TempDir, false, true);
	IFileManager::Get().MakeDirectory(*TempDir, true);

	TestTrue(TEXT("non-numeric hand fixture writes"),
		WriteFixture(TEXT("P902.json"), BaseText.Replace(TEXT("\"hand\": []"), TEXT("\"hand\": [\"oops\"]"))));
	FDAPuzzleDefinition Malformed;
	Error.Reset();
	TestFalse(TEXT("non-numeric hand entries are rejected"),
		FDAPuzzleRuntime::LoadPuzzleFile(FPaths::Combine(TempDir, TEXT("P902.json")), Malformed, Error));
	TestTrue(TEXT("hand error names the field"), Error.Contains(TEXT("hand")));

	TestTrue(TEXT("non-numeric target fixture writes"),
		WriteFixture(TEXT("P903.json"), BaseText.Replace(TEXT("\"target\": \"direct\""), TEXT("\"target\": []"))));
	Error.Reset();
	TestFalse(TEXT("malformed attack targets are rejected"),
		FDAPuzzleRuntime::LoadPuzzleFile(FPaths::Combine(TempDir, TEXT("P903.json")), Malformed, Error));
	TestTrue(TEXT("target error names the field"), Error.Contains(TEXT("target")));

	TestTrue(TEXT("zero LP fixture writes"),
		WriteFixture(TEXT("P904.json"), BaseText.Replace(TEXT("\"lp\": 8000"), TEXT("\"lp\": 0"))));
	Error.Reset();
	TestFalse(TEXT("zero life totals are rejected"),
		FDAPuzzleRuntime::LoadPuzzleFile(FPaths::Combine(TempDir, TEXT("P904.json")), Malformed, Error));
	TestTrue(TEXT("LP error names the field"), Error.Contains(TEXT("lp")));

	IFileManager::Get().DeleteDirectory(*TempDir, false, true);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
