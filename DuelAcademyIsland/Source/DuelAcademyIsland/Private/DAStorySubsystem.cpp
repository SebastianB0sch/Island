// Duel Academy Island - story runtime implementation.

#include "DAStorySubsystem.h"

#include "DAEventGraph.h"
#include "DAHUD.h"
#include "DADialogueUI.h"
#include "DADuelUI.h"
#include "DAProfileSubsystem.h"
#include "DACalendarSubsystem.h"
#include "DADeckLogic.h"
#include "DAInventorySubsystem.h"
#include "DAShopSubsystem.h"
#include "DAIslandSubsystem.h"
#include "DASceneAnchor.h"
#include "DAStudentNPC.h"
#include "DATitleSystem.h"
#include "DAJson.h"
#include "DuelAcademyIsland.h"

#include "Camera/PlayerCameraManager.h"
#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "EngineUtils.h"
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
#include "Templates/Function.h"

namespace
{
	const TCHAR* const DefaultPlayerName = TEXT("ALEX");

	FString ReadArg(const TArray<FString>& Args, int32 Index)
	{
		return Args.IsValidIndex(Index) ? Args[Index] : FString();
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

	/** Normalize NPC display names, roster ids and trigger ids to one story id. */
	FString NormalizeStoryNpcId(const FString& Raw)
	{
		FString Id = Raw.TrimStartAndEnd().ToLower();
		Id.ReplaceInline(TEXT("."), TEXT(""));
		Id.ReplaceInline(TEXT("'"), TEXT(""));
		Id.ReplaceInline(TEXT("-"), TEXT("_"));
		Id.ReplaceInline(TEXT(" "), TEXT("_"));
		while (Id.Contains(TEXT("__")))
		{
			Id.ReplaceInline(TEXT("__"), TEXT("_"));
		}
		if (Id.StartsWith(TEXT("dr_")))
		{
			Id = Id.RightChop(3);
		}
		if (Id == TEXT("alexis_rhodes")) return TEXT("alexis");
		if (Id == TEXT("syrus_truesdale")) return TEXT("syrus");
		if (Id == TEXT("jaden_yuki")) return TEXT("jaden");
		if (Id == TEXT("chumley_huffington")) return TEXT("chumley");
		if (Id == TEXT("lyman_banner")) return TEXT("banner");
		if (Id == TEXT("chancellor_sheppard")) return TEXT("sheppard");
		if (Id == TEXT("nurse_fontaine") || Id == TEXT("miss_fontaine")) return TEXT("fontaine");
		if (Id == TEXT("shadow_duelist") || Id == TEXT("titan")) return TEXT("shadow_duelist");
		if (Id == TEXT("goblin_king")) return TEXT("goblin_king");
		if (Id == TEXT("cyber_angel")) return TEXT("alexis");
		return Id;
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
	bAutoFullSelfTestRequested = FParse::Param(FCommandLine::Get(), TEXT("DAFullStorySelfTest"));

	TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateUObject(this, &UDAStorySubsystem::Tick));

	LoadOpeningData();
	LoadFullCampaignData();
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
	// LoadContentJsonObject resolves paths relative to the content directory.
	// Keep this relative so packaged builds (where ProjectContentDir is itself
	// relative) do not combine the content directory twice.
	const FString Path = FPaths::Combine(TEXT("Data/Story"), RelativePath);
	return LoadContentJsonObject(Path, Out, OutError);
}

bool UDAStorySubsystem::LoadContentJsonObject(const FString& RelativeToContentData, TSharedPtr<FJsonObject>& Out, FString& OutError) const
{
	const FString ContentDir = FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir());
	const FString Path = FPaths::IsRelative(RelativeToContentData)
		? FPaths::Combine(ContentDir, RelativeToContentData)
		: RelativeToContentData;
	return DAJson::LoadObjectFile(Path, Out, OutError);
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
	ParseRewards(OpeningRoot, false);

	FString ScenesPath = TEXT("scenes/opening.json");
	FString DialoguePath = TEXT("dialogue/opening.json");
	FString SchedulesPath = TEXT("schedules/opening.json");
	const TSharedPtr<FJsonObject>* FilesObject = nullptr;
	if (OpeningRoot->TryGetObjectField(TEXT("files"), FilesObject) && FilesObject)
	{
		ScenesPath = DAJson::ReadString(*FilesObject, TEXT("scenes"), ScenesPath);
		DialoguePath = DAJson::ReadString(*FilesObject, TEXT("dialogue"), DialoguePath);
		SchedulesPath = DAJson::ReadString(*FilesObject, TEXT("schedules"), SchedulesPath);
	}

	TSharedPtr<FJsonObject> ScenesRoot;
	if (LoadJsonObject(ScenesPath, ScenesRoot, Error))
	{
		ParseScenes(ScenesRoot, false);
	}
	else
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: %s"), *Error);
	}

	TSharedPtr<FJsonObject> DialogueRoot;
	if (LoadJsonObject(DialoguePath, DialogueRoot, Error))
	{
		ParseDialogue(DialogueRoot, false);
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

bool UDAStorySubsystem::LoadFullCampaignData()
{
	if (bFullCampaignLoaded)
	{
		return true;
	}
	if (!bLoaded && !LoadOpeningData())
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: full campaign cannot load before the opening bundle."));
		return false;
	}

	FString Error;
	TSharedPtr<FJsonObject> EventsRoot;
	if (!LoadJsonObject(TEXT("events.json"), EventsRoot, Error))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: full campaign events unavailable: %s"), *Error);
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* EventValues = nullptr;
	if (EventsRoot->TryGetArrayField(TEXT("events"), EventValues) && EventValues)
	{
		FullCampaignEventIds.Reset();
		FullCampaignEventDocs.Reset();
		for (const TSharedPtr<FJsonValue>& Value : *EventValues)
		{
			const TSharedPtr<FJsonObject> EventJson = Value.IsValid() ? Value->AsObject() : TSharedPtr<FJsonObject>();
			if (EventJson.IsValid())
			{
				const FString EventId = DAJson::ReadString(EventJson, TEXT("id"));
				if (!EventId.IsEmpty())
				{
					FullCampaignEventIds.Add(EventId);
					FullCampaignEventDocs.Add(EventId, EventJson);
				}
			}
		}
	}

	// opening.json is authoritative for E01: keep its trigger, scene and outcomes.
	TSet<FString> Excluded;
	Excluded.Add(TEXT("E01"));
	int32 Added = 0;
	if (!EventGraph.MergeFromJson(EventsRoot, Excluded, Error, Added))
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: full campaign event merge failed: %s"), *Error);
		return false;
	}

	TSharedPtr<FJsonObject> ScenesRoot;
	if (LoadJsonObject(TEXT("scenes/full_campaign.json"), ScenesRoot, Error))
	{
		ParseScenes(ScenesRoot, true);
	}
	else
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: %s"), *Error);
	}

	TSharedPtr<FJsonObject> DialogueRoot;
	if (LoadJsonObject(TEXT("dialogue/full_campaign.json"), DialogueRoot, Error))
	{
		ParseDialogue(DialogueRoot, true);
	}
	else
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: %s"), *Error);
	}

	TSharedPtr<FJsonObject> EmailsRoot;
	if (LoadJsonObject(TEXT("emails.json"), EmailsRoot, Error))
	{
		ParseEmails(EmailsRoot);
	}
	else
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: %s"), *Error);
	}

	bFullCampaignLoaded = Added > 0 && FullCampaignEventIds.Num() > 0;
	UE_LOG(LogDuelAcademyIsland, Log,
		TEXT("Story: loaded full campaign (%d canonical ids, %d merged events, %d scenes, %d lines, %d email contacts)."),
		FullCampaignEventIds.Num(), Added, Scenes.Num(), Lines.Num(), EmailContacts.Num());
	return bFullCampaignLoaded;
}

void UDAStorySubsystem::ParseEvents(const TSharedPtr<FJsonObject>& Root)
{
	FString Error;
	if (!EventGraph.LoadFromJson(Root, Error))
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: event graph load failed: %s"), *Error);
	}
}

void UDAStorySubsystem::ParseScenes(const TSharedPtr<FJsonObject>& Root, bool bMerge)
{
	if (!bMerge)
	{
		Scenes.Reset();
	}
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
		Scene.Id = DAJson::ReadString(SceneJson, TEXT("id"), FString(*Pair.Key));
		Scene.EventId = DAJson::ReadString(SceneJson, TEXT("event_id"), DAJson::ReadString(SceneJson, TEXT("event")));
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
				Command.Type = ParseCommandType(DAJson::ReadString(CommandJson, TEXT("type")));
				Command.CommandId = DAJson::ReadString(CommandJson, TEXT("command_id"));
				Command.Key = DAJson::ReadString(CommandJson, TEXT("key"), DAJson::ReadString(CommandJson, TEXT("text_key")));
				Command.Speaker = DAJson::ReadString(CommandJson, TEXT("speaker"));
				Command.Portrait = DAJson::ReadString(CommandJson, TEXT("portrait"));
				Command.TextKey = DAJson::ReadString(CommandJson, TEXT("text_key"), Command.Key);
				Command.Anchor = DAJson::ReadString(CommandJson, TEXT("anchor"));
				Command.Npc = DAJson::ReadString(CommandJson, TEXT("npc"));
				Command.Title = DAJson::ReadString(CommandJson, TEXT("title"));
				Command.Subtitle = DAJson::ReadString(CommandJson, TEXT("subtitle"));
				Command.Style = DAJson::ReadString(CommandJson, TEXT("style"));
				Command.Sfx = DAJson::ReadString(CommandJson, TEXT("sfx"));
				Command.Track = DAJson::ReadString(CommandJson, TEXT("track"));
				Command.OpponentId = DAJson::ReadString(CommandJson, TEXT("opponent_id"), DAJson::ReadString(CommandJson, TEXT("opponent")));
				Command.OpponentName = DAJson::ReadString(CommandJson, TEXT("opponent_name"));
				Command.OpponentDeckId = DAJson::ReadString(CommandJson, TEXT("opponent_deck_id"), DAJson::ReadString(CommandJson, TEXT("deck")));
				Command.Mode = DAJson::ReadString(CommandJson, TEXT("mode"));
				Command.ScenarioId = DAJson::ReadString(CommandJson, TEXT("scenario_id"));
				Command.OnWin = DAJson::ReadString(CommandJson, TEXT("on_win"));
				Command.OnLose = DAJson::ReadString(CommandJson, TEXT("on_lose"));
				Command.OnDraw = DAJson::ReadString(CommandJson, TEXT("on_draw"));
				Command.NextScene = DAJson::ReadString(CommandJson, TEXT("next_scene"));
				Command.RewardId = DAJson::ReadString(CommandJson, TEXT("reward_id"));
				Command.FlagName = DAJson::ReadString(CommandJson, TEXT("flag"));
				Command.Dp = DAJson::ReadInt(CommandJson, TEXT("dp"), 0);
				Command.TurnLimit = DAJson::ReadInt(CommandJson, TEXT("turn_limit"), 0);
				Command.bOptional = DAJson::ReadBool(CommandJson, TEXT("optional"), false);
				Command.bTutorial = DAJson::ReadBool(CommandJson, TEXT("tutorial"), false);
				Command.bCountsAsWin = DAJson::ReadBool(CommandJson, TEXT("counts_as_win"), false);
				const FString AwardDp = DAJson::ReadString(CommandJson, TEXT("award_dp"));
				Command.bAwardDP = !AwardDp.Equals(TEXT("none"), ESearchCase::IgnoreCase);
				Command.bCompleteEvent = DAJson::ReadBool(CommandJson, TEXT("complete_event"), true);
				Command.bEnterFreeRoam = DAJson::ReadBool(CommandJson, TEXT("enter_free_roam"), false);
				Command.bSkippable = DAJson::ReadBool(CommandJson, TEXT("skippable"), true);
				Command.Duration = DAJson::ReadFloat(CommandJson, TEXT("duration"), 0.f);

				const TArray<FString> Args = DAJson::ReadStringArray(CommandJson, TEXT("args"));
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
					Command.NextScene = DAJson::ReadString(CommandJson, TEXT("next_scene"));
				}

				Command.bFlagValue = DAJson::ReadBool(CommandJson, TEXT("value"), true);

				Scene.Commands.Add(Command);
			}
		}

		// Duplicate ids overwrite each other in this map; warn exactly like
		// MergeFromJson does for duplicate event ids so a data collision is
		// never silent.
		if (Scenes.Contains(Scene.Id))
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: duplicate scene id %s overwritten."), *Scene.Id);
		}
		Scenes.Add(Scene.Id, Scene);
	}
}

void UDAStorySubsystem::ParseDialogue(const TSharedPtr<FJsonObject>& Root, bool bMerge)
{
	if (!bMerge)
	{
		Lines.Reset();
		SpeakerNames.Reset();
		SpeakerColors.Reset();
	}

	const TSharedPtr<FJsonObject>* SpeakersObject = nullptr;
	if (Root->TryGetObjectField(TEXT("speakers"), SpeakersObject) && SpeakersObject)
	{
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*SpeakersObject)->Values)
		{
			const TSharedPtr<FJsonObject> SpeakerJson = Pair.Value.IsValid() ? Pair.Value->AsObject() : TSharedPtr<FJsonObject>();
			if (SpeakerJson.IsValid())
			{
				const FString SpeakerId(*Pair.Key);
				SpeakerNames.Add(SpeakerId, DAJson::ReadString(SpeakerJson, TEXT("display_name"), SpeakerId));
				SpeakerColors.Add(SpeakerId, ColorFromHex(DAJson::ReadString(SpeakerJson, TEXT("color"))));
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
		Line.Key = DAJson::ReadString(LineJson, TEXT("key"), FString(*Pair.Key));
		Line.Speaker = DAJson::ReadString(LineJson, TEXT("speaker"));
		Line.Portrait = DAJson::ReadString(LineJson, TEXT("portrait"));
		Line.Expression = DAJson::ReadString(LineJson, TEXT("expression"), TEXT("neutral"));
		Line.Text = DAJson::ReadString(LineJson, TEXT("text"));
		Line.Next = DAJson::ReadString(LineJson, TEXT("next"));
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
				Choice.Id = DAJson::ReadString(ChoiceJson, TEXT("id"));
				Choice.Text = DAJson::ReadString(ChoiceJson, TEXT("text"));
				Choice.NextScene = DAJson::ReadString(ChoiceJson, TEXT("next_scene"));
				Choice.NextKey = DAJson::ReadString(ChoiceJson, TEXT("next_key"));
				Choice.Requirements = DAJson::ReadObjectArray(ChoiceJson, TEXT("requirements"));
				Choice.Outcomes = DAJson::ReadObjectArray(ChoiceJson, TEXT("outcomes"));
				Choice.Raw = ChoiceJson;
				Line.Choices.Add(Choice);
			}
		}

		// Duplicate dialogue keys overwrite each other in this map; warn exactly
		// like MergeFromJson does for duplicate event ids.
		if (Lines.Contains(Line.Key))
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: duplicate dialogue key %s overwritten."), *Line.Key);
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
			const FString NpcId = DAJson::ReadString(NpcJson, TEXT("npc"), DAJson::ReadString(NpcJson, TEXT("id")));
			if (!NpcId.IsEmpty())
			{
				ScheduledNpcs.Add(NpcId, NpcJson);
			}
		}
	}
}

