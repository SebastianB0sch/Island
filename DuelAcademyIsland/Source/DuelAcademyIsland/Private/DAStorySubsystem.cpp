// Duel Academy Island - story runtime implementation.

#include "DAStorySubsystem.h"

#include "DAEventGraph.h"
#include "DAHUD.h"
#include "DADialogueUI.h"
#include "DAProfileSubsystem.h"
#include "DACalendarSubsystem.h"
#include "DAInventorySubsystem.h"
#include "DuelAcademyIsland.h"

#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "Math/Color.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
	const TCHAR* const DefaultPlayerName = TEXT("ALEX");

	FString ReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, const FString& Fallback = FString())
	{
		FString Value;
		if (Object.IsValid() && Object->TryGetStringField(Field, Value))
		{
			return Value;
		}
		return Fallback;
	}

	int32 ReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Fallback = 0)
	{
		int32 Value = Fallback;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return Value;
	}

	bool ReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, bool bFallback = false)
	{
		bool bValue = bFallback;
		if (Object.IsValid())
		{
			Object->TryGetBoolField(Field, bValue);
		}
		return bValue;
	}

	float ReadFloat(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, float Fallback = 0.f)
	{
		double Value = Fallback;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return static_cast<float>(Value);
	}

	TArray<TSharedPtr<FJsonObject>> ReadObjectArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		TArray<TSharedPtr<FJsonObject>> Result;
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (Object.IsValid() && Object->TryGetArrayField(Field, Values) && Values)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Values)
			{
				if (Value.IsValid() && Value->AsObject().IsValid())
				{
					Result.Add(Value->AsObject());
				}
			}
		}
		return Result;
	}

	TArray<FString> ReadStringArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		TArray<FString> Result;
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (Object.IsValid() && Object->TryGetArrayField(Field, Values) && Values)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Values)
			{
				if (Value.IsValid())
				{
					Result.Add(Value->AsString());
				}
			}
		}
		return Result;
	}

	FString ReadArg(const TArray<FString>& Args, int32 Index)
	{
		return Args.IsValidIndex(Index) ? Args[Index] : FString();
	}

	int32 MonthNumberToIndex(int32 MonthNumber)
	{
		return ((MonthNumber - 10) % 12 + 12) % 12;
	}

	EDAStoryCommandType ParseCommandType(const FString& RawType)
	{
		const FString Type = RawType.ToLower();
		if (Type == TEXT("dialogue")) return EDAStoryCommandType::Dialogue;
		if (Type == TEXT("choice")) return EDAStoryCommandType::Choice;
		if (Type == TEXT("camera")) return EDAStoryCommandType::Camera;
		if (Type == TEXT("move_npc") || Type == TEXT("movenpc")) return EDAStoryCommandType::MoveNpc;
		if (Type == TEXT("fade")) return EDAStoryCommandType::Fade;
		if (Type == TEXT("wait")) return EDAStoryCommandType::Wait;
		if (Type == TEXT("banner")) return EDAStoryCommandType::Banner;
		if (Type == TEXT("play_sfx") || Type == TEXT("playsfx")) return EDAStoryCommandType::PlaySfx;
		if (Type == TEXT("music")) return EDAStoryCommandType::Music;
		if (Type == TEXT("duel")) return EDAStoryCommandType::Duel;
		if (Type == TEXT("reward")) return EDAStoryCommandType::Reward;
		if (Type == TEXT("set_flag") || Type == TEXT("setflag")) return EDAStoryCommandType::SetFlag;
		if (Type == TEXT("end")) return EDAStoryCommandType::End;
		return EDAStoryCommandType::Unknown;
	}

	FString CommandTypeName(EDAStoryCommandType Type)
	{
		switch (Type)
		{
		case EDAStoryCommandType::Dialogue: return TEXT("Dialogue");
		case EDAStoryCommandType::Choice: return TEXT("Choice");
		case EDAStoryCommandType::Camera: return TEXT("Camera");
		case EDAStoryCommandType::MoveNpc: return TEXT("MoveNpc");
		case EDAStoryCommandType::Fade: return TEXT("Fade");
		case EDAStoryCommandType::Wait: return TEXT("Wait");
		case EDAStoryCommandType::Banner: return TEXT("Banner");
		case EDAStoryCommandType::PlaySfx: return TEXT("PlaySfx");
		case EDAStoryCommandType::Music: return TEXT("Music");
		case EDAStoryCommandType::Duel: return TEXT("Duel");
		case EDAStoryCommandType::Reward: return TEXT("Reward");
		case EDAStoryCommandType::SetFlag: return TEXT("SetFlag");
		case EDAStoryCommandType::End: return TEXT("End");
		default: return TEXT("Unknown");
		}
	}

	bool IsA02OwnedCounter(const FString& Counter)
	{
		static const TSet<FString> Owned = {
			TEXT("wins_total"), TEXT("wins_jaden"), TEXT("wins_syrus"), TEXT("wins_chumley"),
			TEXT("losses_total"), TEXT("draws_total"), TEXT("duels_total"),
			TEXT("dp_earned_total"), TEXT("timed_clears"), TEXT("written_correct"),
			TEXT("battle_damage_total"), TEXT("monsters_destroyed_total"), TEXT("lp_lost_total")
		};
		return Owned.Contains(Counter);
	}

	FLinearColor ColorFromHex(const FString& Hex)
	{
		if (Hex.IsEmpty())
		{
			return FLinearColor(1.f, 0.78f, 0.25f, 1.f);
		}
		const FColor Parsed = FColor::FromHex(Hex);
		return FLinearColor(Parsed);
	}

	FString SpeakerTitleFor(const FString& Speaker)
	{
		if (Speaker == TEXT("sheppard")) return TEXT("Chancellor");
		if (Speaker == TEXT("banner")) return TEXT("Slifer Red Headmaster");
		if (Speaker == TEXT("mimicry")) return TEXT("Practical Dueling");
		if (Speaker == TEXT("jaden") || Speaker == TEXT("syrus") || Speaker == TEXT("chumley")) return TEXT("Slifer Red");
		if (Speaker == TEXT("dorothy")) return TEXT("Card Shop");
		if (Speaker == TEXT("player")) return TEXT("Student");
		if (Speaker == TEXT("pda")) return TEXT("PDA");
		return FString();
	}
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

void UDAStorySubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	bAutoOpeningRequested = FParse::Param(FCommandLine::Get(), TEXT("DAOpeningTest"));
	bAutoSelfTestRequested = FParse::Param(FCommandLine::Get(), TEXT("DAStorySelfTest"));

	TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateUObject(this, &UDAStorySubsystem::Tick));

	LoadOpeningData();
	TryRegisterSaveProvider();
}

void UDAStorySubsystem::Deinitialize()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}

	if (bSaveProviderRegistered)
	{
		if (UGameInstance* GI = GetGameInstance())
		{
			if (UDASaveSubsystem* Save = GI->GetSubsystem<UDASaveSubsystem>())
			{
				Save->UnregisterPayloadProvider(this);
			}
		}
		bSaveProviderRegistered = false;
	}

	Super::Deinitialize();
}

UDAStorySubsystem* UDAStorySubsystem::Get(const UObject* WorldContext)
{
	if (!WorldContext)
	{
		return nullptr;
	}
	if (const UWorld* World = WorldContext->GetWorld())
	{
		if (UGameInstance* GI = World->GetGameInstance())
		{
			return GI->GetSubsystem<UDAStorySubsystem>();
		}
	}
	return nullptr;
}

ADAHUD* UDAStorySubsystem::ResolveHUD() const
{
	if (UGameInstance* GI = GetGameInstance())
	{
		if (UWorld* World = GI->GetWorld())
		{
			if (APlayerController* PC = World->GetFirstPlayerController())
			{
				return Cast<ADAHUD>(PC->GetHUD());
			}
		}
	}
	return nullptr;
}

UDAProfileSubsystem* UDAStorySubsystem::ResolveProfile() const
{
	UGameInstance* GI = GetGameInstance();
	return GI ? GI->GetSubsystem<UDAProfileSubsystem>() : nullptr;
}

UDACalendarSubsystem* UDAStorySubsystem::ResolveCalendar() const
{
	UGameInstance* GI = GetGameInstance();
	return GI ? GI->GetSubsystem<UDACalendarSubsystem>() : nullptr;
}

void UDAStorySubsystem::TryRegisterSaveProvider()
{
	if (bSaveProviderRegistered)
	{
		return;
	}
	if (UGameInstance* GI = GetGameInstance())
	{
		if (UDASaveSubsystem* Save = GI->GetSubsystem<UDASaveSubsystem>())
		{
			Save->RegisterPayloadProvider(this);
			bSaveProviderRegistered = true;
		}
	}
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

bool UDAStorySubsystem::LoadJsonObject(const FString& RelativePath, TSharedPtr<FJsonObject>& Out, FString& OutError) const
{
	const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Story"), RelativePath);
	FString Raw;
	if (!FFileHelper::LoadFileToString(Raw, *Path))
	{
		OutError = FString::Printf(TEXT("story JSON not found: %s"), *Path);
		return false;
	}

	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
	if (!FJsonSerializer::Deserialize(Reader, Out) || !Out.IsValid())
	{
		OutError = FString::Printf(TEXT("story JSON is invalid: %s"), *Path);
		return false;
	}
	return true;
}

bool UDAStorySubsystem::LoadOpeningData()
{
	if (bLoaded)
	{
		return true;
	}

	FString Error;
	TSharedPtr<FJsonObject> OpeningRoot;
	if (!LoadJsonObject(TEXT("opening.json"), OpeningRoot, Error))
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: %s"), *Error);
		return false;
	}

	ParseEvents(OpeningRoot);
	ParseRewards(OpeningRoot);

	FString ScenesPath = TEXT("scenes/opening.json");
	FString DialoguePath = TEXT("dialogue/opening.json");
	FString SchedulesPath = TEXT("schedules/opening.json");
	const TSharedPtr<FJsonObject>* FilesObject = nullptr;
	if (OpeningRoot->TryGetObjectField(TEXT("files"), FilesObject) && FilesObject)
	{
		ScenesPath = ReadString(*FilesObject, TEXT("scenes"), ScenesPath);
		DialoguePath = ReadString(*FilesObject, TEXT("dialogue"), DialoguePath);
		SchedulesPath = ReadString(*FilesObject, TEXT("schedules"), SchedulesPath);
	}

	TSharedPtr<FJsonObject> ScenesRoot;
	if (LoadJsonObject(ScenesPath, ScenesRoot, Error))
	{
		ParseScenes(ScenesRoot);
	}
	else
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: %s"), *Error);
	}

	TSharedPtr<FJsonObject> DialogueRoot;
	if (LoadJsonObject(DialoguePath, DialogueRoot, Error))
	{
		ParseDialogue(DialogueRoot);
	}
	else
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: %s"), *Error);
	}

	TSharedPtr<FJsonObject> SchedulesRoot;
	if (LoadJsonObject(SchedulesPath, SchedulesRoot, Error))
	{
		ParseSchedules(SchedulesRoot);
	}
	else
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: %s"), *Error);
	}

	bLoaded = EventGraph.GetEvents().Num() > 0 && Scenes.Num() > 0 && Lines.Num() > 0;
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: loaded opening data (%d events, %d scenes, %d lines, %d schedules)."),
		EventGraph.GetEvents().Num(), Scenes.Num(), Lines.Num(), ScheduledNpcs.Num());
	return bLoaded;
}

