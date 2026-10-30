// Duel Academy Island - puzzle data automation tests.

#include "Misc/AutomationTest.h"

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
	TestEqual(TEXT("20 level-1 puzzle files exist"), Files.Num(), 20);

	TSet<FString> SeenIds;
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
		TestEqual(FString::Printf(TEXT("%s: level 1"), *Id), Level, 1);

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

	TestEqual(TEXT("P001..P020 present"), SeenIds.Num(), 20);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