void UDAStorySubsystem::ParseRewards(const TSharedPtr<FJsonObject>& Root, bool bMerge)
{
	if (!bMerge)
	{
		Rewards.Reset();
	}
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

void UDAStorySubsystem::ParseEmails(const TSharedPtr<FJsonObject>& Root)
{
	EmailContacts.Reset();
	const TArray<TSharedPtr<FJsonValue>>* ContactValues = nullptr;
	if (Root->TryGetArrayField(TEXT("contacts"), ContactValues) && ContactValues)
	{
		for (const TSharedPtr<FJsonValue>& Value : *ContactValues)
		{
			const TSharedPtr<FJsonObject> ContactJson = Value.IsValid() ? Value->AsObject() : TSharedPtr<FJsonObject>();
			if (!ContactJson.IsValid())
			{
				continue;
			}
			const FString ContactId = DAJson::ReadString(ContactJson, TEXT("contact"), DAJson::ReadString(ContactJson, TEXT("id")));
			if (!ContactId.IsEmpty())
			{
				EmailContacts.Add(ContactId, ContactJson);
			}
		}
	}

	const TSharedPtr<FJsonObject>* MessagesObject = nullptr;
	if (Root->TryGetObjectField(TEXT("messages"), MessagesObject) && MessagesObject)
	{
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*MessagesObject)->Values)
		{
			const FString ContactId(*Pair.Key);
			if (!EmailContacts.Contains(ContactId) && Pair.Value.IsValid() && Pair.Value->AsObject().IsValid())
			{
				EmailContacts.Add(ContactId, Pair.Value->AsObject());
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
	AppliedOutcomeKeys.Reset();
	UnlockedDuels.Reset();
	Objectives.Reset();
	PendingPackGrants.Reset();

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
	PreviousTitle.Reset();
	PendingDuel = FDAStoryPendingDuel();
	bResumePendingDuel = false;
	DuelOpenRetryTimer = 0.f;
}

void UDAStorySubsystem::StartOpening()
{
	if (bRunning)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: StartOpening ignored; %s is already running."), *CurrentEventId);
		return;
	}
	if (ADAHUD* HUD = ResolveHUD())
	{
		if (HUD->IsDuelOpen())
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: StartOpening ignored; a duel is open."));
			return;
		}
	}
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

	if (!IsEventCompleteRuntime(TEXT("E01")))
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
	if (ADAHUD* HUD = ResolveHUD())
	{
		HUD->CloseDialogue();
	}

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
	if (ADAHUD* HUD = ResolveHUD())
	{
		if (HUD->IsDuelOpen())
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: StartOpeningFresh ignored; a duel is open."));
			return;
		}
	}
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
	if (ADAHUD* HUD = ResolveHUD())
	{
		HUD->CloseDialogue();
	}
	// A fresh opening is a new campaign, not a continuation in the same
	// GameInstance. Reset the economy before the starter-deck command runs so
	// a second new game cannot inherit the previous trunk, decks or purchases.
	if (UGameInstance* GameInstance = GetGameInstance())
	{
		if (UDAInventorySubsystem* Inventory = GameInstance->GetSubsystem<UDAInventorySubsystem>())
		{
			Inventory->ResetCollection();
		}
		if (UDAShopSubsystem* Shop = GameInstance->GetSubsystem<UDAShopSubsystem>())
		{
			// Preserve the HUD wallet handlers; ResetPurchaseState() clears them.
			Shop->ResetSaveSectionState();
		}
		if (UDADeckLogic* Decks = GameInstance->GetSubsystem<UDADeckLogic>())
		{
			Decks->ResetToDefaults();
		}
	}
	bHeadless = ResolveHUD() == nullptr;
	Profile->InitializeNewGame(DefaultPlayerName);
	Calendar->SetDate(1, 0, 1, EDADayPeriod::AM);
	Profile->SetFlag(TEXT("new_game_started"), true);
	bOpeningStarted = true;
	StartEvent(TEXT("E01"));
}

void UDAStorySubsystem::StartEvent(const FString& EventId)
{
	FString Reason;
	if (!CanStartEvent(EventId, Reason))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: cannot start %s: %s"), *EventId, *Reason);
		return;
	}

	const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
	if (!Event)
	{
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

bool UDAStorySubsystem::CanStartEvent(const FString& EventId, FString& OutReason)
{
	if (!bLoaded && !LoadOpeningData())
	{
		OutReason = TEXT("story data is not loaded");
		return false;
	}
	if (bRunning)
	{
		OutReason = FString::Printf(TEXT("event %s is already running"), *CurrentEventId);
		return false;
	}

	const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
	if (!Event)
	{
		OutReason = FString::Printf(TEXT("unknown event %s"), *EventId);
		return false;
	}
	if (Event->bOnce && IsEventCompleteRuntime(EventId))
	{
		OutReason = FString::Printf(TEXT("event %s is already complete"), *EventId);
		return false;
	}
	if (!Scenes.Contains(Event->Scene))
	{
		OutReason = FString::Printf(TEXT("scene %s is not loaded"), *Event->Scene);
		return false;
	}
	if (!EventGraph.EvaluateRequirements(*Event, ResolveProfile(), ResolveCalendar(), OutReason))
	{
		return false;
	}
	if (!EventGraph.EvaluateTrigger(*Event, ResolveProfile(), ResolveCalendar(), OutReason))
	{
		return false;
	}

	OutReason.Reset();
	return true;
}

bool UDAStorySubsystem::NotifyTalkToNPC(const FString& NpcId)
{
	if (bRunning)
	{
		return false;
	}
	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	if (!Profile || !Calendar)
	{
		return false;
	}

	const FString Id = NormalizeStoryNpcId(NpcId);
	if (Id.IsEmpty())
	{
		return false;
	}

	// Talking is also how the player meets a character. This makes met_* gates
	// and the email/duel-request unlocks behave like the GBA flow.
	Profile->SetFlag(FString::Printf(TEXT("met_%s"), *Id), true);

	const TArray<FString> Available = EventGraph.GetAvailableEvents(Profile, Calendar);
	for (const FString& EventId : Available)
	{
		const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
		if (!Event || !Event->Trigger.IsValid())
		{
			continue;
		}
		if (!DAJson::ReadString(Event->Trigger, TEXT("type")).Equals(TEXT("talk"), ESearchCase::IgnoreCase))
		{
			continue;
		}
		const FString TriggerNpc = NormalizeStoryNpcId(DAJson::ReadString(Event->Trigger, TEXT("npc")));
		if (TriggerNpc != Id)
		{
			continue;
		}

		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: talk to %s starts %s."), *Id, *EventId);
		StartEvent(EventId);
		return IsRunning() && GetCurrentEventId().Equals(EventId, ESearchCase::IgnoreCase);
	}
	return false;
}

void UDAStorySubsystem::NotifyWalkHome(const FString& PartnerId)
{
	UDAProfileSubsystem* Profile = ResolveProfile();
	if (!Profile)
	{
		return;
	}
	const FString Id = NormalizeStoryNpcId(PartnerId);
	if (Id.IsEmpty())
	{
		return;
	}
	const int32 Count = Profile->IncrementCounter(FString::Printf(TEXT("walk_home_%s"), *Id), 1);
	Profile->IncrementCounter(TEXT("walk_home_total"), 1);
	Profile->SetFlag(FString::Printf(TEXT("walk_home_%s_%d"), *Id, Count), true);
	if (Count >= 3)
	{
		Profile->SetFlag(TEXT("walk_home_partner_3"), true);
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: walked home with %s three times."), *Id);
	}
}

void UDAStorySubsystem::NotifyRoomStay()
{
	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	if (!Profile || !Calendar)
	{
		return;
	}
	const EDADayOfWeek Weekday = Calendar->GetWeekday();
	if (Weekday != EDADayOfWeek::Saturday && Weekday != EDADayOfWeek::Sunday)
	{
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: room stay only counts on weekends."));
		return;
	}

	// Count one stay per weekend, not one per weekend day. Saturday is the key;
	// Sunday shares the same key.
	const int32 WeekendKey = Calendar->GetAbsoluteDay() - (Weekday == EDADayOfWeek::Sunday ? 1 : 0);
	const FString WeekendFlag = FString::Printf(TEXT("room_stay_weekend_%d"), WeekendKey);
	if (Profile->GetFlag(WeekendFlag))
	{
		return;
	}
	Profile->SetFlag(WeekendFlag, true);
	const int32 Count = Profile->IncrementCounter(TEXT("room_stay_weekends"), 1);
	if (Count >= 3)
	{
		Profile->SetFlag(TEXT("stayed_in_room_three_weekends"), true);
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: stayed in the room for three weekends."));
	}
}

void UDAStorySubsystem::TryStartNextAvailableEvent()
{
	if (bSuppressAutoStart)
	{
		return;
	}
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
		const FString TriggerType = DAJson::ReadString(Event->Trigger, TEXT("type"));
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
		++PlaythroughMissingScene;
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: missing scene %s."), *SceneId);
		FinishEvent(false, false);
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
	bPendingTextInput = false;
	WaitRemaining = 0.f;
	ActiveChoices.Reset();
	ActiveChoiceConversationId.Reset();
	ActiveChoiceLineKey.Reset();
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

	// Return the camera and fade state to gameplay before another event starts.
	if (!bHeadless)
	{
		UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
		APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
		if (PC)
		{
			if (APawn* Pawn = PC->GetPawn())
			{
				PC->SetViewTargetWithBlend(Pawn, 0.25f, VTBlend_Cubic);
			}
			if (PC->PlayerCameraManager)
			{
				PC->PlayerCameraManager->StopCameraFade();
			}
		}
	}

	bRunning = false;
	bWaitingForDialogue = false;
	bWaitingForChoice = false;
	bWaitingForDuel = false;
	bWaitingForTimer = false;
	bPendingTextInput = false;
	bResumePendingDuel = false;
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

	if (bAutoFullSelfTestRequested && !bAutoFullSelfTestStarted)
	{
		AutoStartDelay -= DeltaSeconds;
		if (AutoStartDelay <= 0.f)
		{
			bAutoFullSelfTestStarted = true;
			RunFullStorySelfTest();
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
		DuelOpenRetryTimer = FMath::Max(0.f, DuelOpenRetryTimer - DeltaSeconds);
		if (ADAHUD* HUD = ResolveHUD())
		{
			const FDADuelUI* DuelUI = HUD->GetDuelUI();
			switch (DecidePendingDuelTick(
				HUD->IsDuelOpen(),
				DuelUI && DuelUI->WasDeckSelectClosedWithoutResult(),
				HUD->IsModalOpen(),
				bResumePendingDuel,
				PendingDuel.bOpened,
				PendingDuel.Elapsed,
				DuelOpenRetryTimer))
			{
			case EDAStoryDuelTickDecision::None:
			{
				if (HUD->IsDuelOpen())
				{
					PendingDuel.bOpened = true;
					bResumePendingDuel = false;
					DuelOpenRetryTimer = 0.f;
				}
				break;
			}
			case EDAStoryDuelTickDecision::Reopen:
			{
				// P4-02: the deck select ended without recording a duel result
				// (the player backed out). Re-present the same selector instead
				// of inferring a phantom loss from unchanged counters.
				UE_LOG(LogDuelAcademyIsland, Log,
					TEXT("Story: duel vs %s closed without a result; re-presenting the deck select."),
					*PendingDuel.OpponentId);
				bResumePendingDuel = false;
				PendingDuel.bOpened = false;
				PendingDuel.Elapsed = 0.f;
				DuelOpenRetryTimer = 0.5f;
				OpenPendingDuelDeckSelect(*HUD);
				break;
			}
			case EDAStoryDuelTickDecision::RetryRequest:
				// P4-03: the initial ask can be silently refused by the HUD
				// (title screen open, another duel...). Re-issue it on a short
				// interval; the 10s loss timer is only the last resort.
				DuelOpenRetryTimer = 0.5f;
				OpenPendingDuelDeckSelect(*HUD);
				break;
			case EDAStoryDuelTickDecision::ResolveInferred:
			{
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
						// Any recorded win counts, not only wins against Jaden.
						bWon = Profile->GetCounter(TEXT("wins_total")) > PendingDuel.PreWinsTotal;
					}
				}
				ResolvePendingDuel(bWon, bDraw);
				break;
			}
			case EDAStoryDuelTickDecision::ResolveLoss:
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: duel UI did not open; treating as a loss."));
				ResolvePendingDuel(false, false);
				break;
			}
		}
		else if (!bResumePendingDuel && PendingDuel.Elapsed > 1.f)
		{
			ResolvePendingDuel(false, false);
		}
		else if (bResumePendingDuel && PendingDuel.Elapsed > 10.f)
		{
			// A restored pending duel with no HUD to present it would otherwise
			// wait forever. Mirror the "duel UI did not open" fallback above so a
			// headless/dedicated load cannot soft-lock the event queue.
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("Story: no HUD to resume the saved pending duel; treating it as a loss."));
			ResolvePendingDuel(false, false);
		}
	}

	if (bPendingContinue && !bWaitingForDialogue && !bWaitingForChoice && !bWaitingForDuel
		&& !bWaitingForTimer && !bPendingTextInput)
	{
		bPendingContinue = false;
		PumpQueue();
	}

	// date/flag/event events can become eligible while the player is walking
	// around. Poll outside modal UI so the campaign does not wait for the next
	// scene transition to start them.
	if (!bRunning && bFreeRoam && !bSuppressAutoStart && !bManualAudience && !bHeadless)
	{
		FreeRoamPollTimer -= DeltaSeconds;
		if (FreeRoamPollTimer <= 0.f)
		{
			FreeRoamPollTimer = 1.f;
			ADAHUD* HUD = ResolveHUD();
			if (!HUD || !HUD->IsModalOpen())
			{
				TryStartNextAvailableEvent();
			}
		}
	}

	// The post-game gate is the end of the 12-month school year, or completing
	// every mandatory canonical event except the King of Games finale.
	if (UDAProfileSubsystem* Profile = ResolveProfile())
	{
		if (!Profile->GetFlag(TEXT("post_game")))
		{
			bool bAllCanonComplete = true;
			for (const FDAEventDefinition& Event : EventGraph.GetEvents())
			{
				if (Event.bCanonEvent && !Event.bOptional
					&& !Event.Id.Equals(TEXT("E33"), ESearchCase::IgnoreCase)
					&& !EventGraph.IsEventComplete(Event.Id, Profile))
				{
					bAllCanonComplete = false;
					break;
				}
			}
			const UDACalendarSubsystem* Calendar = ResolveCalendar();
			if (bAllCanonComplete || (Calendar && Calendar->GetYear() >= 2))
			{
				Profile->SetFlag(TEXT("post_game"), true);
				UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: post-game gate opened (year %d)."),
					Calendar ? Calendar->GetYear() : 0);
			}
		}
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
		++PlaythroughDialogueCommands;
		const FDAStoryLine* Line = FindLine(Command.Key);
		if (!Line)
		{
			++PlaythroughMissingDialogue;
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: missing dialogue line %s."), *Command.Key);
			return true;
		}
		if (bManualAudience)
		{
			bWaitingForDialogue = true;
			bOutBlocked = true;
			return false;
		}
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
		++PlaythroughChoiceCommands;
		const FDAStoryLine* Line = FindLine(Command.Key);
		if (!Line)
		{
			++PlaythroughMissingDialogue;
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: missing choice line %s."), *Command.Key);
			return true;
		}

		if (Line->Input.IsValid())
		{
			if (bManualAudience)
			{
				bPendingTextInput = true;
				PendingTextInputKey = Line->Key;
				bWaitingForDialogue = true;
				bOutBlocked = true;
				return false;
			}
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
		ActiveChoiceLineKey = Line->Key;

		if (bManualAudience)
		{
			ActiveChoiceConversationId = FString::Printf(TEXT("%s.choice.%d"), *CurrentSceneId, CommandIndex);
			bWaitingForChoice = true;
			bOutBlocked = true;
			return false;
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
	{
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: camera anchor %s (%.2fs)."), *Command.Anchor, Command.Duration);
		if (!bHeadless)
		{
			UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
			APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
			if (PC && World)
			{
				for (TActorIterator<ADASceneAnchor> It(World); It; ++It)
				{
					if (It->AnchorId.Equals(Command.Anchor, ESearchCase::IgnoreCase))
					{
						PC->SetViewTargetWithBlend(*It, Command.Duration > 0.f ? Command.Duration : 0.25f, VTBlend_Cubic);
						break;
					}
				}
			}
		}
		return true;
	}

	case EDAStoryCommandType::MoveNpc:
	{
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: move %s to %s (%.2fs)."), *Command.Npc, *Command.Anchor, Command.Duration);
		if (!bHeadless)
		{
			UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
			if (World)
			{
				ADASceneAnchor* Target = nullptr;
				for (TActorIterator<ADASceneAnchor> It(World); It; ++It)
				{
					if (It->AnchorId.Equals(Command.Anchor, ESearchCase::IgnoreCase))
					{
						Target = *It;
						break;
					}
				}
				if (Target)
				{
					for (TActorIterator<ADAStudentNPC> It(World); It; ++It)
					{
						if (It->DuelOpponentId.Equals(Command.Npc, ESearchCase::IgnoreCase)
							|| It->GetInteractName().Contains(Command.Npc, ESearchCase::IgnoreCase))
						{
							It->SetActorLocation(Target->GetActorLocation() + FVector(0, 0, 90),
								false, nullptr, ETeleportType::TeleportPhysics);
							break;
						}
					}
				}
			}
		}
		return true;
	}

	case EDAStoryCommandType::Fade:
	{
		const FString Mode = DAJson::ReadString(Command.Raw, TEXT("mode"), TEXT("out"));
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: fade %s (%.2fs)."), *Mode, Command.Duration);
		if (!bHeadless)
		{
			UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
			APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
			if (PC && PC->PlayerCameraManager)
			{
				const bool bIn = Mode.Equals(TEXT("in"), ESearchCase::IgnoreCase);
				PC->PlayerCameraManager->StartCameraFade(bIn ? 1.f : 0.f, bIn ? 0.f : 1.f,
					FMath::Max(0.05f, Command.Duration), FLinearColor::Black, false, true);
			}
		}
		return true;
	}

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
	{
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: banner '%s' - '%s'."), *Command.Title, *Command.Subtitle);
		if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
		{
			FDAMessage Msg;
			Msg.Title = Command.Title;
			Msg.Body = Command.Subtitle;
			Msg.Accent = FLinearColor(1.f, 0.78f, 0.25f);
			Msg.Duration = Command.Duration > 0.f ? Command.Duration : 4.f;
			Sub->PushMessage(Msg);
		}
		return true;
	}

	case EDAStoryCommandType::PlaySfx:
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: sfx %s."), *Command.Sfx);
		if (!Command.Sfx.IsEmpty())
		{
			if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
			{
				Sub->PlayUISound(FName(*Command.Sfx), 1.f);
			}
		}
		return true;

	case EDAStoryCommandType::Music:
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: music %s."), *Command.Track);
		if (!Command.Track.IsEmpty())
		{
			if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
			{
				Sub->PlayUISound(FName(*Command.Track), 0.55f);
			}
		}
		return true;

	case EDAStoryCommandType::Duel:
	{
		++PlaythroughDuelCommands;
		FDAStoryCommand Resolved = Command;
		if (Command.Raw.IsValid())
		{
			const TSharedPtr<FJsonObject>* ByDorm = nullptr;
			if (Command.Raw->TryGetObjectField(TEXT("opponent_by_dorm"), ByDorm) && ByDorm)
			{
				FString DormKey = TEXT("slifer");
				if (const UDAProfileSubsystem* Profile = ResolveProfile())
				{
					if (Profile->GetDorm() == EDADorm::Ra)
					{
						DormKey = TEXT("ra");
					}
					else if (Profile->GetDorm() == EDADorm::Obelisk)
					{
						DormKey = TEXT("obelisk");
					}
				}
				const TSharedPtr<FJsonObject>* Entry = nullptr;
				if ((*ByDorm)->TryGetObjectField(DormKey, Entry) && Entry)
				{
					const FString Id = DAJson::ReadString(*Entry, TEXT("id"));
					const FString Name = DAJson::ReadString(*Entry, TEXT("name"));
					const FString Deck = DAJson::ReadString(*Entry, TEXT("deck"));
					if (!Id.IsEmpty()) Resolved.OpponentId = Id;
					if (!Name.IsEmpty()) Resolved.OpponentName = Name;
					if (!Deck.IsEmpty()) Resolved.OpponentDeckId = Deck;
					UE_LOG(LogDuelAcademyIsland, Log,
						TEXT("Story: E11 dorm branch %s -> %s (%s)."), *DormKey, *Resolved.OpponentId, *Resolved.OpponentDeckId);
				}
			}
		}
		CapturePendingDuel(Resolved);
		if (bManualAudience)
		{
			bWaitingForDuel = true;
			PendingDuel.bOpened = false;
			PendingDuel.Elapsed = 0.f;
			bOutBlocked = true;
			return false;
		}
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
			*Resolved.OpponentId, *Resolved.OpponentDeckId);
		const FString DuelMode = Resolved.bTutorial ? TEXT("tutorial") : Resolved.Mode;
		HUD->OpenDuelDeckSelect(Resolved.OpponentId, Resolved.OpponentName, Resolved.OpponentDeckId,
			DuelMode, Resolved.bAwardDP);
		bOutBlocked = true;
		return false;
	}

	case EDAStoryCommandType::Reward:
		++PlaythroughRewardCommands;
		ApplyRewardCommand(Command);
		return true;

	case EDAStoryCommandType::SetFlag:
		++PlaythroughFlagCommands;
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
		++PlaythroughUnknownCommand;
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: unsupported command type %s."), *CommandTypeName(Command.Type));
		return true;
	}
}