void UDAStorySubsystem::ParseEvents(const TSharedPtr<FJsonObject>& Root)
{
	FString Error;
	if (!EventGraph.LoadFromJson(Root, Error))
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: event graph load failed: %s"), *Error);
	}
}

void UDAStorySubsystem::ParseScenes(const TSharedPtr<FJsonObject>& Root)
{
	Scenes.Reset();
	const TSharedPtr<FJsonObject>* SceneObject = nullptr;
	if (!Root->TryGetObjectField(TEXT("scenes"), SceneObject) || !SceneObject)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: scenes bundle has no scenes object."));
		return;
	}

	for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*SceneObject)->Values)
	{
		const TSharedPtr<FJsonObject> SceneJson = Pair.Value.IsValid() ? Pair.Value->AsObject() : TSharedPtr<FJsonObject>();
		if (!SceneJson.IsValid())
		{
			continue;
		}

		FDAStoryScene Scene;
		Scene.Id = ReadString(SceneJson, TEXT("id"), FString(*Pair.Key));
		Scene.EventId = ReadString(SceneJson, TEXT("event_id"), ReadString(SceneJson, TEXT("event")));
		Scene.Raw = SceneJson;

		const TArray<TSharedPtr<FJsonValue>>* CommandValues = nullptr;
		if (SceneJson->TryGetArrayField(TEXT("commands"), CommandValues) && CommandValues)
		{
			for (const TSharedPtr<FJsonValue>& CommandValue : *CommandValues)
			{
				const TSharedPtr<FJsonObject> CommandJson = CommandValue.IsValid() ? CommandValue->AsObject() : TSharedPtr<FJsonObject>();
				if (!CommandJson.IsValid())
				{
					continue;
				}

				FDAStoryCommand Command;
				Command.Raw = CommandJson;
				Command.Type = ParseCommandType(ReadString(CommandJson, TEXT("type")));
				Command.CommandId = ReadString(CommandJson, TEXT("command_id"));
				Command.Key = ReadString(CommandJson, TEXT("key"), ReadString(CommandJson, TEXT("text_key")));
				Command.Speaker = ReadString(CommandJson, TEXT("speaker"));
				Command.Portrait = ReadString(CommandJson, TEXT("portrait"));
				Command.TextKey = ReadString(CommandJson, TEXT("text_key"), Command.Key);
				Command.Anchor = ReadString(CommandJson, TEXT("anchor"));
				Command.Npc = ReadString(CommandJson, TEXT("npc"));
				Command.Title = ReadString(CommandJson, TEXT("title"));
				Command.Subtitle = ReadString(CommandJson, TEXT("subtitle"));
				Command.Style = ReadString(CommandJson, TEXT("style"));
				Command.Sfx = ReadString(CommandJson, TEXT("sfx"));
				Command.Track = ReadString(CommandJson, TEXT("track"));
				Command.OpponentId = ReadString(CommandJson, TEXT("opponent_id"), ReadString(CommandJson, TEXT("opponent")));
				Command.OpponentName = ReadString(CommandJson, TEXT("opponent_name"));
				Command.OpponentDeckId = ReadString(CommandJson, TEXT("opponent_deck_id"), ReadString(CommandJson, TEXT("deck")));
				Command.Mode = ReadString(CommandJson, TEXT("mode"));
				Command.ScenarioId = ReadString(CommandJson, TEXT("scenario_id"));
				Command.OnWin = ReadString(CommandJson, TEXT("on_win"));
				Command.OnLose = ReadString(CommandJson, TEXT("on_lose"));
				Command.OnDraw = ReadString(CommandJson, TEXT("on_draw"));
				Command.NextScene = ReadString(CommandJson, TEXT("next_scene"));
				Command.RewardId = ReadString(CommandJson, TEXT("reward_id"));
				Command.FlagName = ReadString(CommandJson, TEXT("flag"));
				Command.Dp = ReadInt(CommandJson, TEXT("dp"), 0);
				Command.TurnLimit = ReadInt(CommandJson, TEXT("turn_limit"), 0);
				Command.bOptional = ReadBool(CommandJson, TEXT("optional"), false);
				Command.bTutorial = ReadBool(CommandJson, TEXT("tutorial"), false);
				Command.bCountsAsWin = ReadBool(CommandJson, TEXT("counts_as_win"), false);
				Command.bCompleteEvent = ReadBool(CommandJson, TEXT("complete_event"), true);
				Command.bEnterFreeRoam = ReadBool(CommandJson, TEXT("enter_free_roam"), false);
				Command.bSkippable = ReadBool(CommandJson, TEXT("skippable"), true);
				Command.Duration = ReadFloat(CommandJson, TEXT("duration"), 0.f);

				const TArray<FString> Args = ReadStringArray(CommandJson, TEXT("args"));
				if (Command.Anchor.IsEmpty()) Command.Anchor = ReadArg(Args, 0);
				if (Command.Npc.IsEmpty()) Command.Npc = ReadArg(Args, 0);
				if (Command.Sfx.IsEmpty()) Command.Sfx = ReadArg(Args, 0);
				if (Command.Track.IsEmpty()) Command.Track = ReadArg(Args, 0);
				if (Command.Title.IsEmpty()) Command.Title = ReadArg(Args, 0);
				if (Command.OpponentId.IsEmpty()) Command.OpponentId = ReadArg(Args, 0);
				if (Command.OpponentDeckId.IsEmpty()) Command.OpponentDeckId = ReadArg(Args, 1);
				if (Command.Mode.IsEmpty()) Command.Mode = ReadArg(Args, 2);
				if (Command.ScenarioId.IsEmpty()) Command.ScenarioId = ReadArg(Args, 3);
				if (Command.FlagName.IsEmpty()) Command.FlagName = ReadArg(Args, 0);
				if (Command.NextScene.IsEmpty() && Command.Type == EDAStoryCommandType::End)
				{
					Command.NextScene = ReadString(CommandJson, TEXT("next_scene"));
				}

				Command.bFlagValue = ReadBool(CommandJson, TEXT("value"), true);

				Scene.Commands.Add(Command);
			}
		}

		Scenes.Add(Scene.Id, Scene);
	}
}

void UDAStorySubsystem::ParseDialogue(const TSharedPtr<FJsonObject>& Root)
{
	Lines.Reset();
	SpeakerNames.Reset();
	SpeakerColors.Reset();

	const TSharedPtr<FJsonObject>* SpeakersObject = nullptr;
	if (Root->TryGetObjectField(TEXT("speakers"), SpeakersObject) && SpeakersObject)
	{
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*SpeakersObject)->Values)
		{
			const TSharedPtr<FJsonObject> SpeakerJson = Pair.Value.IsValid() ? Pair.Value->AsObject() : TSharedPtr<FJsonObject>();
			if (SpeakerJson.IsValid())
			{
				const FString SpeakerId(*Pair.Key);
				SpeakerNames.Add(SpeakerId, ReadString(SpeakerJson, TEXT("display_name"), SpeakerId));
				SpeakerColors.Add(SpeakerId, ColorFromHex(ReadString(SpeakerJson, TEXT("color"))));
			}
		}
	}

	const TSharedPtr<FJsonObject>* LinesObject = nullptr;
	if (!Root->TryGetObjectField(TEXT("lines"), LinesObject) || !LinesObject)
	{
		if (!Root->TryGetObjectField(TEXT("nodes"), LinesObject) || !LinesObject)
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: dialogue bundle has no lines object."));
			return;
		}
	}

	for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*LinesObject)->Values)
	{
		const TSharedPtr<FJsonObject> LineJson = Pair.Value.IsValid() ? Pair.Value->AsObject() : TSharedPtr<FJsonObject>();
		if (!LineJson.IsValid())
		{
			continue;
		}

		FDAStoryLine Line;
		Line.Key = ReadString(LineJson, TEXT("key"), FString(*Pair.Key));
		Line.Speaker = ReadString(LineJson, TEXT("speaker"));
		Line.Portrait = ReadString(LineJson, TEXT("portrait"));
		Line.Expression = ReadString(LineJson, TEXT("expression"), TEXT("neutral"));
		Line.Text = ReadString(LineJson, TEXT("text"));
		Line.Next = ReadString(LineJson, TEXT("next"));
		Line.Raw = LineJson;

		const TSharedPtr<FJsonObject>* InputObject = nullptr;
		if (LineJson->TryGetObjectField(TEXT("input"), InputObject) && InputObject)
		{
			Line.Input = *InputObject;
		}

		const TArray<TSharedPtr<FJsonValue>>* ChoiceValues = nullptr;
		if (LineJson->TryGetArrayField(TEXT("choices"), ChoiceValues) && ChoiceValues)
		{
			for (const TSharedPtr<FJsonValue>& ChoiceValue : *ChoiceValues)
			{
				const TSharedPtr<FJsonObject> ChoiceJson = ChoiceValue.IsValid() ? ChoiceValue->AsObject() : TSharedPtr<FJsonObject>();
				if (!ChoiceJson.IsValid())
				{
					continue;
				}
				FDAStoryChoice Choice;
				Choice.Id = ReadString(ChoiceJson, TEXT("id"));
				Choice.Text = ReadString(ChoiceJson, TEXT("text"));
				Choice.NextScene = ReadString(ChoiceJson, TEXT("next_scene"));
				Choice.NextKey = ReadString(ChoiceJson, TEXT("next_key"));
				Choice.Requirements = ReadObjectArray(ChoiceJson, TEXT("requirements"));
				Choice.Outcomes = ReadObjectArray(ChoiceJson, TEXT("outcomes"));
				Choice.Raw = ChoiceJson;
				Line.Choices.Add(Choice);
			}
		}

		Lines.Add(Line.Key, Line);
	}
}

void UDAStorySubsystem::ParseSchedules(const TSharedPtr<FJsonObject>& Root)
{
	ScheduledNpcs.Reset();

	const TSharedPtr<FJsonObject>* NpcsObject = nullptr;
	if (Root->TryGetObjectField(TEXT("npcs"), NpcsObject) && NpcsObject)
	{
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*NpcsObject)->Values)
		{
			const TSharedPtr<FJsonObject> NpcJson = Pair.Value.IsValid() ? Pair.Value->AsObject() : TSharedPtr<FJsonObject>();
			if (NpcJson.IsValid())
			{
				ScheduledNpcs.Add(FString(*Pair.Key), NpcJson);
			}
		}
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* ScheduleValues = nullptr;
	if (Root->TryGetArrayField(TEXT("schedules"), ScheduleValues) && ScheduleValues)
	{
		for (const TSharedPtr<FJsonValue>& Value : *ScheduleValues)
		{
			const TSharedPtr<FJsonObject> NpcJson = Value.IsValid() ? Value->AsObject() : TSharedPtr<FJsonObject>();
			if (!NpcJson.IsValid())
			{
				continue;
			}
			const FString NpcId = ReadString(NpcJson, TEXT("npc"), ReadString(NpcJson, TEXT("id")));
			if (!NpcId.IsEmpty())
			{
				ScheduledNpcs.Add(NpcId, NpcJson);
			}
		}
	}
}

void UDAStorySubsystem::ParseRewards(const TSharedPtr<FJsonObject>& Root)
{
	Rewards.Reset();
	const TSharedPtr<FJsonObject>* RewardsObject = nullptr;
	if (Root->TryGetObjectField(TEXT("rewards"), RewardsObject) && RewardsObject)
	{
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*RewardsObject)->Values)
		{
			const TSharedPtr<FJsonObject> RewardJson = Pair.Value.IsValid() ? Pair.Value->AsObject() : TSharedPtr<FJsonObject>();
			if (RewardJson.IsValid())
			{
				Rewards.Add(FString(*Pair.Key), RewardJson);
			}
		}
	}
}

// ---------------------------------------------------------------------------
// Opening / event flow
// ---------------------------------------------------------------------------

void UDAStorySubsystem::ResetRuntimeState()
{
	CurrentEventId.Reset();
	CurrentSceneId.Reset();
	CurrentCommands.Reset();
	CommandIndex = 0;

	CompletedEvents.Reset();
	AppliedRewardIds.Reset();
	Objectives.Reset();

	bRunning = false;
	bFreeRoam = false;
	bOpeningStarted = false;
	bWaitingForDialogue = false;
	bWaitingForChoice = false;
	bWaitingForDuel = false;
	bWaitingForTimer = false;
	bPendingContinue = false;
	bPendingTextInput = false;
	WaitRemaining = 0.f;
	ActiveChoices.Reset();
	ActiveChoiceConversationId.Reset();
	ActiveChoiceLineKey.Reset();
	PendingTextInputKey.Reset();
	SelectedStarterDeck.Reset();
	PendingDuel = FDAStoryPendingDuel();
}

void UDAStorySubsystem::StartOpening()
{
	if (!bLoaded && !LoadOpeningData())
	{
		return;
	}

	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	if (!Profile || !Calendar)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: opening cannot start without profile/calendar subsystems."));
		return;
	}

	bHeadless = ResolveHUD() == nullptr;

	if (!Profile->IsInitialized())
	{
		Profile->InitializeNewGame(DefaultPlayerName);
		Calendar->SetDate(1, 0, 1, EDADayPeriod::AM);
	}
	else if (Profile->GetPlayerName().IsEmpty() || Profile->GetPlayerName().Equals(TEXT("New Student"), ESearchCase::IgnoreCase))
	{
		Profile->SetPlayerName(DefaultPlayerName);
	}

	if (!IsEventCompleteRuntime(TEXT("E01")) && Calendar->GetMonthIndex() == 0 && Calendar->GetDay() == 7)
	{
		Calendar->SetDate(1, 0, 1, EDADayPeriod::AM);
	}

	if (SelectedStarterDeck.IsEmpty())
	{
		EnsureStarterDeck(TEXT("fire"));
	}
	else
	{
		ApplyDeckGrant(SelectedStarterDeck);
	}

	Profile->SetFlag(TEXT("new_game_started"), true);
	bOpeningStarted = true;

	if (IsEventCompleteRuntime(TEXT("E01b")))
	{
		bFreeRoam = true;
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: opening already complete; free roam restored."));
		return;
	}

	if (IsEventCompleteRuntime(TEXT("E01")))
	{
		Calendar->SetDate(1, 0, 7, EDADayPeriod::AM);
		StartEvent(TEXT("E01b"));
		return;
	}

	StartEvent(TEXT("E01"));
}

void UDAStorySubsystem::StartOpeningFresh()
{
	if (!bLoaded && !LoadOpeningData())
	{
		return;
	}

	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	if (!Profile || !Calendar)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: opening cannot start without profile/calendar subsystems."));
		return;
	}

	ResetRuntimeState();
	bHeadless = ResolveHUD() == nullptr;
	Profile->InitializeNewGame(DefaultPlayerName);
	Calendar->SetDate(1, 0, 1, EDADayPeriod::AM);
	EnsureStarterDeck(TEXT("fire"));
	Profile->SetFlag(TEXT("new_game_started"), true);
	bOpeningStarted = true;
	StartEvent(TEXT("E01"));
}

void UDAStorySubsystem::StartEvent(const FString& EventId)
{
	if (!bLoaded && !LoadOpeningData())
	{
		return;
	}
	if (bRunning)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: cannot start %s while %s is running."), *EventId, *CurrentEventId);
		return;
	}

	const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
	if (!Event)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: unknown event %s."), *EventId);
		return;
	}
	if (Event->bOnce && IsEventCompleteRuntime(EventId))
	{
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: event %s is already complete."), *EventId);
		return;
	}

	FString Reason;
	if (!EventGraph.EvaluateRequirements(*Event, ResolveProfile(), ResolveCalendar(), Reason))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: event %s requirements not met: %s"), *EventId, *Reason);
		return;
	}
	if (!EventGraph.EvaluateTrigger(*Event, ResolveProfile(), ResolveCalendar(), Reason))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: event %s trigger not met: %s"), *EventId, *Reason);
		return;
	}

	CurrentEventId = EventId;
	CurrentSceneId.Reset();
	CurrentCommands.Reset();
	CommandIndex = 0;
	bRunning = true;
	bFreeRoam = false;

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: starting event %s (%s), scene %s."), *EventId, *Event->Title, *Event->Scene);
	StartScene(Event->Scene, 0);
}

void UDAStorySubsystem::TryStartNextAvailableEvent()
{
	if (bRunning)
	{
		return;
	}

	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	if (!Profile || !Calendar)
	{
		return;
	}

	const TArray<FString> Available = EventGraph.GetAvailableEvents(Profile, Calendar);
	for (const FString& EventId : Available)
	{
		const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
		if (!Event || !Event->Trigger.IsValid())
		{
			continue;
		}
		const FString TriggerType = ReadString(Event->Trigger, TEXT("type"));
		if (TriggerType == TEXT("talk"))
		{
			continue;
		}

		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: auto-starting next event %s."), *EventId);
		StartEvent(EventId);
		return;
	}

	if (IsEventCompleteRuntime(TEXT("E01b")))
	{
		bFreeRoam = true;
	}
}

void UDAStorySubsystem::StartScene(const FString& SceneId, int32 StartIndex)
{
	const FDAStoryScene* Scene = Scenes.Find(SceneId);
	if (!Scene)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: missing scene %s."), *SceneId);
		FinishEvent(true, false);
		return;
	}

	CurrentSceneId = SceneId;
	CurrentCommands = Scene->Commands;
	CommandIndex = FMath::Clamp(StartIndex, 0, CurrentCommands.Num());
	bRunning = true;
	bWaitingForDialogue = false;
	bWaitingForChoice = false;
	bWaitingForDuel = false;
	bWaitingForTimer = false;
	bPendingContinue = true;

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: scene %s (%d commands), start %d."),
		*SceneId, CurrentCommands.Num(), CommandIndex);
}

void UDAStorySubsystem::FinishScene()
{
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: scene %s reached its end without End; completing event."), *CurrentSceneId);
	FinishEvent(true, false);
}

void UDAStorySubsystem::FinishEvent(bool bComplete, bool bEnterFreeRoam)
{
	const FString EventId = CurrentEventId;

	if (bComplete && !EventId.IsEmpty())
	{
		ApplyEventOutcomes(EventId);
		CompleteEvent(EventId);
	}
	if (bEnterFreeRoam)
	{
		bFreeRoam = true;
	}

	bRunning = false;
	bWaitingForDialogue = false;
	bWaitingForChoice = false;
	bWaitingForDuel = false;
	bWaitingForTimer = false;
	bPendingTextInput = false;
	CurrentSceneId.Reset();
	CurrentCommands.Reset();
	CommandIndex = 0;

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: event %s finished (complete=%s, freeRoam=%s)."),
		*EventId, bComplete ? TEXT("true") : TEXT("false"), bFreeRoam ? TEXT("true") : TEXT("false"));

	if (bComplete && !EventId.IsEmpty())
	{
		TryStartNextAvailableEvent();
	}
}

// ---------------------------------------------------------------------------
// Queue execution
// ---------------------------------------------------------------------------

bool UDAStorySubsystem::Tick(float DeltaSeconds)
{
	TryRegisterSaveProvider();

	if (bAutoSelfTestRequested && !bAutoSelfTestStarted)
	{
		AutoStartDelay -= DeltaSeconds;
		if (AutoStartDelay <= 0.f)
		{
			bAutoSelfTestStarted = true;
			RunSelfTest();
		}
		return true;
	}

	if (bAutoOpeningRequested && !bAutoOpeningStarted)
	{
		if (ResolveHUD() != nullptr)
		{
			AutoStartDelay -= DeltaSeconds;
			if (AutoStartDelay <= 0.f)
			{
				bAutoOpeningStarted = true;
				StartOpeningFresh();
			}
		}
		return true;
	}

	if (bWaitingForTimer)
	{
		WaitRemaining -= DeltaSeconds;
		if (WaitRemaining <= 0.f)
		{
			WaitRemaining = 0.f;
			bWaitingForTimer = false;
			++CommandIndex;
			bPendingContinue = true;
		}
	}

	if ((bWaitingForDialogue || bWaitingForChoice) && !bWaitingForDuel)
	{
		if (ADAHUD* HUD = ResolveHUD())
		{
			if (FDADialogueUI* Dialogue = HUD->GetDialogueUI())
			{
				if (!Dialogue->IsOpen())
				{
					HandleDialogueClosed(Dialogue->GetConversationId());
				}
			}
		}
	}

	if (bWaitingForDuel)
	{
		PendingDuel.Elapsed += DeltaSeconds;
		if (ADAHUD* HUD = ResolveHUD())
		{
			if (HUD->IsDuelOpen())
			{
				PendingDuel.bOpened = true;
			}
			else if (PendingDuel.bOpened)
			{
				UDAProfileSubsystem* Profile = ResolveProfile();
				bool bWon = false;
				bool bDraw = false;
				if (Profile)
				{
					if (Profile->GetCounter(TEXT("draws_total")) > PendingDuel.PreDraws)
					{
						bDraw = true;
					}
					else if (PendingDuel.bTutorial)
					{
						bWon = Profile->GetCounter(TEXT("wins_syrus")) > PendingDuel.PreWinsSyrus;
					}
					else
					{
						bWon = Profile->GetCounter(TEXT("wins_jaden")) > PendingDuel.PreWinsJaden;
					}
				}
				ResolvePendingDuel(bWon, bDraw);
			}
			else if (PendingDuel.Elapsed > 10.f)
			{
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: duel UI did not open; treating as a loss."));
				ResolvePendingDuel(false, false);
			}
		}
		else if (PendingDuel.Elapsed > 1.f)
		{
			ResolvePendingDuel(false, false);
		}
	}

	if (bPendingContinue && !bWaitingForDialogue && !bWaitingForChoice && !bWaitingForDuel
		&& !bWaitingForTimer && !bPendingTextInput)
	{
		bPendingContinue = false;
		PumpQueue();
	}

	return true;
}