void UDAStorySubsystem::Advance()
{
	if (bWaitingForDialogue)
	{
		if (bPendingTextInput)
		{
			// Automation/headless path: no text-entry widget exists, so confirm
			// the current profile name exactly like HandleDialogueClosed does.
			SetPlayerName(GetPlayerNameForDisplay());
			bPendingTextInput = false;
			PendingTextInputKey.Reset();
		}
		if (!bManualAudience)
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

	if (!bManualAudience)
	{
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
		FString EnteredName;
		if (ADAHUD* HUD = ResolveHUD())
		{
			if (FDADialogueUI* Dialogue = HUD->GetDialogueUI())
			{
				EnteredName = Dialogue->GetTextEntryValue();
				Dialogue->ClearTextEntry();
			}
		}
		SetPlayerName(EnteredName.IsEmpty() ? GetPlayerNameForDisplay() : EnteredName);
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

	const FString ChoiceKey = Choice.Id.IsEmpty() ? FString::FromInt(OptionIndex) : Choice.Id;
	ApplyOutcomes(Choice.Outcomes,
		FString::Printf(TEXT("choice:%s:%s:%d:%s:%s"),
			*CurrentEventId, *CurrentSceneId, CommandIndex, *ActiveChoiceLineKey, *ChoiceKey));

	if (!Choice.NextScene.IsEmpty())
	{
		const int32 FoundIndex = FindCommandIndexForKey(Choice.NextScene, Choice.NextKey);
		if (FoundIndex == INDEX_NONE && !Choice.NextKey.IsEmpty())
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("Story: choice next_key %s was not found in %s; leaving the event incomplete."),
				*Choice.NextKey, *Choice.NextScene);
			bWaitingForChoice = false;
			FinishEvent(false, false);
			return;
		}
		StartScene(Choice.NextScene, FoundIndex);
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
	return INDEX_NONE;
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
	if (Line.Input.IsValid())
	{
		OutLine.bTextInput = true;
		OutLine.TextMinLength = FMath::Max(1, DAJson::ReadInt(Line.Input, TEXT("min_length"), 1));
		OutLine.TextMaxLength = FMath::Max(OutLine.TextMinLength, DAJson::ReadInt(Line.Input, TEXT("max_length"), 8));
		OutLine.TextDefault = DAJson::ReadString(Line.Input, TEXT("default"));
	}
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
	const FString Upper = NewName.TrimStartAndEnd().ToUpper();
	FString Clean;
	for (const TCHAR Character : Upper)
	{
		if ((Character >= TEXT('A') && Character <= TEXT('Z'))
			|| (Character >= TEXT('0') && Character <= TEXT('9')))
		{
			Clean.AppendChar(Character);
		}
	}
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
	ApplyOutcomes(Event->Outcomes, FString::Printf(TEXT("event:%s"), *EventId));
}

void UDAStorySubsystem::ApplyOutcomes(const TArray<TSharedPtr<FJsonObject>>& Outcomes, const FString& ContextKey)
{
	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	const FString KeyPrefix = ContextKey.IsEmpty() ? FString(TEXT("outcome")) : ContextKey;

	for (int32 OutcomeIndex = 0; OutcomeIndex < Outcomes.Num(); ++OutcomeIndex)
	{
		const TSharedPtr<FJsonObject>& Outcome = Outcomes[OutcomeIndex];
		if (!Outcome.IsValid())
		{
			continue;
		}

		const TArray<TSharedPtr<FJsonObject>> Conditions = DAJson::ReadObjectArray(Outcome, TEXT("conditions"));
		if (Conditions.Num() > 0 && !EvaluateConditions(Conditions))
		{
			continue;
		}

		++PlaythroughOutcomesApplied;
		const FString Type = DAJson::ReadString(Outcome, TEXT("type"));
		if (Type == TEXT("set_flag") || Type == TEXT("flag"))
		{
			const FString Flag = DAJson::ReadString(Outcome, TEXT("flag"), DAJson::ReadString(Outcome, TEXT("id")));
			ApplySetFlag(Flag, DAJson::ReadBool(Outcome, TEXT("value"), true));
		}
		else if (Type == TEXT("add_counter") || Type == TEXT("counter"))
		{
			const FString Counter = DAJson::ReadString(Outcome, TEXT("counter"), DAJson::ReadString(Outcome, TEXT("id")));
			const int32 Amount = DAJson::ReadInt(Outcome, TEXT("amount"), 1);
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
			ApplyRewardById(DAJson::ReadString(Outcome, TEXT("reward_id"), DAJson::ReadString(Outcome, TEXT("id"))));
		}
		else if (Type == TEXT("set_calendar"))
		{
			SetCalendarFromJson(Outcome);
		}
		else if (Type == TEXT("set_objective"))
		{
			SetObjective(DAJson::ReadString(Outcome, TEXT("id")), DAJson::ReadString(Outcome, TEXT("text")));
		}
		else if (Type == TEXT("complete_event"))
		{
			CompleteEvent(DAJson::ReadString(Outcome, TEXT("event"), DAJson::ReadString(Outcome, TEXT("id"))));
		}
		else if (Type == TEXT("unlock_email"))
		{
			const TArray<FString> Contacts = DAJson::ReadStringArray(Outcome, TEXT("contacts"));
			if (Contacts.Num() > 0)
			{
				for (const FString& Contact : Contacts)
				{
					if (Profile) Profile->UnlockEmail(Contact);
				}
			}
			else if (Profile)
			{
				Profile->UnlockEmail(DAJson::ReadString(Outcome, TEXT("contact")));
			}
		}
		else if (Type == TEXT("grant_dp"))
		{
			if (Profile) Profile->AwardDP(DAJson::ReadInt(Outcome, TEXT("amount"), 0));
		}
		else if (Type == TEXT("grant_dp_from_last_lp") || Type == TEXT("dp_equal_remaining_lp"))
		{
			if (Profile) Profile->AwardDP(FMath::Max(0, Profile->GetCounter(TEXT("last_duel_player_lp"))));
		}
		else if (Type == TEXT("select_deck") || Type == TEXT("starter_deck"))
		{
			const FString DeckId = DAJson::ReadString(Outcome, TEXT("deck_id"), DAJson::ReadString(Outcome, TEXT("value")));
			if (!DeckId.IsEmpty())
			{
				SelectStarterDeck(DeckId);
			}
		}
		else if (Type == TEXT("grant_card"))
		{
			GrantStoryCard(Outcome);
		}
		else if (Type == TEXT("grant_pack"))
		{
			const FString PackId = DAJson::ReadString(Outcome, TEXT("pack_id"), DAJson::ReadString(Outcome, TEXT("pack")));
			if (PackId.IsEmpty())
			{
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: grant_pack outcome has no pack id."));
			}
			else
			{
				QueuePackGrant(PackId, DAJson::ReadInt(Outcome, TEXT("count"), 1));
			}
		}
		else if (Type == TEXT("grant_deck"))
		{
			ApplyDeckGrant(DAJson::ReadString(Outcome, TEXT("deck_id"), DAJson::ReadString(Outcome, TEXT("deck"))));
		}
		else if (Type == TEXT("set_title"))
		{
			ApplyStoryTitle(DAJson::ReadString(Outcome, TEXT("title")));
		}
		else if (Type == TEXT("set_dorm") || Type == TEXT("dorm_unlock"))
		{
			if (Profile)
			{
				Profile->SetDorm(DuelAcademyProfile::ParseDorm(DAJson::ReadString(Outcome, TEXT("dorm"), DAJson::ReadString(Outcome, TEXT("value")))));
			}
		}
		else if (Type == TEXT("double_dp") || Type == TEXT("dp_multiplier"))
		{
			if (Profile)
			{
				const int32 CurrentDP = Profile->GetDP();
				const int32 Multiplier = FMath::Max(1, DAJson::ReadInt(Outcome, TEXT("multiplier"), 2));
				Profile->AwardDP(CurrentDP * (Multiplier - 1));
				UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: DP multiplied by %d (now %d)."), Multiplier, Profile->GetDP());
			}
		}
		else if (Type == TEXT("exam_exemption"))
		{
			const FString Scope = DAJson::ReadString(Outcome, TEXT("scope"), DAJson::ReadString(Outcome, TEXT("value"), TEXT("next")));
			ApplySetFlag(FString::Printf(TEXT("exam_exempt_%s"), *DuelAcademyProfile::NormalizeId(Scope)), true);
			ApplySetFlag(TEXT("exam_exempt_next"), true);
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: exam exemption granted (%s)."), *Scope);
		}
		else if (Type == TEXT("unlock_duel"))
		{
			const TArray<FString> Duels = DAJson::ReadStringArray(Outcome, TEXT("opponents"));
			TArray<FString> Ids = Duels;
			if (Ids.Num() == 0)
			{
				Ids = DAJson::ReadStringArray(Outcome, TEXT("duels"));
			}
			if (Ids.Num() == 0)
			{
				Ids.Add(DAJson::ReadString(Outcome, TEXT("id"), DAJson::ReadString(Outcome, TEXT("opponent"))));
			}
			for (const FString& DuelId : Ids)
			{
				UnlockDuel(DuelId);
			}
		}
		else if (Type == TEXT("item"))
		{
			const FString ItemName = DAJson::ReadString(Outcome, TEXT("name"), DAJson::ReadString(Outcome, TEXT("id")));
			const FString ItemKey = DuelAcademyProfile::NormalizeId(ItemName);
			if (!ItemKey.IsEmpty())
			{
				ApplySetFlag(FString::Printf(TEXT("item_%s"), *ItemKey), true);
				if (Profile)
				{
					Profile->IncrementCounter(FString::Printf(TEXT("item_%s"), *ItemKey), 1);
				}
				UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: item '%s' recorded."), *ItemName);
			}
		}
		else if (Type == TEXT("name_change"))
		{
			ApplySetFlag(TEXT("name_change_unlocked"), true);
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: name change unlocked."));
		}
		else if (Type == TEXT("temporary_title"))
		{
			ApplyTemporaryTitle(DAJson::ReadString(Outcome, TEXT("value"), DAJson::ReadString(Outcome, TEXT("title"))));
		}
		else if (Type == TEXT("restore_title"))
		{
			RestorePreviousTitle();
		}
		else if (Type == TEXT("next_event"))
		{
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: next_event outcome '%s' is left to the event graph."),
				*DAJson::ReadString(Outcome, TEXT("event"), DAJson::ReadString(Outcome, TEXT("id"))));
		}
		else
		{
			++PlaythroughUnknownOutcome;
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: unknown outcome type '%s'."), *Type);
		}

		AppliedOutcomeKeys.Add(OutcomeKey);
	}
}