bool UDAStorySubsystem::PumpQueue()
{
	if (!bRunning)
	{
		return false;
	}
	if (bWaitingForDialogue || bWaitingForChoice || bWaitingForDuel || bWaitingForTimer || bPendingTextInput)
	{
		return false;
	}

	int32 Guard = 0;
	while (bRunning && Guard++ < 4096)
	{
		if (!CurrentCommands.IsValidIndex(CommandIndex))
		{
			FinishScene();
			return true;
		}

		const FDAStoryCommand Command = CurrentCommands[CommandIndex];
		bool bBlocked = false;
		const bool bContinue = ExecuteCommand(Command, bBlocked);
		if (bBlocked)
		{
			return false;
		}
		if (!bContinue)
		{
			return false;
		}
		++CommandIndex;
	}

	UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: command guard exceeded in scene %s."), *CurrentSceneId);
	bPendingContinue = false;
	return false;
}

bool UDAStorySubsystem::ExecuteCommand(const FDAStoryCommand& Command, bool& bOutBlocked)
{
	bOutBlocked = false;

	switch (Command.Type)
	{
	case EDAStoryCommandType::Dialogue:
	{
		if (bHeadless)
		{
			return true;
		}
		ADAHUD* HUD = ResolveHUD();
		if (!HUD)
		{
			bHeadless = true;
			return true;
		}
		const FDAStoryLine* Line = FindLine(Command.Key);
		if (!Line)
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: missing dialogue line %s."), *Command.Key);
			return true;
		}
		FDADialogueLine UILine;
		BuildDialogueLine(*Line, false, UILine);
		bWaitingForDialogue = true;
		HUD->BeginDialogueLine(UILine);
		BindDialogueDelegates(HUD);
		bOutBlocked = true;
		return false;
	}

	case EDAStoryCommandType::Choice:
	{
		const FDAStoryLine* Line = FindLine(Command.Key);
		if (!Line)
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: missing choice line %s."), *Command.Key);
			return true;
		}

		if (Line->Input.IsValid())
		{
			if (bHeadless)
			{
				SetPlayerName(GetPlayerNameForDisplay());
				return true;
			}
			ADAHUD* HUD = ResolveHUD();
			if (!HUD)
			{
				bHeadless = true;
				SetPlayerName(GetPlayerNameForDisplay());
				return true;
			}
			FDADialogueLine UILine;
			BuildDialogueLine(*Line, false, UILine);
			bPendingTextInput = true;
			PendingTextInputKey = Line->Key;
			bWaitingForDialogue = true;
			HUD->BeginDialogueLine(UILine);
			BindDialogueDelegates(HUD);
			bOutBlocked = true;
			return false;
		}

		ActiveChoices.Reset();
		for (const FDAStoryChoice& Choice : Line->Choices)
		{
			if (EvaluateConditions(Choice.Requirements))
			{
				ActiveChoices.Add(Choice);
			}
		}
		if (ActiveChoices.Num() == 0)
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: choice line %s has no valid options."), *Command.Key);
			return true;
		}

		if (bHeadless)
		{
			ApplyChoiceInternal(0);
			bOutBlocked = true;
			return false;
		}

		ADAHUD* HUD = ResolveHUD();
		if (!HUD)
		{
			bHeadless = true;
			ApplyChoiceInternal(0);
			bOutBlocked = true;
			return false;
		}

		ActiveChoiceLineKey = Line->Key;
		ActiveChoiceConversationId = FString::Printf(TEXT("%s.choice.%d"), *CurrentSceneId, CommandIndex);

		FDADialogueLine UILine;
		BuildDialogueLine(*Line, true, UILine);
		TArray<FDADialogueLine> ChoiceLines;
		ChoiceLines.Add(UILine);
		bWaitingForChoice = true;
		HUD->BeginDialogue(ChoiceLines, ActiveChoiceConversationId);
		BindDialogueDelegates(HUD);
		if (FDADialogueUI* Dialogue = HUD->GetDialogueUI())
		{
			Dialogue->SetAllowEscapeClose(false);
		}
		bOutBlocked = true;
		return false;
	}

	case EDAStoryCommandType::Camera:
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: camera anchor %s (%.2fs)."), *Command.Anchor, Command.Duration);
		return true;

	case EDAStoryCommandType::MoveNpc:
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: move %s to %s (%.2fs)."), *Command.Npc, *Command.Anchor, Command.Duration);
		return true;

	case EDAStoryCommandType::Fade:
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: fade %s (%.2fs)."), *ReadString(Command.Raw, TEXT("mode"), TEXT("out")), Command.Duration);
		return true;

	case EDAStoryCommandType::Wait:
		if (bHeadless || bFastForward || Command.Duration <= 0.f)
		{
			return true;
		}
		WaitRemaining = Command.Duration;
		bWaitingForTimer = true;
		bOutBlocked = true;
		return false;

	case EDAStoryCommandType::Banner:
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: banner '%s' - '%s'."), *Command.Title, *Command.Subtitle);
		return true;

	case EDAStoryCommandType::PlaySfx:
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: sfx %s."), *Command.Sfx);
		return true;

	case EDAStoryCommandType::Music:
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: music %s."), *Command.Track);
		return true;

	case EDAStoryCommandType::Duel:
	{
		CapturePendingDuel(Command);
		if (bHeadless)
		{
			SimulateDuelResult(true, false);
			bOutBlocked = true;
			return false;
		}

		ADAHUD* HUD = ResolveHUD();
		if (!HUD)
		{
			bHeadless = true;
			SimulateDuelResult(true, false);
			bOutBlocked = true;
			return false;
		}

		bWaitingForDuel = true;
		PendingDuel.bOpened = false;
		PendingDuel.Elapsed = 0.f;
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: opening duel selector for %s (%s)."),
			*Command.OpponentId, *Command.OpponentDeckId);
		HUD->OpenDuelDeckSelect(Command.OpponentId, Command.OpponentName, Command.OpponentDeckId);
		bOutBlocked = true;
		return false;
	}

	case EDAStoryCommandType::Reward:
		ApplyRewardCommand(Command);
		return true;

	case EDAStoryCommandType::SetFlag:
		ApplySetFlag(Command.FlagName, Command.bFlagValue);
		return true;

	case EDAStoryCommandType::End:
		if (!Command.NextScene.IsEmpty())
		{
			StartScene(Command.NextScene, 0);
			bOutBlocked = true;
			return false;
		}
		FinishEvent(Command.bCompleteEvent, Command.bEnterFreeRoam);
		bOutBlocked = true;
		return false;

	default:
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: unsupported command type %s."), *CommandTypeName(Command.Type));
		return true;
	}
}

void UDAStorySubsystem::Advance()
{
	if (bWaitingForDialogue)
	{
		if (ADAHUD* HUD = ResolveHUD())
		{
			if (FDADialogueUI* Dialogue = HUD->GetDialogueUI())
			{
				if (Dialogue->IsOpen())
				{
					Dialogue->Advance();
					return;
				}
			}
		}
		bWaitingForDialogue = false;
		++CommandIndex;
		bPendingContinue = true;
		return;
	}

	if (bWaitingForChoice)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: Advance ignored while a choice is pending."));
		return;
	}

	if (bWaitingForTimer)
	{
		WaitRemaining = 0.f;
		bWaitingForTimer = false;
		++CommandIndex;
		bPendingContinue = true;
		return;
	}

	bPendingContinue = false;
	PumpQueue();
}

void UDAStorySubsystem::Choose(int32 OptionIndex)
{
	if (!bWaitingForChoice || !ActiveChoices.IsValidIndex(OptionIndex))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: Choose(%d) ignored; no matching pending choice."), OptionIndex);
		return;
	}

	if (ADAHUD* HUD = ResolveHUD())
	{
		if (FDADialogueUI* Dialogue = HUD->GetDialogueUI())
		{
			if (Dialogue->IsOpen())
			{
				Dialogue->Choose(OptionIndex);
				return;
			}
		}
	}

	ApplyChoiceInternal(OptionIndex);
	bWaitingForChoice = false;
	bPendingContinue = true;
}

void UDAStorySubsystem::BindDialogueDelegates(ADAHUD* HUD)
{
	if (!HUD || (bDialogueDelegatesBound && BoundHUD.Get() == HUD))
	{
		return;
	}

	if (FDADialogueUI* Dialogue = HUD->GetDialogueUI())
	{
		Dialogue->OnDialogueClosed.AddUObject(this, &UDAStorySubsystem::HandleDialogueClosed);
		Dialogue->OnChoiceMade.AddUObject(this, &UDAStorySubsystem::HandleChoiceMade);
		BoundHUD = HUD;
		bDialogueDelegatesBound = true;
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: bound dialogue callbacks."));
	}
}

void UDAStorySubsystem::HandleDialogueClosed(const FString& ConversationId)
{
	if (bPendingTextInput)
	{
		SetPlayerName(GetPlayerNameForDisplay());
		bPendingTextInput = false;
		bWaitingForDialogue = false;
		++CommandIndex;
		bPendingContinue = true;
		return;
	}

	if (bWaitingForChoice)
	{
		// The choice callback normally resolves first. If the UI was closed
		// without a choice, take the first option rather than soft-locking.
		ApplyChoiceInternal(0);
		bWaitingForChoice = false;
		bPendingContinue = true;
		return;
	}

	if (bWaitingForDialogue)
	{
		bWaitingForDialogue = false;
		++CommandIndex;
		bPendingContinue = true;
	}
}