bool UDAStorySubsystem::ApplyRewardById(const FString& RewardId)
{
	if (RewardId.IsEmpty() || AppliedRewardIds.Contains(RewardId))
	{
		return false;
	}

	const TSharedPtr<FJsonObject>* RewardPtr = Rewards.Find(RewardId);
	if (!RewardPtr || !RewardPtr->IsValid())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: reward id '%s' is not declared."), *RewardId);
		return false;
	}
	const TSharedPtr<FJsonObject> Reward = *RewardPtr;
	const FString Type = DAJson::ReadString(Reward, TEXT("type"));

	UDAProfileSubsystem* Profile = ResolveProfile();
	if (Type == TEXT("dp"))
	{
		const int32 Amount = DAJson::ReadInt(Reward, TEXT("amount"), DAJson::ReadInt(Reward, TEXT("dp"), 0));
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
		const TArray<FString> Contacts = DAJson::ReadStringArray(Reward, TEXT("contacts"));
		if (Profile)
		{
			for (const FString& Contact : Contacts)
			{
				Profile->UnlockEmail(Contact);
			}
			const FString SingleContact = DAJson::ReadString(Reward, TEXT("contact"));
			if (!SingleContact.IsEmpty())
			{
				Profile->UnlockEmail(SingleContact);
			}
		}
	}
	else if (Type == TEXT("deck_grant"))
	{
		ApplyDeckGrant(DAJson::ReadString(Reward, TEXT("deck_id")));
	}
	else if (Type == TEXT("card") || Type == TEXT("card_grant"))
	{
		GrantStoryCard(Reward);
	}
	else if (Type == TEXT("pack") || Type == TEXT("pack_grant"))
	{
		const FString PackId = DAJson::ReadString(Reward, TEXT("pack_id"), DAJson::ReadString(Reward, TEXT("pack")));
		if (!PackId.IsEmpty())
		{
			QueuePackGrant(PackId, DAJson::ReadInt(Reward, TEXT("count"), 1));
		}
	}
	else if (Type == TEXT("flag"))
	{
		ApplySetFlag(DAJson::ReadString(Reward, TEXT("flag")), true);
	}
	else if (Type == TEXT("title"))
	{
		ApplyStoryTitle(DAJson::ReadString(Reward, TEXT("title")));
	}
	else if (Type == TEXT("dorm"))
	{
		if (Profile) Profile->SetDorm(DuelAcademyProfile::ParseDorm(DAJson::ReadString(Reward, TEXT("dorm"))));
	}

	AppliedRewardIds.Add(RewardId);
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: applied reward %s (%s)."), *RewardId, *Type);
	return true;
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
		const TArray<FString> Emails = DAJson::ReadStringArray(Command.Raw, TEXT("emails"));
		if (Profile)
		{
			for (const FString& Email : Emails)
			{
				Profile->UnlockEmail(Email);
			}
		}

		const FString DeckId = DAJson::ReadString(Command.Raw, TEXT("deck_id"));
		if (!DeckId.IsEmpty())
		{
			ApplyDeckGrant(DeckId);
		}

		const FString PackId = DAJson::ReadString(Command.Raw, TEXT("pack_id"));
		if (!PackId.IsEmpty())
		{
			QueuePackGrant(PackId, DAJson::ReadInt(Command.Raw, TEXT("count"), 1));
		}

		const TArray<FString> Flags = DAJson::ReadStringArray(Command.Raw, TEXT("flags"));
		for (const FString& Flag : Flags)
		{
			ApplySetFlag(Flag, true);
		}
	}

	AppliedRewardIds.Add(Key);
}

void UDAStorySubsystem::GrantStoryCard(const TSharedPtr<FJsonObject>& Source)
{
	const int32 CardId = DAJson::ReadInt(Source, TEXT("card_id"), DAJson::ReadInt(Source, TEXT("card"), 0));
	const int32 Count = FMath::Max(1, DAJson::ReadInt(Source, TEXT("count"), 1));
	if (UGameInstance* GI = GetGameInstance())
	{
		if (UDAInventorySubsystem* Inventory = GI->GetSubsystem<UDAInventorySubsystem>())
		{
			Inventory->AddCard(CardId, Count);
			return;
		}
	}
	// Headless fallback until the A06 inventory exists (read by card conditions).
	if (UDAProfileSubsystem* Profile = ResolveProfile())
	{
		Profile->IncrementCounter(FString::Printf(TEXT("card_%d"), CardId), Count);
	}
}

void UDAStorySubsystem::QueuePackGrant(const FString& PackId, int32 Count)
{
	if (PackId.IsEmpty())
	{
		return;
	}
	const int32 SafeCount = FMath::Max(1, Count);
	PendingPackGrants.FindOrAdd(PackId) += SafeCount;
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: pack '%s' queued as an unopened grant (x%d)."), *PackId, SafeCount);
}