void UDAStorySubsystem::HandleChoiceMade(const FString& ConversationId, int32 OptionIndex)
{
	if (!bWaitingForChoice || !ConversationId.Equals(ActiveChoiceConversationId))
	{
		return;
	}

	ApplyChoiceInternal(OptionIndex);
	bWaitingForChoice = false;
	bPendingContinue = true;
}

void UDAStorySubsystem::RequestContinue()
{
	bPendingContinue = true;
}

// ---------------------------------------------------------------------------
// Choices / dialogue
// ---------------------------------------------------------------------------

void UDAStorySubsystem::ApplyChoiceInternal(int32 OptionIndex)
{
	if (!ActiveChoices.IsValidIndex(OptionIndex))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: invalid choice index %d; using 0."), OptionIndex);
		OptionIndex = 0;
	}
	if (!ActiveChoices.IsValidIndex(OptionIndex))
	{
		ActiveChoices.Reset();
		bWaitingForChoice = false;
		bPendingContinue = true;
		return;
	}

	const FDAStoryChoice Choice = ActiveChoices[OptionIndex];
	ActiveChoices.Reset();

	ApplyOutcomes(Choice.Outcomes);

	if (!Choice.NextScene.IsEmpty())
	{
		StartScene(Choice.NextScene, FindCommandIndexForKey(Choice.NextScene, Choice.NextKey));
	}
	else if (!Choice.NextKey.IsEmpty())
	{
		const int32 FoundIndex = FindCommandIndexForKey(CurrentSceneId, Choice.NextKey);
		if (FoundIndex != INDEX_NONE)
		{
			CommandIndex = FoundIndex;
		}
		else
		{
			++CommandIndex;
		}
	}
	else
	{
		++CommandIndex;
	}

	bWaitingForChoice = false;
	bPendingContinue = true;
}

int32 UDAStorySubsystem::FindCommandIndexForKey(const FString& Key) const
{
	return FindCommandIndexForKey(CurrentSceneId, Key);
}

int32 UDAStorySubsystem::FindCommandIndexForKey(const FString& SceneId, const FString& Key) const
{
	if (Key.IsEmpty())
	{
		return 0;
	}
	if (SceneId.Equals(CurrentSceneId))
	{
		for (int32 Index = 0; Index < CurrentCommands.Num(); ++Index)
		{
			if (CurrentCommands[Index].Key.Equals(Key, ESearchCase::IgnoreCase)
				|| CurrentCommands[Index].TextKey.Equals(Key, ESearchCase::IgnoreCase))
			{
				return Index;
			}
		}
	}
	if (const FDAStoryScene* Scene = Scenes.Find(SceneId))
	{
		for (int32 Index = 0; Index < Scene->Commands.Num(); ++Index)
		{
			if (Scene->Commands[Index].Key.Equals(Key, ESearchCase::IgnoreCase)
				|| Scene->Commands[Index].TextKey.Equals(Key, ESearchCase::IgnoreCase))
			{
				return Index;
			}
		}
	}
	return 0;
}

FDAStoryLine* UDAStorySubsystem::FindLine(const FString& Key)
{
	return Lines.Find(Key);
}

const FDAStoryLine* UDAStorySubsystem::FindLine(const FString& Key) const
{
	return Lines.Find(Key);
}

FString UDAStorySubsystem::ResolveText(const FString& Text) const
{
	FString Result = Text;
	Result.ReplaceInline(TEXT("{player_name}"), *GetPlayerNameForDisplay());
	Result.ReplaceInline(TEXT("{player_name_spelled}"), *GetPlayerNameSpelled());
	return Result;
}

FString UDAStorySubsystem::GetPlayerNameForDisplay() const
{
	if (const UDAProfileSubsystem* Profile = ResolveProfile())
	{
		const FString Name = Profile->GetPlayerName();
		if (!Name.IsEmpty() && !Name.Equals(TEXT("New Student"), ESearchCase::IgnoreCase))
		{
			return Name;
		}
	}
	return DefaultPlayerName;
}

FString UDAStorySubsystem::GetPlayerNameSpelled() const
{
	const FString Name = GetPlayerNameForDisplay();
	FString Spelled;
	for (const TCHAR Character : Name)
	{
		if (!Spelled.IsEmpty())
		{
			Spelled.AppendChar(TEXT(' '));
		}
		Spelled.AppendChar(Character);
	}
	return Spelled;
}

void UDAStorySubsystem::BuildDialogueLine(const FDAStoryLine& Line, bool bChoice, FDADialogueLine& OutLine) const
{
	OutLine = FDADialogueLine();
	OutLine.SpeakerId = Line.Speaker;
	OutLine.SpeakerName = SpeakerNames.FindRef(Line.Speaker);
	if (Line.Speaker.Equals(TEXT("player"), ESearchCase::IgnoreCase))
	{
		OutLine.SpeakerName = GetPlayerNameForDisplay();
	}
	else if (Line.Speaker.Equals(TEXT("narrator"), ESearchCase::IgnoreCase))
	{
		OutLine.SpeakerName = TEXT("Narration");
	}
	else if (Line.Speaker.Equals(TEXT("pda"), ESearchCase::IgnoreCase))
	{
		OutLine.SpeakerName = TEXT("PDA");
	}
	else if (OutLine.SpeakerName.IsEmpty())
	{
		OutLine.SpeakerName = Line.Speaker;
	}

	FString PortraitId = Line.Portrait;
	FString Expression = Line.Expression;
	if (PortraitId.Equals(TEXT("none"), ESearchCase::IgnoreCase))
	{
		PortraitId.Reset();
	}
	else if (PortraitId.Equals(TEXT("ui_pda"), ESearchCase::IgnoreCase))
	{
		Expression = TEXT("neutral");
	}
	else
	{
		int32 UnderscoreIndex = INDEX_NONE;
		if (PortraitId.FindLastChar(TEXT('_'), UnderscoreIndex) && UnderscoreIndex > 0)
		{
			const FString Suffix = PortraitId.RightChop(UnderscoreIndex + 1);
			if (!Suffix.IsEmpty())
			{
				Expression = Suffix;
				PortraitId = PortraitId.LeftChop(PortraitId.Len() - UnderscoreIndex);
			}
		}
	}

	OutLine.Portrait = PortraitId;
	OutLine.Expression = Expression.IsEmpty() ? FString(TEXT("neutral")) : Expression;
	OutLine.Text = ResolveText(Line.Text);
	OutLine.TextKey = Line.Key;
	OutLine.NodeId = Line.Key;
	OutLine.SpeakerTitle = SpeakerTitleFor(Line.Speaker);
	OutLine.bChoice = bChoice;
	OutLine.Accent = SpeakerColors.FindRef(Line.Speaker);
	if (OutLine.Accent.A <= 0.f)
	{
		OutLine.Accent = FLinearColor(1.f, 0.78f, 0.25f, 1.f);
	}

	if (bChoice)
	{
		for (const FDAStoryChoice& Choice : ActiveChoices)
		{
			OutLine.Options.Add(ResolveText(Choice.Text));
		}
	}
}

void UDAStorySubsystem::SelectStarterDeck(const FString& DeckId)
{
	ApplyDeckGrant(DeckId);
}

void UDAStorySubsystem::SetPlayerName(const FString& NewName)
{
	FString Clean = NewName.TrimStartAndEnd().ToUpper();
	Clean = Clean.Left(8);
	if (Clean.IsEmpty())
	{
		Clean = DefaultPlayerName;
	}
	if (UDAProfileSubsystem* Profile = ResolveProfile())
	{
		Profile->SetPlayerName(Clean);
	}
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: player name set to %s."), *Clean);
}

// ---------------------------------------------------------------------------
// Outcomes / rewards
// ---------------------------------------------------------------------------

bool UDAStorySubsystem::EvaluateConditions(const TArray<TSharedPtr<FJsonObject>>& Conditions) const
{
	FString Reason;
	return FDAEventGraph::EvaluateConditionArray(Conditions, ResolveProfile(), ResolveCalendar(), Reason);
}

void UDAStorySubsystem::ApplyEventOutcomes(const FString& EventId)
{
	const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
	if (!Event)
	{
		return;
	}
	ApplyOutcomes(Event->Outcomes);
}

void UDAStorySubsystem::ApplyOutcomes(const TArray<TSharedPtr<FJsonObject>>& Outcomes)
{
	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();

	for (const TSharedPtr<FJsonObject>& Outcome : Outcomes)
	{
		if (!Outcome.IsValid())
		{
			continue;
		}

		const TArray<TSharedPtr<FJsonObject>> Conditions = ReadObjectArray(Outcome, TEXT("conditions"));
		if (Conditions.Num() > 0 && !EvaluateConditions(Conditions))
		{
			continue;
		}

		const FString Type = ReadString(Outcome, TEXT("type"));
		if (Type == TEXT("set_flag") || Type == TEXT("flag"))
		{
			const FString Flag = ReadString(Outcome, TEXT("flag"), ReadString(Outcome, TEXT("id")));
			ApplySetFlag(Flag, ReadBool(Outcome, TEXT("value"), true));
		}
		else if (Type == TEXT("add_counter") || Type == TEXT("counter"))
		{
			const FString Counter = ReadString(Outcome, TEXT("counter"), ReadString(Outcome, TEXT("id")));
			const int32 Amount = ReadInt(Outcome, TEXT("amount"), 1);
			if (IsA02OwnedCounter(Counter))
			{
				UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: counter %s is A02-owned; story outcome skipped."), *Counter);
			}
			else if (Profile)
			{
				Profile->IncrementCounter(Counter, Amount);
			}
		}
		else if (Type == TEXT("reward") || Type == TEXT("grant_reward"))
		{
			ApplyRewardById(ReadString(Outcome, TEXT("reward_id"), ReadString(Outcome, TEXT("id"))));
		}
		else if (Type == TEXT("set_calendar"))
		{
			SetCalendarFromJson(Outcome);
		}
		else if (Type == TEXT("set_objective"))
		{
			SetObjective(ReadString(Outcome, TEXT("id")), ReadString(Outcome, TEXT("text")));
		}
		else if (Type == TEXT("complete_event"))
		{
			CompleteEvent(ReadString(Outcome, TEXT("event"), ReadString(Outcome, TEXT("id"))));
		}
		else if (Type == TEXT("unlock_email"))
		{
			const TArray<FString> Contacts = ReadStringArray(Outcome, TEXT("contacts"));
			if (Contacts.Num() > 0)
			{
				for (const FString& Contact : Contacts)
				{
					if (Profile) Profile->UnlockEmail(Contact);
				}
			}
			else if (Profile)
			{
				Profile->UnlockEmail(ReadString(Outcome, TEXT("contact")));
			}
		}
		else if (Type == TEXT("grant_dp"))
		{
			if (Profile) Profile->AwardDP(ReadInt(Outcome, TEXT("amount"), 0));
		}
		else if (Type == TEXT("grant_card"))
		{
			if (UGameInstance* GI = GetGameInstance())
			{
				if (UDAInventorySubsystem* Inventory = GI->GetSubsystem<UDAInventorySubsystem>())
				{
					const int32 CardId = ReadInt(Outcome, TEXT("card_id"), ReadInt(Outcome, TEXT("card"), 0));
					Inventory->AddCard(CardId, ReadInt(Outcome, TEXT("count"), 1));
				}
			}
		}
		else if (Type == TEXT("grant_pack"))
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: pack reward '%s' needs an A06 unopened-pack hook."),
				*ReadString(Outcome, TEXT("pack_id"), ReadString(Outcome, TEXT("pack"))));
		}
		else if (Type == TEXT("grant_deck"))
		{
			ApplyDeckGrant(ReadString(Outcome, TEXT("deck_id"), ReadString(Outcome, TEXT("deck"))));
		}
		else if (Type == TEXT("set_title"))
		{
			if (Profile) Profile->SetTitle(ReadString(Outcome, TEXT("title")));
		}
		else if (Type == TEXT("set_dorm"))
		{
			if (Profile)
			{
				Profile->SetDorm(DuelAcademyProfile::ParseDorm(ReadString(Outcome, TEXT("dorm"), ReadString(Outcome, TEXT("value")))));
			}
		}
		else if (Type == TEXT("next_event"))
		{
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: next_event outcome '%s' is left to the event graph."),
				*ReadString(Outcome, TEXT("event"), ReadString(Outcome, TEXT("id"))));
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: unknown outcome type '%s'."), *Type);
		}
	}
}