void UDAStorySubsystem::ApplyStoryTitle(const FString& Title)
{
	UDAProfileSubsystem* Profile = ResolveProfile();
	if (!Profile)
	{
		return;
	}
	// An explicit story title ends any temporary title (e.g. E07's Occult
	// Duelist before E08 restores Apprentice Duelist); otherwise the next title
	// refresh would bring the temporary title back.
	Profile->ClearTemporaryTitle();
	Profile->SetTitle(Title);
	if (!Title.Equals(TEXT("Dropout Boy"), ESearchCase::IgnoreCase))
	{
		// E29 recovers from the exam fail state by setting a normal title. A
		// later A02 title refresh must not resurrect Dropout Boy.
		FString DropoutFlag = TEXT("dropout_boy");
		if (UGameInstance* GI = GetGameInstance())
		{
			if (const UDATitleSystem* Titles = GI->GetSubsystem<UDATitleSystem>())
			{
				DropoutFlag = Titles->GetDropoutFlag();
			}
		}
		Profile->SetFlag(DropoutFlag, false);
		Profile->SetFlag(TEXT("dropout"), false);
	}
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

void UDAStorySubsystem::ApplyTemporaryTitle(const FString& Title)
{
	if (Title.IsEmpty())
	{
		return;
	}
	if (UDAProfileSubsystem* Profile = ResolveProfile())
	{
		PreviousTitle = Profile->GetTitle();
		Profile->SetTemporaryTitle(Title, 30);
	}
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: temporary title '%s' (previous '%s')."), *Title, *PreviousTitle);
}

void UDAStorySubsystem::RestorePreviousTitle()
{
	UDAProfileSubsystem* Profile = ResolveProfile();
	if (!Profile)
	{
		return;
	}
	const FString Restored = PreviousTitle.IsEmpty() ? FString(TEXT("Apprentice Duelist")) : PreviousTitle;
	Profile->SetTitle(Restored);
	Profile->ClearTemporaryTitle();
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: title restored to '%s'."), *Restored);
	PreviousTitle.Reset();
}

void UDAStorySubsystem::UnlockDuel(const FString& DuelId)
{
	const FString Key = DuelAcademyProfile::NormalizeId(DuelId);
	if (Key.IsEmpty())
	{
		return;
	}
	UnlockedDuels.Add(Key);
	ApplySetFlag(FString::Printf(TEXT("duel_unlocked_%s"), *Key), true);
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: duel request '%s' unlocked."), *Key);
}

bool UDAStorySubsystem::ApplyDeckGrant(const FString& DeckId)
{
	if (DeckId.IsEmpty())
	{
		return false;
	}

	SelectedStarterDeck = DeckId;
	UDAProfileSubsystem* Profile = ResolveProfile();
	if (!Profile)
	{
		return false;
	}

	// V2 residual corner: the starter flags must only record a deck choice the
	// import actually applied, so a failed import stays retryable.
	bool bImported = false;

	if (UObject* Provider = Profile->GetDeckProvider())
	{
		if (UDADeckLogic* DeckLogic = Cast<UDADeckLogic>(Provider))
		{
			// Starter recipes (fire/water/wind) are card-database ids, not player
			// deck ids. Import the chosen recipe under its stable recipe id and
			// grant its cards once; a reloaded/duplicate grant finds the existing
			// deck and does not add a second copy of the collection.
			const bool bHadDeck = DeckLogic->FindPlayerDeck(DeckId) != nullptr;
			const FString DeckName = FString::Printf(TEXT("%s Deck"), *DeckId.ToUpper());
			FString ActiveDeckId;
			FString DeckError;
			bool bCreated = false;
			if (DeckLogic->EnsureStarterDeck(DeckId, DeckName, ActiveDeckId, bCreated, DeckError))
			{
				if (bCreated && !bHadDeck)
				{
					if (UGameInstance* GameInstance = GetGameInstance())
					{
						if (UDAInventorySubsystem* Inventory = GameInstance->GetSubsystem<UDAInventorySubsystem>())
						{
							Inventory->GrantStarterCollection(DeckLogic->GetStarterDeckCards(DeckId));
						}
					}
				}
				DeckLogic->SetActiveDeckId(ActiveDeckId);
				bImported = true;
			}
			else
			{
				UE_LOG(LogDuelAcademyIsland, Warning,
					TEXT("Story: could not import starter deck %s: %s"), *DeckId, *DeckError);
			}
		}
		else if (IDAProfileDeckInterface* Decks = Cast<IDAProfileDeckInterface>(Provider))
		{
			Decks->SetActiveDeckId(DeckId);
			bImported = true;
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

	if (bImported)
	{
		Profile->SetFlag(FString::Printf(TEXT("starter_deck_%s"), *DeckId.ToLower()), true);
		Profile->SetFlag(TEXT("starter_deck_chosen"), true);
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: granted/activated deck %s."), *DeckId);
	}
	return bImported;
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
		return ApplyRewardById(RewardId);
	}
	return ApplyDeckGrant(Deck);
}

void UDAStorySubsystem::SetCalendarFromJson(const TSharedPtr<FJsonObject>& Object)
{
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	if (!Calendar || !Object.IsValid())
	{
		return;
	}

	const int32 Year = DAJson::ReadInt(Object, TEXT("year"), 1);
	int32 MonthIndex = DAJson::ReadInt(Object, TEXT("month_index"), INDEX_NONE);
	if (MonthIndex == INDEX_NONE)
	{
		MonthIndex = UDACalendarSubsystem::MonthNumberToIndex(DAJson::ReadInt(Object, TEXT("month"), Calendar->GetMonthNumber()));
	}
	const int32 Day = DAJson::ReadInt(Object, TEXT("day"), 1);

	const EDADayPeriod Period = UDACalendarSubsystem::ParsePeriod(DAJson::ReadString(Object, TEXT("period"), TEXT("AM")));

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
	// Every event's own outcomes set event_XX_cleared before this runs, so the
	// runtime set (not the profile flag) decides whether this is a first clear.
	bool bAlreadyCompleted = false;
	CompletedEvents.Add(EventId, &bAlreadyCompleted);
	if (UDAProfileSubsystem* Profile = ResolveProfile())
	{
		Profile->SetFlag(FDAEventGraph::EventCompletionFlag(EventId), true);
		if (!bAlreadyCompleted)
		{
			// UDATitleSystem gates Duel King / King of Games on this counter.
			Profile->IncrementCounter(TEXT("story_events_cleared"), 1);
		}

		// Data-only email hooks: emails.json owns unlocked_by and duel_requests.
		// Apply them through A02 so the PDA and A07 can consume the same state.
		for (const TPair<FString, TSharedPtr<FJsonObject>>& Pair : EmailContacts)
		{
			if (!Pair.Value.IsValid())
			{
				continue;
			}
			const TArray<FString> UnlockedBy = DAJson::ReadStringArray(Pair.Value, TEXT("unlocked_by"));
			if (!UnlockedBy.Contains(EventId))
			{
				continue;
			}

			Profile->UnlockEmail(Pair.Key);
			for (const TSharedPtr<FJsonObject>& Request : DAJson::ReadObjectArray(Pair.Value, TEXT("duel_requests")))
			{
				const FString RequestId = DAJson::ReadString(Request, TEXT("id"));
				const FString OpponentId = DAJson::ReadString(Request, TEXT("opponent"));
				if (!RequestId.IsEmpty())
				{
					Profile->AddDuelRequest(Pair.Key, RequestId);
				}
				if (!OpponentId.IsEmpty())
				{
					UnlockDuel(OpponentId);
				}
			}
		}

		// DASaveGame.h documents "event completion" as part of the autosave
		// trigger set; keep the reason in the same lowercase style as the
		// profile's "duel_result"/"result_token" reasons.
		Profile->RequestProgressionAutosave(TEXT("event_complete"));
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

TArray<FString> UDAStorySubsystem::GetEmailContactIds() const
{
	TArray<FString> Ids;
	EmailContacts.GetKeys(Ids);
	Ids.Sort();
	return Ids;
}

TArray<FString> UDAStorySubsystem::GetEmailMessageIds(const FString& ContactId) const
{
	TArray<FString> Ids;
	if (const TSharedPtr<FJsonObject>* Contact = EmailContacts.Find(ContactId))
	{
		for (const TSharedPtr<FJsonObject>& Message : DAJson::ReadObjectArray(*Contact, TEXT("messages")))
		{
			const FString Id = DAJson::ReadString(Message, TEXT("id"));
			if (!Id.IsEmpty())
			{
				Ids.Add(Id);
			}
		}
	}
	return Ids;
}

TArray<FString> UDAStorySubsystem::GetEmailDuelRequestIds(const FString& ContactId) const
{
	TArray<FString> Ids;
	if (const TSharedPtr<FJsonObject>* Contact = EmailContacts.Find(ContactId))
	{
		for (const TSharedPtr<FJsonObject>& Request : DAJson::ReadObjectArray(*Contact, TEXT("duel_requests")))
		{
			const FString Id = DAJson::ReadString(Request, TEXT("id"));
			if (!Id.IsEmpty())
			{
				Ids.Add(Id);
			}
		}
	}
	return Ids;
}

TArray<FString> UDAStorySubsystem::GetUnlockedDuelIds() const
{
	TArray<FString> Ids = UnlockedDuels.Array();
	Ids.Sort();
	return Ids;
}

bool UDAStorySubsystem::IsDuelUnlocked(const FString& DuelId) const
{
	return UnlockedDuels.Contains(DuelAcademyProfile::NormalizeId(DuelId));
}

TArray<FString> UDAStorySubsystem::GetPendingPackGrants() const
{
	TArray<FString> Ids;
	PendingPackGrants.GetKeys(Ids);
	Ids.Sort();
	return Ids;
}

bool UDAStorySubsystem::ConsumePendingPackGrant(const FString& PackId)
{
	int32* Count = PendingPackGrants.Find(PackId);
	if (!Count || *Count <= 0)
	{
		return false;
	}
	--(*Count);
	if (*Count <= 0)
	{
		PendingPackGrants.Remove(PackId);
	}
	return true;
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
	PendingDuel.bAwardDP = Command.bAwardDP;

	if (const UDAProfileSubsystem* Profile = ResolveProfile())
	{
		PendingDuel.PreWinsSyrus = Profile->GetCounter(TEXT("wins_syrus"));
		PendingDuel.PreWinsTotal = Profile->GetCounter(TEXT("wins_total"));
		PendingDuel.PreDuels = Profile->GetCounter(TEXT("duels_total"));
		PendingDuel.PreDraws = Profile->GetCounter(TEXT("draws_total"));
		PendingDuel.PreLosses = Profile->GetCounter(TEXT("losses_total"));
	}
}

void UDAStorySubsystem::InferPendingDuelResult(bool& bOutWon, bool& bOutDraw) const
{
	bOutWon = false;
	bOutDraw = false;
	const UDAProfileSubsystem* Profile = ResolveProfile();
	if (!Profile)
	{
		return;
	}

	if (Profile->GetCounter(TEXT("draws_total")) > PendingDuel.PreDraws)
	{
		bOutDraw = true;
		return;
	}
	if (PendingDuel.bTutorial)
	{
		bOutWon = Profile->GetCounter(TEXT("wins_syrus")) > PendingDuel.PreWinsSyrus;
		return;
	}

	// wins_total covers every opponent; the per-opponent counters are kept as
	// fallbacks for hand-edited or legacy saves that only moved one of them.
	bOutWon = Profile->GetCounter(TEXT("wins_total")) > PendingDuel.PreWinsTotal
		|| Profile->GetCounter(TEXT("wins_jaden")) > PendingDuel.PreWinsJaden
		|| Profile->GetCounter(TEXT("wins_syrus")) > PendingDuel.PreWinsSyrus;
}

EDAStoryDuelTickDecision UDAStorySubsystem::DecidePendingDuelTick(bool bDuelOpen, bool bDeckSelectClosedWithoutResult,
	bool bModalOpen, bool bResumePendingDuel, bool bOpened, float Elapsed, float RetryTimer)
{
	if (bDuelOpen)
	{
		// The deck select/duel owns the screen; the tick only marks the duel as
		// opened (a side effect of being here, no further decision needed).
		return EDAStoryDuelTickDecision::None;
	}
	if (bResumePendingDuel)
	{
		// A save restored a pending duel. Re-present once the screen frees up
		// instead of replaying the duel command; never time a restore into a
		// loss while a modal simply blocks the open.
		return (Elapsed > 0.5f && !bModalOpen)
			? EDAStoryDuelTickDecision::Reopen
			: EDAStoryDuelTickDecision::None;
	}
	if (bDeckSelectClosedWithoutResult)
	{
		// P4-02: the player backed out of the story deck select. That is a
		// re-present, never a story loss.
		return EDAStoryDuelTickDecision::Reopen;
	}
	if (bOpened)
	{
		// P4-02: the duel ran and closed; infer the result from the counters.
		return EDAStoryDuelTickDecision::ResolveInferred;
	}
	if (Elapsed > 10.f)
	{
		// Only a genuinely unopenable HUD reaches this: the refusal retry below
		// consumed its full 10s budget (or no retry could open the selector).
		return EDAStoryDuelTickDecision::ResolveLoss;
	}
	return RetryTimer <= 0.f
		? EDAStoryDuelTickDecision::RetryRequest
		: EDAStoryDuelTickDecision::None;
}

void UDAStorySubsystem::OpenPendingDuelDeckSelect(ADAHUD& HUD)
{
	const FString DuelMode = PendingDuel.bTutorial ? TEXT("tutorial") : PendingDuel.Mode;
	HUD.OpenDuelDeckSelect(PendingDuel.OpponentId, PendingDuel.OpponentName,
		PendingDuel.OpponentDeckId, DuelMode, PendingDuel.bAwardDP);
}

void UDAStorySubsystem::ResolvePendingDuel(bool bWon, bool bDraw)
{
	++PlaythroughDuelResolved;
	const FString SceneId = bDraw ? PendingDuel.OnDraw : (bWon ? PendingDuel.OnWin : PendingDuel.OnLose);
	const FString Opponent = PendingDuel.OpponentId;

	bWaitingForDuel = false;
	PendingDuel.bOpened = false;
	PendingDuel.Elapsed = 0.f;
	bResumePendingDuel = false;
	DuelOpenRetryTimer = 0.f;

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: duel vs %s resolved (won=%s, draw=%s) -> %s"),
		*Opponent, bWon ? TEXT("true") : TEXT("false"), bDraw ? TEXT("true") : TEXT("false"),
		SceneId.IsEmpty() ? TEXT("<finish>") : *SceneId);

	// Headless/manual audiences resolve duels without the duel UI, so they must
	// still feed the same profile counters the live path records. A changed
	// duels_total means DADuelUI already recorded this result.
	if (UDAProfileSubsystem* Profile = ResolveProfile())
	{
		if (!PendingDuel.bTutorial && Profile->GetCounter(TEXT("duels_total")) == PendingDuel.PreDuels)
		{
			const FString OpponentKey = NormalizeStoryNpcId(Opponent);
			Profile->IncrementCounter(TEXT("duels_total"), 1);
			if (bDraw)
			{
				Profile->IncrementCounter(TEXT("draws_total"), 1);
				Profile->SetCounter(TEXT("last_duel_player_lp"), 0);
			}
			else if (!bWon)
			{
				Profile->IncrementCounter(TEXT("losses_total"), 1);
				if (!OpponentKey.IsEmpty())
				{
					Profile->IncrementCounter(FString::Printf(TEXT("losses_%s"), *OpponentKey), 1);
				}
				Profile->SetCounter(TEXT("last_duel_player_lp"), 0);
			}
			else
			{
				Profile->IncrementCounter(TEXT("wins_total"), 1);
				if (!OpponentKey.IsEmpty())
				{
					Profile->IncrementCounter(FString::Printf(TEXT("wins_%s"), *OpponentKey), 1);
				}
				Profile->SetCounter(TEXT("last_duel_player_lp"), 8000);
			}
		}
	}

	if (!SceneId.IsEmpty())
	{
		StartScene(SceneId, 0);
	}
	else
	{
		// Multi-duel events chain duel commands with no branch scene. Continue
		// with the next command instead of ending the event after one duel.
		++CommandIndex;
		bPendingContinue = true;
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
	const TArray<FString> Periods = DAJson::ReadStringArray(Object, TEXT("periods"));
	if (Periods.Num() > 0)
	{
		return Periods.Contains(Period);
	}
	const FString Single = DAJson::ReadString(Object, TEXT("period"));
	return Single.IsEmpty() || Single.Equals(Period, ESearchCase::IgnoreCase);
}

bool UDAStorySubsystem::MatchScheduleWeekday(const TSharedPtr<FJsonObject>& Object, const FString& Weekday) const
{
	if (!Object.IsValid())
	{
		return false;
	}
	const TArray<FString> Weekdays = DAJson::ReadStringArray(Object, TEXT("weekdays"));
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
	// EvaluateCondition already treats null as pass and handles typeless
	// {"all": [...]} / {"any": [...]} objects with the correct semantics.
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

	const TArray<TSharedPtr<FJsonObject>> Overrides = DAJson::ReadObjectArray(Npc, TEXT("date_overrides"));
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

		const int32 Priority = DAJson::ReadInt(Override, TEXT("priority"), 0);
		if (Priority >= BestPriority)
		{
			BestPriority = Priority;
			OutLocation = DAJson::ReadString(Override, TEXT("location"));
			OutAnchor = DAJson::ReadString(Override, TEXT("anchor"));
			bFound = true;
		}
	}

	const TArray<TSharedPtr<FJsonObject>> Entries = DAJson::ReadObjectArray(Npc, TEXT("entries"));
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

		const int32 Priority = DAJson::ReadInt(Entry, TEXT("priority"), 0);
		if (Priority >= BestPriority)
		{
			BestPriority = Priority;
			OutLocation = DAJson::ReadString(Entry, TEXT("location"));
			OutAnchor = DAJson::ReadString(Entry, TEXT("anchor"));
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

	// TSet iteration order is not stable across runs. Sort the serialized
	// arrays so saving the same story state twice stays byte-identical.
	TArray<FString> CompletedIds = CompletedEvents.Array();
	CompletedIds.Sort();
	TArray<TSharedPtr<FJsonValue>> Completed;
	for (const FString& EventId : CompletedIds)
	{
		Completed.Add(MakeShared<FJsonValueString>(EventId));
	}
	Root->SetArrayField(TEXT("completed"), Completed);

	TArray<FString> AppliedIds = AppliedRewardIds.Array();
	AppliedIds.Sort();
	TArray<TSharedPtr<FJsonValue>> Applied;
	for (const FString& RewardId : AppliedIds)
	{
		Applied.Add(MakeShared<FJsonValueString>(RewardId));
	}
	Root->SetArrayField(TEXT("applied_rewards"), Applied);

	TArray<FString> UnlockedIds = UnlockedDuels.Array();
	UnlockedIds.Sort();
	TArray<TSharedPtr<FJsonValue>> Unlocked;
	for (const FString& DuelId : UnlockedIds)
	{
		Unlocked.Add(MakeShared<FJsonValueString>(DuelId));
	}
	Root->SetArrayField(TEXT("unlocked_duels"), Unlocked);
	Root->SetStringField(TEXT("previous_title"), PreviousTitle);

	TArray<FString> OutcomeIds = AppliedOutcomeKeys.Array();
	OutcomeIds.Sort();
	TArray<TSharedPtr<FJsonValue>> AppliedOutcomes;
	for (const FString& OutcomeKey : OutcomeIds)
	{
		AppliedOutcomes.Add(MakeShared<FJsonValueString>(OutcomeKey));
	}
	Root->SetArrayField(TEXT("applied_outcomes"), AppliedOutcomes);

	Root->SetBoolField(TEXT("waiting_for_duel"), bWaitingForDuel);
	if (bWaitingForDuel)
	{
		TSharedPtr<FJsonObject> PendingObject = MakeShared<FJsonObject>();
		PendingObject->SetStringField(TEXT("opponent_id"), PendingDuel.OpponentId);
		PendingObject->SetStringField(TEXT("opponent_name"), PendingDuel.OpponentName);
		PendingObject->SetStringField(TEXT("opponent_deck_id"), PendingDuel.OpponentDeckId);
		PendingObject->SetStringField(TEXT("mode"), PendingDuel.Mode);
		PendingObject->SetStringField(TEXT("on_win"), PendingDuel.OnWin);
		PendingObject->SetStringField(TEXT("on_lose"), PendingDuel.OnLose);
		PendingObject->SetStringField(TEXT("on_draw"), PendingDuel.OnDraw);
		PendingObject->SetBoolField(TEXT("tutorial"), PendingDuel.bTutorial);
		PendingObject->SetBoolField(TEXT("award_dp"), PendingDuel.bAwardDP);
		PendingObject->SetBoolField(TEXT("opened"), PendingDuel.bOpened);
		PendingObject->SetNumberField(TEXT("elapsed"), PendingDuel.Elapsed);
		PendingObject->SetNumberField(TEXT("pre_wins_jaden"), PendingDuel.PreWinsJaden);
		PendingObject->SetNumberField(TEXT("pre_wins_syrus"), PendingDuel.PreWinsSyrus);
		PendingObject->SetNumberField(TEXT("pre_wins_total"), PendingDuel.PreWinsTotal);
		PendingObject->SetNumberField(TEXT("pre_duels"), PendingDuel.PreDuels);
		PendingObject->SetNumberField(TEXT("pre_draws"), PendingDuel.PreDraws);
		PendingObject->SetNumberField(TEXT("pre_losses"), PendingDuel.PreLosses);
		Root->SetObjectField(TEXT("pending_duel"), PendingObject);
	}

	TSharedPtr<FJsonObject> PackObject = MakeShared<FJsonObject>();
	for (const TPair<FString, int32>& Pair : PendingPackGrants)
	{
		PackObject->SetNumberField(Pair.Key, Pair.Value);
	}
	Root->SetObjectField(TEXT("pending_packs"), PackObject);

	TSharedPtr<FJsonObject> ObjectiveObject = MakeShared<FJsonObject>();
	for (const TPair<FString, FString>& Pair : Objectives)
	{
		ObjectiveObject->SetStringField(Pair.Key, Pair.Value);
	}
	Root->SetObjectField(TEXT("objectives"), ObjectiveObject);

	// Sort nested object keys through the save subsystem's canonical serializer
	// so pending_packs/objectives TMap order cannot change the bytes.
	return UDASaveSubsystem::SerializeCanonicalJson(Root);
}

bool UDAStorySubsystem::LoadState(const FString& Json, FString& OutError)
{
	TSharedPtr<FJsonObject> Root;
	if (!DAJson::ParseObject(Json, Root))
	{
		OutError = TEXT("story state is invalid JSON");
		return false;
	}

	// Fields absent from the saved state must not inherit this session's values.
	ResetRuntimeState();

	Root->TryGetStringField(TEXT("event"), CurrentEventId);
	Root->TryGetStringField(TEXT("scene"), CurrentSceneId);
	Root->TryGetNumberField(TEXT("command"), CommandIndex);
	CommandIndex = FMath::Max(0, CommandIndex);
	Root->TryGetBoolField(TEXT("running"), bRunning);
	Root->TryGetBoolField(TEXT("free_roam"), bFreeRoam);
	Root->TryGetBoolField(TEXT("opening_started"), bOpeningStarted);
	Root->TryGetStringField(TEXT("starter_deck"), SelectedStarterDeck);

	auto ReadStringSet = [&Root](const TCHAR* Field, TSet<FString>& OutSet)
	{
		OutSet.Reset();
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (Root->TryGetArrayField(Field, Values) && Values)
		{
			for (const TSharedPtr<FJsonValue>& Value : *Values)
			{
				if (Value.IsValid() && Value->Type == EJson::String)
				{
					const FString Id = Value->AsString();
					if (!Id.IsEmpty())
					{
						OutSet.Add(Id);
					}
				}
			}
		}
		else if (Root->HasField(Field))
		{
			// Full save loads are rejected by ValidateSaveSection before this
			// point; reaching here means a direct LoadState reset a ledger.
			// Make that visible instead of silently granting outcomes again.
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("Story: save field '%s' is not a string array; the %s ledger was reset while reading."),
				*FString(Field), *FString(Field));
		}
	};

	ReadStringSet(TEXT("completed"), CompletedEvents);
	ReadStringSet(TEXT("applied_rewards"), AppliedRewardIds);
	ReadStringSet(TEXT("applied_outcomes"), AppliedOutcomeKeys);
	ReadStringSet(TEXT("unlocked_duels"), UnlockedDuels);
	Root->TryGetStringField(TEXT("previous_title"), PreviousTitle);

	PendingPackGrants.Reset();
	const TSharedPtr<FJsonObject>* PackObject = nullptr;
	if (Root->TryGetObjectField(TEXT("pending_packs"), PackObject) && PackObject)
	{
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*PackObject)->Values)
		{
			double CountNumber = 0.0;
			if (Pair.Value.IsValid() && Pair.Value->Type == EJson::Number
				&& Pair.Value->TryGetNumber(CountNumber) && FMath::IsFinite(CountNumber) && CountNumber >= 1.0)
			{
				const double Clamped = FMath::Min(CountNumber, static_cast<double>(TNumericLimits<int32>::Max()));
				const int32 Count = static_cast<int32>(FMath::Max<int64>(1, FMath::RoundToInt(Clamped)));
				PendingPackGrants.Add(FString(*Pair.Key), Count);
			}
		}
	}

	Objectives.Reset();
	const TSharedPtr<FJsonObject>* ObjectiveObject = nullptr;
	if (Root->TryGetObjectField(TEXT("objectives"), ObjectiveObject) && ObjectiveObject)
	{
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : (*ObjectiveObject)->Values)
		{
			if (Pair.Value.IsValid() && Pair.Value->Type == EJson::String)
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
	bPendingContinue = false;
	bResumePendingDuel = false;
	DuelOpenRetryTimer = 0.f;
	WaitRemaining = 0.f;
	ActiveChoices.Reset();
	ActiveChoiceConversationId.Reset();
	ActiveChoiceLineKey.Reset();
	PendingTextInputKey.Reset();
	PendingDuel = FDAStoryPendingDuel();

	// Pending-duel state is additive. Older saves have no pending_duel object
	// and keep the historical replay-the-duel-command behavior.
	bool bSavedWaitingForDuel = false;
	Root->TryGetBoolField(TEXT("waiting_for_duel"), bSavedWaitingForDuel);
	const TSharedPtr<FJsonObject>* PendingObject = nullptr;
	if (Root->TryGetObjectField(TEXT("pending_duel"), PendingObject) && PendingObject && PendingObject->IsValid())
	{
		FDAStoryPendingDuel LoadedDuel;
		(*PendingObject)->TryGetStringField(TEXT("opponent_id"), LoadedDuel.OpponentId);
		(*PendingObject)->TryGetStringField(TEXT("opponent_name"), LoadedDuel.OpponentName);
		(*PendingObject)->TryGetStringField(TEXT("opponent_deck_id"), LoadedDuel.OpponentDeckId);
		(*PendingObject)->TryGetStringField(TEXT("mode"), LoadedDuel.Mode);
		(*PendingObject)->TryGetStringField(TEXT("on_win"), LoadedDuel.OnWin);
		(*PendingObject)->TryGetStringField(TEXT("on_lose"), LoadedDuel.OnLose);
		(*PendingObject)->TryGetStringField(TEXT("on_draw"), LoadedDuel.OnDraw);
		(*PendingObject)->TryGetBoolField(TEXT("tutorial"), LoadedDuel.bTutorial);
		(*PendingObject)->TryGetBoolField(TEXT("award_dp"), LoadedDuel.bAwardDP);
		(*PendingObject)->TryGetBoolField(TEXT("opened"), LoadedDuel.bOpened);
		double Elapsed = 0.0;
		if ((*PendingObject)->TryGetNumberField(TEXT("elapsed"), Elapsed) && FMath::IsFinite(Elapsed))
		{
			LoadedDuel.Elapsed = static_cast<float>(FMath::Clamp(Elapsed, 0.0, 10.0));
		}
		(*PendingObject)->TryGetNumberField(TEXT("pre_wins_jaden"), LoadedDuel.PreWinsJaden);
		(*PendingObject)->TryGetNumberField(TEXT("pre_wins_syrus"), LoadedDuel.PreWinsSyrus);
		(*PendingObject)->TryGetNumberField(TEXT("pre_wins_total"), LoadedDuel.PreWinsTotal);
		(*PendingObject)->TryGetNumberField(TEXT("pre_duels"), LoadedDuel.PreDuels);
		(*PendingObject)->TryGetNumberField(TEXT("pre_draws"), LoadedDuel.PreDraws);
		(*PendingObject)->TryGetNumberField(TEXT("pre_losses"), LoadedDuel.PreLosses);

		if (!LoadedDuel.OpponentId.IsEmpty())
		{
			PendingDuel = LoadedDuel;
			bWaitingForDuel = true;
		}
	}
	if (bSavedWaitingForDuel && PendingDuel.OpponentId.IsEmpty())
	{
		// A save that declared a waiting duel but carried no usable opponent is
		// treated as corrupt and resumes in free roam instead of soft-locking.
		bWaitingForDuel = false;
	}

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

	if (bWaitingForDuel)
	{
		const bool bDuelCommand = bRunning && CurrentCommands.IsValidIndex(CommandIndex)
			&& CurrentCommands[CommandIndex].Type == EDAStoryCommandType::Duel;
		if (!bDuelCommand)
		{
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("Story: pending duel in save does not match the restored command; clearing it."));
			bWaitingForDuel = false;
			PendingDuel = FDAStoryPendingDuel();
		}
		else
		{
			// If the duel result was already recorded before the save (for
			// example the save happened after the UI result but before the
			// story tick), resolve the saved branch now instead of re-opening
			// the duel and counting the result twice.
			bool bResultRecorded = false;
			bool bWon = false;
			bool bDraw = false;
			if (const UDAProfileSubsystem* Profile = ResolveProfile())
			{
				InferPendingDuelResult(bWon, bDraw);
				bResultRecorded = bDraw || bWon
					|| Profile->GetCounter(TEXT("losses_total")) > PendingDuel.PreLosses;
			}

			if (bResultRecorded)
			{
				UE_LOG(LogDuelAcademyIsland, Log,
					TEXT("Story: pending duel already recorded its result; resolving the saved branch."));
				ResolvePendingDuel(bWon, bDraw);
			}
			else
			{
				// Do not replay the duel command. Tick re-presents the saved duel
				// selector and waits for the real result.
				bResumePendingDuel = true;
				bPendingContinue = false;
			}
		}
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

bool UDAStorySubsystem::ValidateSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError) const
{
	if (!InSection.IsValid())
	{
		OutError = TEXT("Story save section is missing.");
		return false;
	}

	FString State;
	if (!InSection->TryGetStringField(TEXT("state"), State) || State.IsEmpty())
	{
		OutError = TEXT("Story save section has no state payload.");
		return false;
	}

	TSharedPtr<FJsonObject> Parsed;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(State);
	if (!FJsonSerializer::Deserialize(Reader, Parsed) || !Parsed.IsValid())
	{
		OutError = TEXT("Story save section contains invalid state JSON.");
		return false;
	}

	// The idempotency ledgers are reject-or-accept, never silently reset: a
	// null/ill-typed array used to clear the ledger at read time, which made
	// granting outcomes reapply (double DP/pack/card) after a corrupt load.
	// P4-12 is deferred, so validate the existing key scheme as-is.
	static const TCHAR* const LedgerFields[] = {
		TEXT("applied_outcomes"), TEXT("completed"), TEXT("applied_rewards"), TEXT("unlocked_duels")
	};
	for (const TCHAR* Field : LedgerFields)
	{
		if (!Parsed->HasField(Field))
		{
			continue;
		}
		const TSharedPtr<FJsonValue> Value = Parsed->TryGetField(Field);
		if (!Value.IsValid() || Value->Type != EJson::Array)
		{
			OutError = FString::Printf(TEXT("Story save state field '%s' is not an array."), *FString(Field));
			return false;
		}
	}

	OutError.Reset();
	return true;
}

bool UDAStorySubsystem::ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError)
{
	if (!ValidateSaveSection(InSection, OutError))
	{
		// No story state in this save: start from a clean runtime instead of
		// keeping the previous session's completed events and queue.
		ResetRuntimeState();
		OutError.Reset();
		return true;
	}

	FString State;
	InSection->TryGetStringField(TEXT("state"), State);
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
	UGameInstance* GameInstance = GetGameInstance();
	UDADeckLogic* Decks = GameInstance ? GameInstance->GetSubsystem<UDADeckLogic>() : nullptr;
	UDAInventorySubsystem* Inventory = GameInstance ? GameInstance->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	const bool bStarterDeckImported = Decks && (Decks->FindPlayerDeck(TEXT("fire"))
		|| Decks->FindPlayerDeck(TEXT("water")) || Decks->FindPlayerDeck(TEXT("wind")));
	AddCheck(TEXT("starter deck imported"), bStarterDeckImported,
		Decks && Decks->GetActiveDeck() ? Decks->GetActiveDeck()->Id : FString(TEXT("no active deck")));
	AddCheck(TEXT("starter cards granted"), Inventory && Inventory->GetCollectionSize() > 0,
		Inventory ? FString::FromInt(Inventory->GetCollectionSize()) : FString(TEXT("no inventory")));
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
// Full-campaign audit (implementation in DAStorySelfTest.cpp)
// ---------------------------------------------------------------------------

void UDAStorySubsystem::CollectConditionState(const TSharedPtr<FJsonObject>& Condition,
	TSet<FString>& OutFlags, TSet<FString>& OutCounters, TSet<FString>& OutEvents) const
{
	if (!Condition.IsValid())
	{
		return;
	}

	const FString Kind = DAJson::ReadString(Condition, TEXT("type"));
	if (Kind == TEXT("flag"))
	{
		const FString Flag = DAJson::ReadString(Condition, TEXT("flag"), DAJson::ReadString(Condition, TEXT("id")));
		if (!Flag.IsEmpty())
		{
			OutFlags.Add(Flag);
		}
	}
	else if (Kind == TEXT("counter"))
	{
		const FString Counter = DAJson::ReadString(Condition, TEXT("counter"), DAJson::ReadString(Condition, TEXT("id")));
		if (!Counter.IsEmpty())
		{
			OutCounters.Add(Counter);
		}
	}
	else if (Kind == TEXT("event") || Kind == TEXT("event_complete"))
	{
		const FString EventId = DAJson::ReadString(Condition, TEXT("id"), DAJson::ReadString(Condition, TEXT("event")));
		if (!EventId.IsEmpty())
		{
			OutEvents.Add(EventId);
		}
	}
	else if (Kind == TEXT("wins_against_each"))
	{
		static const TCHAR* const Duelists[] = {
			TEXT("jaden"), TEXT("syrus"), TEXT("chumley"), TEXT("bastion"), TEXT("chazz"),
			TEXT("zane"), TEXT("alexis"), TEXT("jasmine"), TEXT("mindy"), TEXT("crowler"),
			TEXT("banner"), TEXT("blair"), TEXT("brier"), TEXT("beauregard"), TEXT("topher"),
			TEXT("conklin"), TEXT("damon"), TEXT("dimitri"), TEXT("gerard"), TEXT("fontaine")
		};
		for (const TCHAR* Duelist : Duelists)
		{
			OutCounters.Add(FString::Printf(TEXT("wins_%s"), Duelist));
		}
	}
	else if (Kind == TEXT("written_correct_percent"))
	{
		OutCounters.Add(TEXT("written_correct"));
		OutCounters.Add(TEXT("written_total"));
	}
	else if (Kind == TEXT("after_ending"))
	{
		OutFlags.Add(TEXT("post_game"));
	}

	const TCHAR* NestedFields[] = { TEXT("conditions"), TEXT("all"), TEXT("any") };
	for (const TCHAR* Field : NestedFields)
	{
		for (const TSharedPtr<FJsonObject>& Child : DAJson::ReadObjectArray(Condition, Field))
		{
			CollectConditionState(Child, OutFlags, OutCounters, OutEvents);
		}
	}
}

void UDAStorySubsystem::CollectEventState(const FDAEventDefinition& Event, TSet<FString>& OutFlags,
	TSet<FString>& OutCounters, TSet<FString>& OutEvents) const
{
	CollectConditionState(Event.Trigger, OutFlags, OutCounters, OutEvents);
	for (const TSharedPtr<FJsonObject>& Requirement : Event.Requirements)
	{
		CollectConditionState(Requirement, OutFlags, OutCounters, OutEvents);
	}
}

bool UDAStorySubsystem::RunFullStorySelfTest()
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
	auto AddInfo = [&Report](const FString& Text)
	{
		Report.Add(FString::Printf(TEXT("INFO %s"), *Text));
	};

	const double StartTime = FPlatformTime::Seconds();

	if (bRunning)
	{
		LastFullSelfTestReport = FString::Printf(TEXT("FAIL cannot run the audit while %s is running"), *CurrentEventId);
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("FullStorySelfTest: %s"), *LastFullSelfTestReport);
		return false;
	}

	if (!LoadFullCampaignData())
	{
		LastFullSelfTestReport = TEXT("FAIL full campaign data did not load");
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("FullStorySelfTest: %s"), *LastFullSelfTestReport);
		return false;
	}

	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	if (!Profile || !Calendar)
	{
		LastFullSelfTestReport = TEXT("FAIL profile/calendar subsystems are unavailable");
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("FullStorySelfTest: %s"), *LastFullSelfTestReport);
		return false;
	}

	AddSimpleCheck(TEXT("full campaign loaded"), bFullCampaignLoaded);
	AddCheck(TEXT("35 canonical event ids"), FullCampaignEventIds.Num() == 35,
		FString::FromInt(FullCampaignEventIds.Num()));
	AddSimpleCheck(TEXT("opening E01 remains loaded"), EventGraph.FindEvent(TEXT("E01")) != nullptr);

	int32 FullSceneCount = 0;
	for (const TPair<FString, FDAStoryScene>& Pair : Scenes)
	{
		if (Pair.Key.StartsWith(TEXT("full.")))
		{
			++FullSceneCount;
		}
	}
	AddInfo(FString::Printf(TEXT("%d canonical events, %d full scenes, %d total dialogue lines, %d email contacts"),
		FullCampaignEventIds.Num(), FullSceneCount, Lines.Num(), EmailContacts.Num()));

	// Compare against the read-only A01 canon manifest when it is available.
	TSharedPtr<FJsonObject> CanonRoot;
	FString CanonError;
	TSet<FString> CanonIds;
	if (LoadContentJsonObject(TEXT("Data/Canon/events.json"), CanonRoot, CanonError))
	{
		const TArray<TSharedPtr<FJsonValue>>* CanonValues = nullptr;
		if (CanonRoot->TryGetArrayField(TEXT("events"), CanonValues) && CanonValues)
		{
			for (const TSharedPtr<FJsonValue>& Value : *CanonValues)
			{
				const TSharedPtr<FJsonObject> CanonEvent = Value.IsValid() ? Value->AsObject() : TSharedPtr<FJsonObject>();
				FString CanonId;
				if (CanonEvent.IsValid() && CanonEvent->TryGetStringField(TEXT("id"), CanonId))
				{
					CanonIds.Add(CanonId);
				}
			}
		}
	}
	TArray<FString> CanonMismatch;
	if (CanonIds.Num() > 0)
	{
		for (const FString& CanonId : CanonIds)
		{
			if (!FullCampaignEventIds.Contains(CanonId))
			{
				CanonMismatch.Add(CanonId);
			}
		}
		for (const FString& FullId : FullCampaignEventIds)
		{
			if (!CanonIds.Contains(FullId))
			{
				CanonMismatch.Add(FullId);
			}
		}
		AddCheck(TEXT("ids match A01 canon"), CanonMismatch.Num() == 0,
			FString::Join(CanonMismatch, TEXT(", ")));
	}
	else
	{
		AddInfo(FString::Printf(TEXT("A01 canon manifest unavailable: %s"), *CanonError));
	}

	TSet<FString> SeenIds;
	bool bUniqueIds = true;
	for (const FDAEventDefinition& Event : EventGraph.GetEvents())
	{
		if (SeenIds.Contains(Event.Id))
		{
			bUniqueIds = false;
		}
		SeenIds.Add(Event.Id);
	}
	AddCheck(TEXT("unique event ids"), bUniqueIds, FString::FromInt(SeenIds.Num()));

	// ---------------------------------------------------------------- structure
	TArray<FString> MissingScenes;
	TArray<FString> MissingLines;
	TArray<FString> MissingAnchorScenes;
	int32 BadCommandCounts = 0;
	int32 UnknownCommands = 0;
	int32 MissingAnchorCount = 0;

	TSharedPtr<FJsonObject> AnchorRoot;
	FString AnchorError;
	TSet<FString> AnchorIds;
	if (LoadContentJsonObject(TEXT("Data/World/anchors.json"), AnchorRoot, AnchorError))
	{
		TFunction<void(const TSharedPtr<FJsonValue>&)> WalkAnchors;
		WalkAnchors = [&AnchorIds, &WalkAnchors](const TSharedPtr<FJsonValue>& Value)
		{
			if (!Value.IsValid())
			{
				return;
			}
			if (Value->Type == EJson::Object)
			{
				const TSharedPtr<FJsonObject> Object = Value->AsObject();
				FString Id;
				if (Object.IsValid() && Object->TryGetStringField(TEXT("id"), Id) && !Id.IsEmpty())
				{
					AnchorIds.Add(Id);
				}
				for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : Object->Values)
				{
					WalkAnchors(Pair.Value);
				}
			}
			else if (Value->Type == EJson::Array)
			{
				for (const TSharedPtr<FJsonValue>& Child : Value->AsArray())
				{
					WalkAnchors(Child);
				}
			}
		};
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : AnchorRoot->Values)
		{
			WalkAnchors(Pair.Value);
		}
	}
	else
	{
		AddInfo(FString::Printf(TEXT("A08 anchors unavailable: %s"), *AnchorError));
	}

	for (const FString& EventId : FullCampaignEventIds)
	{
		const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
		if (!Event)
		{
			MissingScenes.Add(EventId);
			continue;
		}

		// The audit checks the full-bundle scene (full.E01 is intentionally not
		// merged as the runtime scene because opening.json owns E01).
		const FString BundleSceneId = FString::Printf(TEXT("full.%s"), *EventId);
		const FDAStoryScene* Scene = Scenes.Find(BundleSceneId);
		if (!Scene)
		{
			MissingScenes.Add(EventId);
			continue;
		}
		if (!Scenes.Contains(Event->Scene))
		{
			MissingScenes.Add(FString::Printf(TEXT("%s:runtime:%s"), *EventId, *Event->Scene));
		}

		const TSharedPtr<FJsonObject>* FullDocPtr = FullCampaignEventDocs.Find(EventId);
		const TSharedPtr<FJsonObject>& EventRaw = (FullDocPtr && FullDocPtr->IsValid()) ? *FullDocPtr : Event->Raw;

		if (Scene->Commands.Num() < 3 || Scene->Commands.Num() > 8)
		{
			++BadCommandCounts;
		}

		for (const FString& Key : DAJson::ReadStringArray(EventRaw, TEXT("dialogue_keys")))
		{
			if (!Lines.Contains(Key))
			{
				MissingLines.Add(FString::Printf(TEXT("%s:%s"), *EventId, *Key));
			}
		}

		for (const FDAStoryCommand& Command : Scene->Commands)
		{
			if (Command.Type == EDAStoryCommandType::Unknown)
			{
				++UnknownCommands;
			}
			if (Command.Type == EDAStoryCommandType::Dialogue && !Lines.Contains(Command.Key))
			{
				MissingLines.Add(FString::Printf(TEXT("%s:%s"), *Scene->Id, *Command.Key));
			}
			if (Command.Type == EDAStoryCommandType::Camera && !Command.Anchor.IsEmpty()
				&& AnchorIds.Num() > 0 && !AnchorIds.Contains(Command.Anchor))
			{
				++MissingAnchorCount;
				MissingAnchorScenes.Add(FString::Printf(TEXT("%s:%s"), *Scene->Id, *Command.Anchor));
			}
		}

		const FString EventAnchor = DAJson::ReadString(EventRaw, TEXT("anchor"));
		if (!EventAnchor.IsEmpty() && AnchorIds.Num() > 0 && !AnchorIds.Contains(EventAnchor))
		{
			++MissingAnchorCount;
			MissingAnchorScenes.Add(FString::Printf(TEXT("%s:event_anchor:%s"), *EventId, *EventAnchor));
		}
	}

	AddCheck(TEXT("every event has a loaded scene"), MissingScenes.Num() == 0,
		FString::Join(MissingScenes, TEXT(", ")));
	AddCheck(TEXT("scene command counts are 3-8"), BadCommandCounts == 0, FString::FromInt(BadCommandCounts));
	AddCheck(TEXT("all scene commands are known"), UnknownCommands == 0, FString::FromInt(UnknownCommands));
	AddCheck(TEXT("all dialogue keys resolve"), MissingLines.Num() == 0,
		FString::Join(MissingLines, TEXT(", ")));
	AddCheck(TEXT("A08 anchors resolve"), MissingAnchorCount == 0,
		FString::Join(MissingAnchorScenes, TEXT(", ")));

	// ---------------------------------------------------------------- rewards
	TSharedPtr<FJsonObject> ShopRoot;
	FString ShopError;
	TSet<FString> PackIds;
	if (LoadContentJsonObject(TEXT("Data/Shop/packs.json"), ShopRoot, ShopError))
	{
		const TArray<TSharedPtr<FJsonValue>>* PackValues = nullptr;
		if (ShopRoot->TryGetArrayField(TEXT("packs"), PackValues) && PackValues)
		{
			for (const TSharedPtr<FJsonValue>& Value : *PackValues)
			{
				const TSharedPtr<FJsonObject> Pack = Value.IsValid() ? Value->AsObject() : TSharedPtr<FJsonObject>();
				FString PackId;
				if (Pack.IsValid() && Pack->TryGetStringField(TEXT("id"), PackId))
				{
					PackIds.Add(PackId);
				}
			}
		}
	}
	else
	{
		AddInfo(FString::Printf(TEXT("A06 shop packs unavailable: %s"), *ShopError));
	}

	static const TSet<FString> KnownRewardTypes = {
		TEXT("dp"), TEXT("email_unlock"), TEXT("card"), TEXT("card_by_result"), TEXT("tutorial"),
		TEXT("temporary_title"), TEXT("restore_title"), TEXT("pack_by_dorm"), TEXT("dorm_unlock"),
		TEXT("exam_exemption"), TEXT("unlock_duel"), TEXT("dp_multiplier"), TEXT("flag"), TEXT("item"),
		TEXT("choice_reward"), TEXT("dp_equal_remaining_lp"), TEXT("card_by_partner"), TEXT("pack"),
		TEXT("name_change"), TEXT("title")
	};
	static const TSet<FString> KnownOutcomeTypes = {
		TEXT("set_flag"), TEXT("flag"), TEXT("add_counter"), TEXT("counter"), TEXT("reward"),
		TEXT("grant_reward"), TEXT("set_calendar"), TEXT("set_objective"), TEXT("complete_event"),
		TEXT("unlock_email"), TEXT("grant_dp"), TEXT("grant_card"), TEXT("grant_pack"),
		TEXT("grant_deck"), TEXT("set_title"), TEXT("set_dorm"), TEXT("dorm_unlock"), TEXT("double_dp"),
		TEXT("dp_multiplier"), TEXT("exam_exemption"), TEXT("unlock_duel"), TEXT("item"),
		TEXT("name_change"), TEXT("temporary_title"), TEXT("restore_title"), TEXT("next_event"),
		TEXT("grant_dp_from_last_lp"), TEXT("dp_equal_remaining_lp"), TEXT("select_deck")
	};

	TArray<FString> BadRewards;
	TArray<FString> BadOutcomes;
	TArray<FString> BadPacks;
	TArray<FString> MissingRewardIds;
	int32 RewardCount = 0;
	for (const FString& EventId : FullCampaignEventIds)
	{
		const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
		const TSharedPtr<FJsonObject>* FullDocPtr = FullCampaignEventDocs.Find(EventId);
		const TSharedPtr<FJsonObject> EventRaw = (FullDocPtr && FullDocPtr->IsValid()) ? *FullDocPtr : (Event ? Event->Raw : TSharedPtr<FJsonObject>());
		if (!EventRaw.IsValid())
		{
			continue;
		}

		const TArray<TSharedPtr<FJsonValue>>* RewardValues = nullptr;
		if (EventRaw->TryGetArrayField(TEXT("rewards"), RewardValues) && RewardValues)
		{
			for (const TSharedPtr<FJsonValue>& Value : *RewardValues)
			{
				const TSharedPtr<FJsonObject> Reward = Value.IsValid() ? Value->AsObject() : TSharedPtr<FJsonObject>();
				if (!Reward.IsValid())
				{
					continue;
				}
				++RewardCount;
				const FString Type = DAJson::ReadString(Reward, TEXT("type"));
				if (!KnownRewardTypes.Contains(Type))
				{
					BadRewards.Add(FString::Printf(TEXT("%s:%s"), *EventId, *Type));
				}
				if (Type == TEXT("pack"))
				{
					const FString PackId = DAJson::ReadString(Reward, TEXT("pack"), DAJson::ReadString(Reward, TEXT("pack_id")));
					if (!PackIds.Contains(PackId))
					{
						BadPacks.Add(FString::Printf(TEXT("%s:%s"), *EventId, *PackId));
					}
				}
				else if (Type == TEXT("pack_by_dorm"))
				{
					for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : Reward->Values)
					{
						const FString Key(*Pair.Key);
						if (Key.Equals(TEXT("type"), ESearchCase::IgnoreCase)
							|| Key.Equals(TEXT("note"), ESearchCase::IgnoreCase)
							|| Key.Equals(TEXT("source"), ESearchCase::IgnoreCase))
						{
							continue;
						}
						if (Pair.Value.IsValid() && Pair.Value->Type == EJson::String)
						{
							const FString PackId = Pair.Value->AsString();
							if (!PackIds.Contains(PackId))
							{
								BadPacks.Add(FString::Printf(TEXT("%s:%s"), *EventId, *PackId));
							}
						}
					}
				}
			}
		}

		for (const TSharedPtr<FJsonObject>& Outcome : Event->Outcomes)
		{
			const FString Type = DAJson::ReadString(Outcome, TEXT("type"));
			if (!KnownOutcomeTypes.Contains(Type))
			{
				BadOutcomes.Add(FString::Printf(TEXT("%s:%s"), *EventId, *Type));
			}
			if (Type == TEXT("reward") || Type == TEXT("grant_reward"))
			{
				const FString RewardId = DAJson::ReadString(Outcome, TEXT("reward_id"), DAJson::ReadString(Outcome, TEXT("id")));
				if (!Rewards.Contains(RewardId))
				{
					MissingRewardIds.Add(FString::Printf(TEXT("%s:%s"), *EventId, *RewardId));
				}
			}
		}
	}

	AddCheck(TEXT("reward types are known"), BadRewards.Num() == 0,
		FString::Join(BadRewards, TEXT(", ")));
	AddCheck(TEXT("reward packs exist in A06 shop"), BadPacks.Num() == 0,
		FString::Join(BadPacks, TEXT(", ")));
	AddCheck(TEXT("outcome types are supported"), BadOutcomes.Num() == 0,
		FString::Join(BadOutcomes, TEXT(", ")));
	AddCheck(TEXT("reward ids resolve"), MissingRewardIds.Num() == 0,
		FString::Join(MissingRewardIds, TEXT(", ")));
	AddInfo(FString::Printf(TEXT("%d canon reward records audited"), RewardCount));

	// ---------------------------------------------------------------- A07 duels
	TSharedPtr<FJsonObject> RosterRoot;
	FString RosterError;
	TMap<FString, TSet<FString>> OpponentDecks;
	if (LoadContentJsonObject(TEXT("Data/Opponents/roster.json"), RosterRoot, RosterError))
	{
		const TArray<TSharedPtr<FJsonValue>>* DuelistValues = nullptr;
		if (RosterRoot->TryGetArrayField(TEXT("duelists"), DuelistValues) && DuelistValues)
		{
			for (const TSharedPtr<FJsonValue>& Value : *DuelistValues)
			{
				const TSharedPtr<FJsonObject> Duelist = Value.IsValid() ? Value->AsObject() : TSharedPtr<FJsonObject>();
				FString OpponentId;
				if (!Duelist.IsValid() || !Duelist->TryGetStringField(TEXT("id"), OpponentId))
				{
					continue;
				}
				TSet<FString>& Decks = OpponentDecks.Add(OpponentId);
				for (const FString& DeckId : DAJson::ReadStringArray(Duelist, TEXT("decks")))
				{
					Decks.Add(DeckId);
				}
			}
		}
	}
	else
	{
		AddInfo(FString::Printf(TEXT("A07 roster unavailable: %s"), *RosterError));
	}

	TArray<FString> BadOpponents;
	TArray<FString> BadDecks;
	int32 DuelCount = 0;
	auto ValidateDuel = [&](const FString& Source, const FString& OpponentId, const FString& DeckId)
	{
		++DuelCount;
		const TSet<FString>* Decks = OpponentDecks.Find(OpponentId);
		if (!Decks)
		{
			BadOpponents.Add(FString::Printf(TEXT("%s:%s"), *Source, *OpponentId));
			return;
		}
		if (!DeckId.IsEmpty() && !Decks->Contains(DeckId))
		{
			BadDecks.Add(FString::Printf(TEXT("%s:%s/%s"), *Source, *OpponentId, *DeckId));
		}
	};

	for (const FString& EventId : FullCampaignEventIds)
	{
		const TSharedPtr<FJsonObject>* FullDocPtr = FullCampaignEventDocs.Find(EventId);
		if (!FullDocPtr || !FullDocPtr->IsValid())
		{
			continue;
		}
		const TArray<TSharedPtr<FJsonValue>>* DuelValues = nullptr;
		if ((*FullDocPtr)->TryGetArrayField(TEXT("duels"), DuelValues) && DuelValues)
		{
			for (const TSharedPtr<FJsonValue>& Value : *DuelValues)
			{
				const TSharedPtr<FJsonObject> Duel = Value.IsValid() ? Value->AsObject() : TSharedPtr<FJsonObject>();
				if (Duel.IsValid())
				{
					ValidateDuel(EventId, DAJson::ReadString(Duel, TEXT("opponent_id"), DAJson::ReadString(Duel, TEXT("opponent"))),
						DAJson::ReadString(Duel, TEXT("opponent_deck_id"), DAJson::ReadString(Duel, TEXT("deck"))));
				}
			}
		}
	}

	for (const TPair<FString, FDAStoryScene>& Pair : Scenes)
	{
		if (!Pair.Key.StartsWith(TEXT("full.")))
		{
			continue;
		}
		for (const FDAStoryCommand& Command : Pair.Value.Commands)
		{
			if (Command.Type == EDAStoryCommandType::Duel)
			{
				ValidateDuel(Pair.Key, Command.OpponentId, Command.OpponentDeckId);
			}
		}
	}

	for (const TPair<FString, TSharedPtr<FJsonObject>>& Pair : EmailContacts)
	{
		const TArray<TSharedPtr<FJsonValue>>* RequestValues = nullptr;
		if (Pair.Value.IsValid() && Pair.Value->TryGetArrayField(TEXT("duel_requests"), RequestValues) && RequestValues)
		{
			for (const TSharedPtr<FJsonValue>& Value : *RequestValues)
			{
				const TSharedPtr<FJsonObject> Request = Value.IsValid() ? Value->AsObject() : TSharedPtr<FJsonObject>();
				if (Request.IsValid())
				{
					ValidateDuel(FString::Printf(TEXT("email:%s"), *Pair.Key),
						DAJson::ReadString(Request, TEXT("opponent")), DAJson::ReadString(Request, TEXT("deck")));
				}
			}
		}
	}

	AddCheck(TEXT("A07 opponent ids resolve"), BadOpponents.Num() == 0,
		FString::Join(BadOpponents, TEXT(", ")));
	AddCheck(TEXT("A07 opponent decks resolve"), BadDecks.Num() == 0,
		FString::Join(BadDecks, TEXT(", ")));
	AddInfo(FString::Printf(TEXT("%d duel references audited"), DuelCount));
	AddCheck(TEXT("email contacts loaded"), EmailContacts.Num() == 6, FString::FromInt(EmailContacts.Num()));

	// ---------------------------------------------------------------- availability
	// Snapshot and restore so the audit does not overwrite a live profile.
	TSharedPtr<FJsonObject> ProfileSnapshot = MakeShared<FJsonObject>();
	TSharedPtr<FJsonObject> CalendarSnapshot = MakeShared<FJsonObject>();
	Profile->WriteSaveData(ProfileSnapshot);
	Calendar->WriteSaveData(CalendarSnapshot);

	UDAInventorySubsystem* Inventory = GetGameInstance() ? GetGameInstance()->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	int32 AddedCard348 = 0;

	auto SetOpeningBaseline = [Profile]()
	{
		Profile->ResetToDefaults();
		Profile->SetFlag(TEXT("new_game"), true);
		Profile->SetFlag(TEXT("new_game_started"), true);
		Profile->SetFlag(TEXT("registered"), true);
		Profile->SetFlag(TEXT("tutorial_complete"), true);
		Profile->SetFlag(TEXT("first_free_roam"), true);
		Profile->SetFlag(TEXT("opening_complete"), true);
		Profile->SetFlag(TEXT("shop_unlocked"), true);
		Profile->SetFlag(TEXT("save_unlocked"), true);
		Profile->SetFlag(FDAEventGraph::EventCompletionFlag(TEXT("E01")), true);
		Profile->SetFlag(FDAEventGraph::EventCompletionFlag(TEXT("E01b")), true);
	};

	auto WalkTwelveMonths = [this, Profile, Calendar](TSet<FString>& OutAvailable)
	{
		const EDADayPeriod Periods[] = { EDADayPeriod::AM, EDADayPeriod::PM, EDADayPeriod::Night };
		// A02's Year is the school year: index 0 is October and the year rolls
		// over after September. Walk one complete school year, not two literal
		// calendar years.
		for (int32 MonthIndex = 0; MonthIndex < 12; ++MonthIndex)
		{
			const int32 Year = 1;
			const int32 Days = Calendar->GetDaysInMonth(Year, MonthIndex);
			for (int32 Day = 1; Day <= Days; ++Day)
			{
				for (EDADayPeriod Period : Periods)
				{
					Calendar->SetDate(Year, MonthIndex, Day, Period);
					for (const FString& EventId : FullCampaignEventIds)
					{
						const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
						if (!Event)
						{
							continue;
						}
						FString Reason;
						if (EventGraph.EvaluateTrigger(*Event, Profile, Calendar, Reason)
							&& EventGraph.EvaluateRequirements(*Event, Profile, Calendar, Reason))
						{
							OutAvailable.Add(EventId);
						}
					}
				}
			}
		}
	};

	TSet<FString> CounterlessAvailable;
	SetOpeningBaseline();
	Calendar->SetDate(1, 0, 1, EDADayPeriod::AM);
	WalkTwelveMonths(CounterlessAvailable);

	TArray<FString> Unreachable = FullCampaignEventIds.Array();
	Unreachable.Sort();
	for (int32 Index = Unreachable.Num() - 1; Index >= 0; --Index)
	{
		if (CounterlessAvailable.Contains(Unreachable[Index]))
		{
			Unreachable.RemoveAt(Index);
		}
	}
	AddInfo(FString::Printf(TEXT("%d/%d events reachable without counters"), CounterlessAvailable.Num(), FullCampaignEventIds.Num()));
	AddInfo(FString::Printf(TEXT("unreachable without counters: %s"),
		Unreachable.Num() > 0 ? *FString::Join(Unreachable, TEXT(", ")) : TEXT("<none>")));

	// Maxed-progress pass: proves every event is reachable once its gates are met.
	TSet<FString> AllFlags;
	TSet<FString> AllCounters;
	TSet<FString> AllEvents;
	for (const FString& EventId : FullCampaignEventIds)
	{
		if (const FDAEventDefinition* Event = EventGraph.FindEvent(EventId))
		{
			CollectEventState(*Event, AllFlags, AllCounters, AllEvents);
		}
	}

	TSet<FString> MaxedAvailable;
	SetOpeningBaseline();
	for (const FString& Counter : AllCounters)
	{
		Profile->SetCounter(Counter, 9999);
	}
	for (const FString& Flag : AllFlags)
	{
		Profile->SetFlag(Flag, true);
	}
	for (const FString& EventId : AllEvents)
	{
		Profile->SetFlag(FDAEventGraph::EventCompletionFlag(EventId), true);
	}
	Profile->SetTitle(TEXT("Dropout Boy"));
	Profile->SetCounter(TEXT("card_348"), 1);
	if (Inventory && Inventory->GetCount(348) <= 0)
	{
		AddedCard348 = Inventory->AddCard(348, 1);
	}

	const EDADorm Dorms[] = { EDADorm::Slifer, EDADorm::Ra, EDADorm::Obelisk };
	for (EDADorm Dorm : Dorms)
	{
		Profile->SetDorm(Dorm);
		Calendar->SetDate(1, 0, 1, EDADayPeriod::AM);
		WalkTwelveMonths(MaxedAvailable);
	}

	TArray<FString> MaxedMissing = FullCampaignEventIds.Array();
	MaxedMissing.Sort();
	for (int32 Index = MaxedMissing.Num() - 1; Index >= 0; --Index)
	{
		if (MaxedAvailable.Contains(MaxedMissing[Index]))
		{
			MaxedMissing.RemoveAt(Index);
		}
	}
	AddCheck(TEXT("all 35 events reachable with progress"), MaxedMissing.Num() == 0,
		FString::Join(MaxedMissing, TEXT(", ")));

	// Restore the live profile/calendar and inventory.
	if (AddedCard348 > 0 && Inventory)
	{
		Inventory->RemoveCard(348, AddedCard348);
	}
	FString RestoreError;
	Profile->ReadSaveData(ProfileSnapshot, RestoreError);
	Calendar->ReadSaveData(CalendarSnapshot, RestoreError);
	if (!RestoreError.IsEmpty())
	{
		AddInfo(FString::Printf(TEXT("snapshot restore warning: %s"), *RestoreError));
	}

	// StartEvent availability is structural for every canon id.
	TArray<FString> NoScene;
	for (const FString& EventId : FullCampaignEventIds)
	{
		const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
		if (!Event || !Scenes.Contains(Event->Scene))
		{
			NoScene.Add(EventId);
		}
	}
	AddCheck(TEXT("StartEvent can resolve every id"), NoScene.Num() == 0,
		FString::Join(NoScene, TEXT(", ")));

	const double Elapsed = FPlatformTime::Seconds() - StartTime;
	bool bAllPass = true;
	for (const FString& Line : Report)
	{
		if (Line.StartsWith(TEXT("FAIL")))
		{
			bAllPass = false;
		}
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("FullStorySelfTest: %s"), *Line);
	}
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("FullStorySelfTest: %s in %.3fs"),
		bAllPass ? TEXT("PASS") : TEXT("FAIL"), Elapsed);

	LastFullSelfTestReport = FString::Join(Report, TEXT("\n"));
	LastFullSelfTestReport += FString::Printf(TEXT("\n%s in %.3fs"),
		bAllPass ? TEXT("PASS") : TEXT("FAIL"), Elapsed);
	return bAllPass;
}



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
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
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
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
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

static FAutoConsoleCommandWithWorldAndArgs GDAFullStorySelfTestCommand(
	TEXT("da.FullStorySelfTest"),
	TEXT("Run the headless 35-event full-campaign audit."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
	{
		if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(World))
		{
			Story->RunFullStorySelfTest();
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("da.FullStorySelfTest: story subsystem not found."));
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
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
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
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
	{
		if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(World))
		{
			Story->DebugLogState();
		}
	}));