void UDAStorySubsystem::ApplyRewardById(const FString& RewardId)
{
	if (RewardId.IsEmpty() || AppliedRewardIds.Contains(RewardId))
	{
		return;
	}

	const TSharedPtr<FJsonObject>* RewardPtr = Rewards.Find(RewardId);
	if (!RewardPtr || !RewardPtr->IsValid())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: reward id '%s' is not declared."), *RewardId);
		return;
	}
	const TSharedPtr<FJsonObject> Reward = *RewardPtr;
	const FString Type = ReadString(Reward, TEXT("type"));

	UDAProfileSubsystem* Profile = ResolveProfile();
	if (Type == TEXT("dp"))
	{
		const int32 Amount = ReadInt(Reward, TEXT("amount"), ReadInt(Reward, TEXT("dp"), 0));
		if (Profile)
		{
			if (RewardId == TEXT("opening_starting_dp") && Profile->GetDP() < Amount)
			{
				Profile->AwardDP(Amount - Profile->GetDP());
			}
			else if (RewardId != TEXT("opening_starting_dp"))
			{
				Profile->AwardDP(Amount);
			}
		}
	}
	else if (Type == TEXT("email_unlock"))
	{
		const TArray<FString> Contacts = ReadStringArray(Reward, TEXT("contacts"));
		if (Profile)
		{
			for (const FString& Contact : Contacts)
			{
				Profile->UnlockEmail(Contact);
			}
		}
	}
	else if (Type == TEXT("deck_grant"))
	{
		ApplyDeckGrant(ReadString(Reward, TEXT("deck_id")));
	}
	else if (Type == TEXT("card") || Type == TEXT("card_grant"))
	{
		if (UGameInstance* GI = GetGameInstance())
		{
			if (UDAInventorySubsystem* Inventory = GI->GetSubsystem<UDAInventorySubsystem>())
			{
				const int32 CardId = ReadInt(Reward, TEXT("card_id"), ReadInt(Reward, TEXT("card"), 0));
				Inventory->AddCard(CardId, ReadInt(Reward, TEXT("count"), 1));
			}
		}
	}
	else if (Type == TEXT("pack") || Type == TEXT("pack_grant"))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: pack reward '%s' needs an A06 unopened-pack hook."),
			*ReadString(Reward, TEXT("pack_id"), ReadString(Reward, TEXT("pack"))));
	}
	else if (Type == TEXT("flag"))
	{
		ApplySetFlag(ReadString(Reward, TEXT("flag")), true);
	}
	else if (Type == TEXT("title"))
	{
		if (Profile) Profile->SetTitle(ReadString(Reward, TEXT("title")));
	}
	else if (Type == TEXT("dorm"))
	{
		if (Profile) Profile->SetDorm(DuelAcademyProfile::ParseDorm(ReadString(Reward, TEXT("dorm"))));
	}

	AppliedRewardIds.Add(RewardId);
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: applied reward %s (%s)."), *RewardId, *Type);
}

void UDAStorySubsystem::ApplyRewardCommand(const FDAStoryCommand& Command)
{
	if (!Command.RewardId.IsEmpty())
	{
		ApplyRewardById(Command.RewardId);
		return;
	}

	const FString Key = Command.CommandId.IsEmpty()
		? FString::Printf(TEXT("cmd:%s:%d"), *CurrentSceneId, CommandIndex)
		: FString::Printf(TEXT("cmd:%s"), *Command.CommandId);
	if (AppliedRewardIds.Contains(Key))
	{
		return;
	}

	UDAProfileSubsystem* Profile = ResolveProfile();
	if (Profile && Command.Dp > 0)
	{
		Profile->AwardDP(Command.Dp);
	}

	if (Command.Raw.IsValid())
	{
		const TArray<FString> Emails = ReadStringArray(Command.Raw, TEXT("emails"));
		if (Profile)
		{
			for (const FString& Email : Emails)
			{
				Profile->UnlockEmail(Email);
			}
		}

		const FString DeckId = ReadString(Command.Raw, TEXT("deck_id"));
		if (!DeckId.IsEmpty())
		{
			ApplyDeckGrant(DeckId);
		}

		const FString PackId = ReadString(Command.Raw, TEXT("pack_id"));
		if (!PackId.IsEmpty())
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: pack reward '%s' needs an A06 unopened-pack hook."), *PackId);
		}

		const TArray<FString> Flags = ReadStringArray(Command.Raw, TEXT("flags"));
		for (const FString& Flag : Flags)
		{
			ApplySetFlag(Flag, true);
		}
	}

	AppliedRewardIds.Add(Key);
}

void UDAStorySubsystem::ApplySetFlag(const FString& Flag, bool bValue)
{
	if (Flag.IsEmpty())
	{
		return;
	}
	if (UDAProfileSubsystem* Profile = ResolveProfile())
	{
		Profile->SetFlag(Flag, bValue);
	}
}

void UDAStorySubsystem::ApplyDeckGrant(const FString& DeckId)
{
	if (DeckId.IsEmpty())
	{
		return;
	}

	SelectedStarterDeck = DeckId;
	UDAProfileSubsystem* Profile = ResolveProfile();
	if (!Profile)
	{
		return;
	}

	if (UObject* Provider = Profile->GetDeckProvider())
	{
		if (IDAProfileDeckInterface* Decks = Cast<IDAProfileDeckInterface>(Provider))
		{
			Decks->SetActiveDeckId(DeckId);
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: deck provider does not implement IDAProfileDeckInterface."));
		}
	}
	else
	{
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: no A06 deck provider yet; selected deck %s recorded in story state."), *DeckId);
	}

	Profile->SetFlag(FString::Printf(TEXT("starter_deck_%s"), *DeckId.ToLower()), true);
	Profile->SetFlag(TEXT("starter_deck_chosen"), true);
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: granted/activated deck %s."), *DeckId);
}

bool UDAStorySubsystem::EnsureStarterDeck(const FString& PreferredDeck)
{
	FString Deck = PreferredDeck.IsEmpty() ? FString(TEXT("fire")) : PreferredDeck;
	if (UDAProfileSubsystem* Profile = ResolveProfile())
	{
		if (Profile->GetFlag(TEXT("starter_deck_water"))) Deck = TEXT("water");
		else if (Profile->GetFlag(TEXT("starter_deck_wind"))) Deck = TEXT("wind");
		else if (Profile->GetFlag(TEXT("starter_deck_fire"))) Deck = TEXT("fire");
	}

	const FString RewardId = FString::Printf(TEXT("opening_starter_deck_%s"), *Deck.ToLower());
	if (Rewards.Contains(RewardId))
	{
		ApplyRewardById(RewardId);
	}
	else
	{
		ApplyDeckGrant(Deck);
	}
	return true;
}

void UDAStorySubsystem::SetCalendarFromJson(const TSharedPtr<FJsonObject>& Object)
{
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	if (!Calendar || !Object.IsValid())
	{
		return;
	}

	const int32 Year = ReadInt(Object, TEXT("year"), 1);
	int32 MonthIndex = ReadInt(Object, TEXT("month_index"), INDEX_NONE);
	if (MonthIndex == INDEX_NONE)
	{
		MonthIndex = MonthNumberToIndex(ReadInt(Object, TEXT("month"), Calendar->GetMonthNumber()));
	}
	const int32 Day = ReadInt(Object, TEXT("day"), 1);

	EDADayPeriod Period = EDADayPeriod::AM;
	const FString PeriodText = ReadString(Object, TEXT("period"), TEXT("AM"));
	if (PeriodText.Equals(TEXT("PM"), ESearchCase::IgnoreCase)) Period = EDADayPeriod::PM;
	else if (PeriodText.Equals(TEXT("Night"), ESearchCase::IgnoreCase)) Period = EDADayPeriod::Night;

	Calendar->SetDate(Year, MonthIndex, Day, Period);
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: calendar -> %s"), *Calendar->GetFullDateText());
}

void UDAStorySubsystem::SetObjective(const FString& Id, const FString& Text)
{
	if (Id.IsEmpty())
	{
		return;
	}
	Objectives.Add(Id, Text);
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: objective %s - %s"), *Id, *Text);
}

void UDAStorySubsystem::CompleteEvent(const FString& EventId)
{
	if (EventId.IsEmpty())
	{
		return;
	}
	CompletedEvents.Add(EventId);
	if (UDAProfileSubsystem* Profile = ResolveProfile())
	{
		Profile->SetFlag(FDAEventGraph::EventCompletionFlag(EventId), true);
	}
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: event %s marked complete."), *EventId);
}

bool UDAStorySubsystem::IsEventCompleteRuntime(const FString& EventId) const
{
	if (CompletedEvents.Contains(EventId))
	{
		return true;
	}
	if (const UDAProfileSubsystem* Profile = ResolveProfile())
	{
		return Profile->GetFlag(FDAEventGraph::EventCompletionFlag(EventId));
	}
	return false;
}

// ---------------------------------------------------------------------------
// Duels
// ---------------------------------------------------------------------------

void UDAStorySubsystem::CapturePendingDuel(const FDAStoryCommand& Command)
{
	PendingDuel = FDAStoryPendingDuel();
	PendingDuel.OpponentId = Command.OpponentId.IsEmpty() ? TEXT("syrus") : Command.OpponentId;
	PendingDuel.OpponentName = Command.OpponentName.IsEmpty() ? PendingDuel.OpponentId : Command.OpponentName;
	PendingDuel.OpponentDeckId = Command.OpponentDeckId.IsEmpty() ? TEXT("syrus_roids") : Command.OpponentDeckId;
	PendingDuel.Mode = Command.Mode.IsEmpty() ? TEXT("free") : Command.Mode;
	PendingDuel.OnWin = Command.OnWin;
	PendingDuel.OnLose = Command.OnLose;
	PendingDuel.OnDraw = Command.OnDraw;
	PendingDuel.bTutorial = Command.bTutorial;

	if (const UDAProfileSubsystem* Profile = ResolveProfile())
	{
		PendingDuel.PreWinsJaden = Profile->GetCounter(TEXT("wins_jaden"));
		PendingDuel.PreWinsSyrus = Profile->GetCounter(TEXT("wins_syrus"));
		PendingDuel.PreWinsTotal = Profile->GetCounter(TEXT("wins_total"));
		PendingDuel.PreDuels = Profile->GetCounter(TEXT("duels_total"));
		PendingDuel.PreDraws = Profile->GetCounter(TEXT("draws_total"));
	}
}

void UDAStorySubsystem::ResolvePendingDuel(bool bWon, bool bDraw)
{
	const FString SceneId = bDraw ? PendingDuel.OnDraw : (bWon ? PendingDuel.OnWin : PendingDuel.OnLose);
	const FString Opponent = PendingDuel.OpponentId;

	bWaitingForDuel = false;
	PendingDuel.bOpened = false;
	PendingDuel.Elapsed = 0.f;

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: duel vs %s resolved (won=%s, draw=%s) -> %s"),
		*Opponent, bWon ? TEXT("true") : TEXT("false"), bDraw ? TEXT("true") : TEXT("false"),
		SceneId.IsEmpty() ? TEXT("<finish>") : *SceneId);

	if (!SceneId.IsEmpty())
	{
		StartScene(SceneId, 0);
	}
	else
	{
		FinishEvent(true, false);
	}
	bPendingContinue = true;
}

void UDAStorySubsystem::SimulateDuelResult(bool bWon, bool bDraw)
{
	ResolvePendingDuel(bWon, bDraw);
}

void UDAStorySubsystem::NotifyDuelResult(bool bPlayerWon, bool bDraw)
{
	if (!bWaitingForDuel)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: NotifyDuelResult ignored; no pending story duel."));
		return;
	}
	ResolvePendingDuel(bPlayerWon, bDraw);
}

// ---------------------------------------------------------------------------
// Schedules
// ---------------------------------------------------------------------------

bool UDAStorySubsystem::MatchScheduleDate(const TSharedPtr<FJsonObject>& DateObject) const
{
	const UDACalendarSubsystem* Calendar = ResolveCalendar();
	if (!Calendar || !DateObject.IsValid())
	{
		return false;
	}

	int32 Year = Calendar->GetYear();
	int32 Month = Calendar->GetMonthNumber();
	int32 Day = Calendar->GetDay();
	DateObject->TryGetNumberField(TEXT("year"), Year);
	DateObject->TryGetNumberField(TEXT("month"), Month);
	DateObject->TryGetNumberField(TEXT("day"), Day);

	return Calendar->GetYear() == Year && Calendar->GetMonthNumber() == Month && Calendar->GetDay() == Day;
}

bool UDAStorySubsystem::MatchSchedulePeriod(const TSharedPtr<FJsonObject>& Object, const FString& Period) const
{
	if (!Object.IsValid())
	{
		return false;
	}
	const TArray<FString> Periods = ReadStringArray(Object, TEXT("periods"));
	if (Periods.Num() > 0)
	{
		return Periods.Contains(Period);
	}
	const FString Single = ReadString(Object, TEXT("period"));
	return Single.IsEmpty() || Single.Equals(Period, ESearchCase::IgnoreCase);
}

bool UDAStorySubsystem::MatchScheduleWeekday(const TSharedPtr<FJsonObject>& Object, const FString& Weekday) const
{
	if (!Object.IsValid())
	{
		return false;
	}
	const TArray<FString> Weekdays = ReadStringArray(Object, TEXT("weekdays"));
	if (Weekdays.Num() == 0)
	{
		return true;
	}
	for (const FString& Day : Weekdays)
	{
		if (Day.Equals(TEXT("all"), ESearchCase::IgnoreCase) || Day.Equals(Weekday, ESearchCase::IgnoreCase))
		{
			return true;
		}
	}
	return false;
}

bool UDAStorySubsystem::EvaluateScheduleConditions(const TSharedPtr<FJsonObject>& Conditions) const
{
	if (!Conditions.IsValid())
	{
		return true;
	}

	TArray<TSharedPtr<FJsonObject>> AllConditions = ReadObjectArray(Conditions, TEXT("all"));
	if (AllConditions.Num() == 0)
	{
		AllConditions = ReadObjectArray(Conditions, TEXT("any"));
	}
	if (AllConditions.Num() > 0)
	{
		return EvaluateConditions(AllConditions);
	}

	FString Reason;
	return FDAEventGraph::EvaluateCondition(Conditions, ResolveProfile(), ResolveCalendar(), Reason);
}

bool UDAStorySubsystem::GetScheduledNpcLocation(const FString& NpcId, const FString& Weekday, const FString& Period,
	FString& OutLocation, FString& OutAnchor)
{
	OutLocation.Reset();
	OutAnchor.Reset();

	const TSharedPtr<FJsonObject>* NpcPtr = ScheduledNpcs.Find(NpcId);
	if (!NpcPtr || !NpcPtr->IsValid())
	{
		return false;
	}
	const TSharedPtr<FJsonObject> Npc = *NpcPtr;

	int32 BestPriority = MIN_int32;
	bool bFound = false;

	const TArray<TSharedPtr<FJsonObject>> Overrides = ReadObjectArray(Npc, TEXT("date_overrides"));
	for (const TSharedPtr<FJsonObject>& Override : Overrides)
	{
		const TSharedPtr<FJsonObject>* DateObject = nullptr;
		if (!Override->TryGetObjectField(TEXT("date"), DateObject) || !DateObject || !MatchScheduleDate(*DateObject))
		{
			continue;
		}
		if (!MatchSchedulePeriod(Override, Period))
		{
			continue;
		}
		const TSharedPtr<FJsonObject>* Conditions = nullptr;
		Override->TryGetObjectField(TEXT("conditions"), Conditions);
		if (!EvaluateScheduleConditions(Conditions ? *Conditions : TSharedPtr<FJsonObject>()))
		{
			continue;
		}

		const int32 Priority = ReadInt(Override, TEXT("priority"), 0);
		if (Priority >= BestPriority)
		{
			BestPriority = Priority;
			OutLocation = ReadString(Override, TEXT("location"));
			OutAnchor = ReadString(Override, TEXT("anchor"));
			bFound = true;
		}
	}

	const TArray<TSharedPtr<FJsonObject>> Entries = ReadObjectArray(Npc, TEXT("entries"));
	for (const TSharedPtr<FJsonObject>& Entry : Entries)
	{
		if (!MatchScheduleWeekday(Entry, Weekday) || !MatchSchedulePeriod(Entry, Period))
		{
			continue;
		}
		const TSharedPtr<FJsonObject>* Conditions = nullptr;
		Entry->TryGetObjectField(TEXT("conditions"), Conditions);
		if (!EvaluateScheduleConditions(Conditions ? *Conditions : TSharedPtr<FJsonObject>()))
		{
			continue;
		}

		const int32 Priority = ReadInt(Entry, TEXT("priority"), 0);
		if (Priority >= BestPriority)
		{
			BestPriority = Priority;
			OutLocation = ReadString(Entry, TEXT("location"));
			OutAnchor = ReadString(Entry, TEXT("anchor"));
			bFound = true;
		}
	}

	return bFound && !OutLocation.IsEmpty();
}

bool UDAStorySubsystem::GetScheduledNpcLocationNow(const FString& NpcId, FString& OutLocation, FString& OutAnchor)
{
	const UDACalendarSubsystem* Calendar = ResolveCalendar();
	if (!Calendar)
	{
		return false;
	}
	return GetScheduledNpcLocation(NpcId,
		Calendar->GetWeekdayName(Calendar->GetWeekday()),
		Calendar->GetPeriodName(Calendar->GetPeriod()),
		OutLocation, OutAnchor);
}

// ---------------------------------------------------------------------------
// Save state
// ---------------------------------------------------------------------------

FString UDAStorySubsystem::SaveState() const
{
	TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetNumberField(TEXT("version"), 1);
	Root->SetStringField(TEXT("event"), CurrentEventId);
	Root->SetStringField(TEXT("scene"), CurrentSceneId);
	Root->SetNumberField(TEXT("command"), CommandIndex);
	Root->SetBoolField(TEXT("running"), bRunning);
	Root->SetBoolField(TEXT("free_roam"), bFreeRoam);
	Root->SetBoolField(TEXT("opening_started"), bOpeningStarted);
	Root->SetStringField(TEXT("starter_deck"), SelectedStarterDeck);

	TArray<TSharedPtr<FJsonValue>> Completed;
	for (const FString& EventId : CompletedEvents)
	{
		Completed.Add(MakeShared<FJsonValueString>(EventId));
	}
	Root->SetArrayField(TEXT("completed"), Completed);

	TArray<TSharedPtr<FJsonValue>> Applied;
	for (const FString& RewardId : AppliedRewardIds)
	{
		Applied.Add(MakeShared<FJsonValueString>(RewardId));
	}
	Root->SetArrayField(TEXT("applied_rewards"), Applied);

	TSharedPtr<FJsonObject> ObjectiveObject = MakeShared<FJsonObject>();
	for (const TPair<FString, FString>& Pair : Objectives)
	{
		ObjectiveObject->SetStringField(Pair.Key, Pair.Value);
	}
	Root->SetObjectField(TEXT("objectives"), ObjectiveObject);

	FString Out;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
	if (!FJsonSerializer::Serialize(Root.ToSharedRef(), Writer))
	{
		return TEXT("{}");
	}
	return Out;
}

bool UDAStorySubsystem::LoadState(const FString& Json, FString& OutError)
{
	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		OutError = TEXT("story state is invalid JSON");
		return false;
	}

	Root->TryGetStringField(TEXT("event"), CurrentEventId);
	Root->TryGetStringField(TEXT("scene"), CurrentSceneId);
	Root->TryGetNumberField(TEXT("command"), CommandIndex);
	Root->TryGetBoolField(TEXT("running"), bRunning);
	Root->TryGetBoolField(TEXT("free_roam"), bFreeRoam);
	Root->TryGetBoolField(TEXT("opening_started"), bOpeningStarted);
	Root->TryGetStringField(TEXT("starter_deck"), SelectedStarterDeck);

	CompletedEvents.Reset();
	const TArray<TSharedPtr<FJsonValue>>* Completed = nullptr;
	if (Root->TryGetArrayField(TEXT("completed"), Completed) && Completed)
	{
		for (const TSharedPtr<FJsonValue>& Value : *Completed)
		{
			if (Value.IsValid()) CompletedEvents.Add(Value->AsString());
		}
	}

	AppliedRewardIds.Reset();
	const TArray<TSharedPtr<FJsonValue>>* Applied = nullptr;
	if (Root->TryGetArrayField(TEXT("applied_rewards"), Applied) && Applied)
	{
		for (const TSharedPtr<FJsonValue>& Value : *Applied)
		{
			if (Value.IsValid()) AppliedRewardIds.Add(Value->AsString());
		}
	}

	Objectives.Reset();
	const TSharedPtr<FJsonObject>* ObjectiveObject = nullptr;
	if (Root->TryGetObjectField(TEXT("objectives"), ObjectiveObject) && ObjectiveObject)
	{
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*ObjectiveObject)->Values)
		{
			if (Pair.Value.IsValid())
			{
				Objectives.Add(FString(*Pair.Key), Pair.Value->AsString());
			}
		}
	}

	bWaitingForDialogue = false;
	bWaitingForChoice = false;
	bWaitingForDuel = false;
	bWaitingForTimer = false;
	bPendingTextInput = false;
	WaitRemaining = 0.f;
	ActiveChoices.Reset();

	if (bRunning)
	{
		const FDAStoryScene* Scene = Scenes.Find(CurrentSceneId);
		if (!Scene)
		{
			bRunning = false;
			CurrentCommands.Reset();
			CommandIndex = 0;
		}
		else
		{
			CurrentCommands = Scene->Commands;
			CommandIndex = FMath::Clamp(CommandIndex, 0, CurrentCommands.Num());
			bPendingContinue = true;
		}
	}
	else
	{
		CurrentCommands.Reset();
		CommandIndex = 0;
	}

	OutError.Reset();
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: state loaded (event %s, scene %s, command %d)."),
		*CurrentEventId, *CurrentSceneId, CommandIndex);
	return true;
}

FString UDAStorySubsystem::GetSaveSectionName() const
{
	return TEXT("story");
}

bool UDAStorySubsystem::WriteSaveSection(TSharedPtr<FJsonObject>& OutSection) const
{
	if (!OutSection.IsValid())
	{
		OutSection = MakeShared<FJsonObject>();
	}
	OutSection->SetNumberField(TEXT("version"), 1);
	OutSection->SetStringField(TEXT("state"), SaveState());
	return true;
}

bool UDAStorySubsystem::ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError)
{
	FString State;
	if (!InSection.IsValid() || !InSection->TryGetStringField(TEXT("state"), State) || State.IsEmpty())
	{
		OutError.Reset();
		return true;
	}
	return LoadState(State, OutError);
}

// ---------------------------------------------------------------------------
// Self-test
// ---------------------------------------------------------------------------

bool UDAStorySubsystem::RunSelfTest()
{
	TArray<FString> Report;
	auto AddCheck = [&Report](const FString& Label, bool bPass, const FString& Detail)
	{
		FString Suffix;
		if (!Detail.IsEmpty())
		{
			Suffix = FString::Printf(TEXT(" (%s)"), *Detail);
		}
		Report.Add(FString::Printf(TEXT("%s %s%s"), bPass ? TEXT("PASS") : TEXT("FAIL"), *Label, *Suffix));
	};
	auto AddSimpleCheck = [&AddCheck](const FString& Label, bool bPass)
	{
		AddCheck(Label, bPass, FString());
	};

	if (!bLoaded && !LoadOpeningData())
	{
		LastSelfTestReport = TEXT("FAIL story data did not load");
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("StorySelfTest: %s"), *LastSelfTestReport);
		return false;
	}

	StartOpeningFresh();
	bHeadless = true;
	bFastForward = true;

	const double StartTime = FPlatformTime::Seconds();
	int32 Steps = 0;
	while ((bRunning || bPendingContinue) && Steps < 4096)
	{
		++Steps;
		bPendingContinue = false;
		PumpQueue();
		if (bWaitingForDuel)
		{
			SimulateDuelResult(true, false);
		}
		if (bWaitingForTimer)
		{
			WaitRemaining = 0.f;
			bWaitingForTimer = false;
		}
	}

	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();

	AddSimpleCheck(TEXT("E01 completed"), IsEventCompleteRuntime(TEXT("E01")));
	AddSimpleCheck(TEXT("E01b completed"), IsEventCompleteRuntime(TEXT("E01b")));
	AddSimpleCheck(TEXT("free roam"), bFreeRoam);
	AddSimpleCheck(TEXT("registered"), Profile && Profile->GetFlag(TEXT("registered")));
	AddSimpleCheck(TEXT("tutorial complete"), Profile && Profile->GetFlag(TEXT("tutorial_complete")));
	AddSimpleCheck(TEXT("first free roam flag"), Profile && Profile->GetFlag(TEXT("first_free_roam")));
	AddSimpleCheck(TEXT("shop unlocked"), Profile && Profile->GetFlag(TEXT("shop_unlocked")));
	AddSimpleCheck(TEXT("save unlocked"), Profile && Profile->GetFlag(TEXT("save_unlocked")));
	AddSimpleCheck(TEXT("starter deck chosen"), Profile && Profile->GetFlag(TEXT("starter_deck_chosen")));
	AddCheck(TEXT("3000 DP"), Profile && Profile->GetDP() == 3000,
		Profile ? FString::FromInt(Profile->GetDP()) : FString(TEXT("no profile")));
	AddCheck(TEXT("date is Oct 7 AM"), Calendar && Calendar->GetYear() == 1 && Calendar->GetMonthIndex() == 0
		&& Calendar->GetDay() == 7 && Calendar->GetPeriod() == EDADayPeriod::AM,
		Calendar ? Calendar->GetFullDateText() : FString(TEXT("no calendar")));
	AddCheck(TEXT("weekday is Saturday"), Calendar && Calendar->GetWeekday() == EDADayOfWeek::Saturday,
		Calendar ? Calendar->GetWeekdayName(Calendar->GetWeekday()) : FString(TEXT("no calendar")));
	AddCheck(TEXT("command guard"), Steps < 4096, FString::FromInt(Steps));

	const double Elapsed = FPlatformTime::Seconds() - StartTime;
	bool bAllPass = true;
	for (const FString& Line : Report)
	{
		if (Line.StartsWith(TEXT("FAIL")))
		{
			bAllPass = false;
		}
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("StorySelfTest: %s"), *Line);
	}
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("StorySelfTest: %s in %.3fs"),
		bAllPass ? TEXT("PASS") : TEXT("FAIL"), Elapsed);

	LastSelfTestReport = FString::Join(Report, TEXT("\n"));
	LastSelfTestReport += FString::Printf(TEXT("\n%s in %.3fs"),
		bAllPass ? TEXT("PASS") : TEXT("FAIL"), Elapsed);

	bHeadless = false;
	bFastForward = false;
	return bAllPass;
}

// ---------------------------------------------------------------------------
// Debug
// ---------------------------------------------------------------------------

void UDAStorySubsystem::DebugLogState() const
{
	LogState(TEXT("console"));
}

void UDAStorySubsystem::LogState(const FString& Prefix) const
{
	const UDAProfileSubsystem* Profile = ResolveProfile();
	const UDACalendarSubsystem* Calendar = ResolveCalendar();
	const FString DateText = Calendar ? Calendar->GetFullDateText() : FString(TEXT("<none>"));
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("StoryState[%s]: event=%s scene=%s command=%d running=%s freeRoam=%s headless=%s dp=%d date=%s"),
		*Prefix, *CurrentEventId, *CurrentSceneId, CommandIndex,
		bRunning ? TEXT("true") : TEXT("false"), bFreeRoam ? TEXT("true") : TEXT("false"),
		bHeadless ? TEXT("true") : TEXT("false"),
		Profile ? Profile->GetDP() : -1,
		*DateText);
}

// ---------------------------------------------------------------------------
// Console commands
// ---------------------------------------------------------------------------

static FAutoConsoleCommandWithWorldAndArgs GDAOpeningTestCommand(
	TEXT("da.OpeningTest"),
	TEXT("Start the A03 opening vertical slice on a fresh profile."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(World))
		{
			Story->StartOpeningFresh();
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("da.OpeningTest: story subsystem not found."));
		}
	}));

static FAutoConsoleCommandWithWorldAndArgs GDAStorySelfTestCommand(
	TEXT("da.StorySelfTest"),
	TEXT("Run the headless opening story self-test."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(World))
		{
			Story->RunSelfTest();
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("da.StorySelfTest: story subsystem not found."));
		}
	}));

static FAutoConsoleCommandWithWorldAndArgs GDAStoryStartCommand(
	TEXT("da.StoryStart"),
	TEXT("Start a story event by id (da.StoryStart E01)."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(World))
		{
			if (Args.Num() > 0)
			{
				Story->StartEvent(Args[0]);
			}
		}
	}));

static FAutoConsoleCommandWithWorldAndArgs GDAStoryNameCommand(
	TEXT("da.StoryName"),
	TEXT("Set the story/profile name (max 8 characters)."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(World))
		{
			if (Args.Num() > 0)
			{
				Story->SetPlayerName(Args[0]);
			}
		}
	}));

static FAutoConsoleCommandWithWorldAndArgs GDAStoryDeckCommand(
	TEXT("da.StoryDeck"),
	TEXT("Select a starter deck by id: fire, water or wind."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(World))
		{
			if (Args.Num() > 0)
			{
				Story->SelectStarterDeck(Args[0]);
			}
		}
	}));

static FAutoConsoleCommandWithWorldAndArgs GDAStoryAdvanceCommand(
	TEXT("da.StoryAdvance"),
	TEXT("Advance the current dialogue/queue for automation."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(World))
		{
			Story->Advance();
		}
	}));

static FAutoConsoleCommandWithWorldAndArgs GDAStoryChooseCommand(
	TEXT("da.StoryChoose"),
	TEXT("Choose a pending story option (da.StoryChoose 0)."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(World))
		{
			if (Args.Num() > 0)
			{
				Story->Choose(FCString::Atoi(*Args[0]));
			}
		}
	}));

static FAutoConsoleCommandWithWorldAndArgs GDAStoryStateCommand(
	TEXT("da.StoryState"),
	TEXT("Log the current story state."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(World))
		{
			Story->DebugLogState();
		}
	}));
