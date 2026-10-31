// Duel Academy Island - in-engine story playthrough harness.
//
// The harness deliberately uses the public A02/A06/A07 seams instead of
// touching their save/economy/opponent internals. It plays the real opening,
// advances the real calendar, and drives the real story scene queue. External
// gates that no current lane produces (post_game, room-stay and walk-home
// flags) are simulated through UDAProfileSubsystem::SetFlag and reported.

#include "DAStoryPlaythroughTest.h"

#include "DAStorySubsystem.h"
#include "DAEventGraph.h"
#include "DAProfileSubsystem.h"
#include "DACalendarSubsystem.h"
#include "DAInventorySubsystem.h"
#include "DATitleSystem.h"
#include "DuelAcademyIsland.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/ScopeExit.h"
#include "Templates/Function.h"

namespace
{
	const TCHAR* const PlaythroughPrefix = TEXT("StoryPlaythroughTest");

	struct FStoryPlayEventResult
	{
		FString EventId;
		FString Title;
		bool bStarted = false;
		bool bCompleted = false;
		bool bForced = false;
		FString NaturalBlockers;
		FString NaturalBlockerDate;
		TArray<FString> ForcedGates;
		TArray<FString> EffectFailures;
		FString Failure;

		int32 DPBefore = 0;
		int32 DPAfter = 0;
		int32 DialogueCommands = 0;
		int32 ChoiceCommands = 0;
		int32 DuelCommands = 0;
		int32 DuelResolved = 0;
		int32 Rewards = 0;
		int32 Flags = 0;
		int32 Outcomes = 0;
		int32 MissingDialogue = 0;
		int32 MissingScene = 0;
		int32 UnknownCommand = 0;
		int32 UnknownOutcome = 0;
		int32 StartAttempts = 0;

		bool Passed() const
		{
			return bStarted && bCompleted && Failure.IsEmpty() && EffectFailures.Num() == 0;
		}
	};

	FString PlayReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, const FString& Fallback = FString())
	{
		FString Value;
		if (Object.IsValid() && Object->TryGetStringField(Field, Value))
		{
			return Value;
		}
		return Fallback;
	}

	int32 PlayReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Fallback = 0)
	{
		int32 Value = Fallback;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return Value;
	}

	bool PlayReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, bool bFallback = false)
	{
		bool bValue = bFallback;
		if (Object.IsValid())
		{
			Object->TryGetBoolField(Field, bValue);
		}
		return bValue;
	}

	TArray<TSharedPtr<FJsonObject>> PlayReadObjectArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
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

	TArray<FString> PlayReadStringArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
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

	int32 PlayMonthNumberToIndex(int32 MonthNumber)
	{
		return ((MonthNumber - 10) % 12 + 12) % 12;
	}

	bool StoryTestIsA02OwnedCounter(const FString& Counter)
	{
		static const TSet<FString> Owned = {
			TEXT("wins_total"), TEXT("wins_jaden"), TEXT("wins_syrus"), TEXT("wins_chumley"),
			TEXT("losses_total"), TEXT("draws_total"), TEXT("duels_total"),
			TEXT("dp_earned_total"), TEXT("timed_clears"), TEXT("written_correct"),
			TEXT("battle_damage_total"), TEXT("monsters_destroyed_total"), TEXT("lp_lost_total")
		};
		return Owned.Contains(Counter);
	}

	FString JoinReasons(const TArray<FString>& Reasons)
	{
		return Reasons.Num() > 0 ? FString::Join(Reasons, TEXT("; ")) : FString(TEXT("<none>"));
	}

	void DescribeCondition(const TSharedPtr<FJsonObject>& Condition, const UDAProfileSubsystem* Profile,
		const UDACalendarSubsystem* Calendar, TArray<FString>& OutReasons)
	{
		if (!Condition.IsValid())
		{
			return;
		}

		FString Reason;
		if (FDAEventGraph::EvaluateCondition(Condition, Profile, Calendar, Reason))
		{
			return;
		}

		const FString Kind = PlayReadString(Condition, TEXT("type"));
		if (Kind.IsEmpty() || Kind == TEXT("all") || Kind == TEXT("any"))
		{
			TArray<TSharedPtr<FJsonObject>> Children = PlayReadObjectArray(Condition, TEXT("conditions"));
			if (Children.Num() == 0)
			{
				Children = PlayReadObjectArray(Condition, TEXT("all"));
			}
			if (Children.Num() == 0)
			{
				Children = PlayReadObjectArray(Condition, TEXT("any"));
			}
			for (const TSharedPtr<FJsonObject>& Child : Children)
			{
				DescribeCondition(Child, Profile, Calendar, OutReasons);
			}
		}

		if (Reason.IsEmpty())
		{
			Reason = FString::Printf(TEXT("%s condition failed"), Kind.IsEmpty() ? TEXT("group") : *Kind);
		}
		OutReasons.AddUnique(Reason);
	}

	int32 EventSortOrder(const FDAEventDefinition* Event)
	{
		if (!Event)
		{
			return MAX_int32;
		}
		return Event->Raw.IsValid() ? PlayReadInt(Event->Raw, TEXT("order"), Event->Priority) : Event->Priority;
	}
}

bool UDAStorySubsystem::RunStoryPlaythroughTest()
{
	TArray<FString> Report;
	int32 Passed = 0;
	int32 Failed = 0;

	auto AddCheck = [&Report, &Passed, &Failed](const FString& Label, bool bPass, const FString& Detail)
	{
		FString Suffix;
		if (!Detail.IsEmpty())
		{
			Suffix = FString::Printf(TEXT(" (%s)"), *Detail);
		}
		Report.Add(FString::Printf(TEXT("%s %s%s"), bPass ? TEXT("PASS") : TEXT("FAIL"), *Label, *Suffix));
		if (bPass)
		{
			++Passed;
		}
		else
		{
			++Failed;
		}
	};
	auto AddInfo = [&Report](const FString& Text)
	{
		Report.Add(FString::Printf(TEXT("INFO %s"), *Text));
	};

	const double StartTime = FPlatformTime::Seconds();

	if (bRunning)
	{
		LastPlaythroughReport = FString::Printf(TEXT("FAIL cannot start while %s is running"), *CurrentEventId);
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("%s: %s"), PlaythroughPrefix, *LastPlaythroughReport);
		return false;
	}

	UGameInstance* GameInstance = GetGameInstance();
	UDAProfileSubsystem* Profile = ResolveProfile();
	UDACalendarSubsystem* Calendar = ResolveCalendar();
	UDAInventorySubsystem* Inventory = GameInstance ? GameInstance->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	UDATitleSystem* TitleSystem = GameInstance ? GameInstance->GetSubsystem<UDATitleSystem>() : nullptr;

	if (!LoadFullCampaignData())
	{
		LastPlaythroughReport = TEXT("FAIL full campaign data did not load");
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("%s: %s"), PlaythroughPrefix, *LastPlaythroughReport);
		return false;
	}
	if (!Profile || !Calendar)
	{
		LastPlaythroughReport = TEXT("FAIL profile/calendar subsystems are unavailable");
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("%s: %s"), PlaythroughPrefix, *LastPlaythroughReport);
		return false;
	}

	AddCheck(TEXT("full campaign loaded"), bFullCampaignLoaded, FString::FromInt(FullCampaignEventIds.Num()));
	AddCheck(TEXT("35 canonical events"), FullCampaignEventIds.Num() == 35, FString::FromInt(FullCampaignEventIds.Num()));

	// ------------------------------------------------------------ preflight
	TArray<FString> MissingScenes;
	TArray<FString> MissingLines;
	TArray<FString> UnknownCommands;
	TArray<FString> BadDuelCommands;
	TArray<FString> MissingRewardIds;
	int32 SceneCommands = 0;
	int32 DialogueKeys = 0;
	int32 DuelCommands = 0;

	for (const TPair<FString, FDAStoryScene>& Pair : Scenes)
	{
		if (!Pair.Key.StartsWith(TEXT("opening.")) && !Pair.Key.StartsWith(TEXT("full.")))
		{
			continue;
		}
		for (const FDAStoryCommand& Command : Pair.Value.Commands)
		{
			++SceneCommands;
			if (Command.Type == EDAStoryCommandType::Unknown)
			{
				UnknownCommands.Add(Pair.Key);
			}
			else if (Command.Type == EDAStoryCommandType::Dialogue || Command.Type == EDAStoryCommandType::Choice)
			{
				++DialogueKeys;
				if (!Lines.Contains(Command.Key))
				{
					MissingLines.Add(FString::Printf(TEXT("%s:%s"), *Pair.Key, *Command.Key));
				}
			}
			else if (Command.Type == EDAStoryCommandType::Duel)
			{
				++DuelCommands;
				if (Command.OpponentId.IsEmpty())
				{
					BadDuelCommands.Add(Pair.Key);
				}
			}
		}
	}

	for (const FString& EventId : FullCampaignEventIds)
	{
		const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
		if (!Event)
		{
			MissingScenes.Add(FString::Printf(TEXT("%s:no-event"), *EventId));
			continue;
		}
		if (!Scenes.Contains(Event->Scene))
		{
			MissingScenes.Add(FString::Printf(TEXT("%s:%s"), *EventId, *Event->Scene));
		}
		for (const FString& Key : PlayReadStringArray(Event->Raw, TEXT("dialogue_keys")))
		{
			if (!Lines.Contains(Key))
			{
				MissingLines.Add(FString::Printf(TEXT("%s:%s"), *EventId, *Key));
			}
		}
		for (const TSharedPtr<FJsonObject>& Outcome : Event->Outcomes)
		{
			const FString Type = PlayReadString(Outcome, TEXT("type"));
			if (Type == TEXT("reward") || Type == TEXT("grant_reward"))
			{
				const FString RewardId = PlayReadString(Outcome, TEXT("reward_id"),
					PlayReadString(Outcome, TEXT("id")));
				if (!Rewards.Contains(RewardId))
				{
					MissingRewardIds.Add(FString::Printf(TEXT("%s:%s"), *EventId, *RewardId));
				}
			}
		}
	}

	AddCheck(TEXT("every canonical event has a loaded scene"), MissingScenes.Num() == 0,
		FString::Join(MissingScenes, TEXT(", ")));
	AddCheck(TEXT("every dialogue/choice key resolves"), MissingLines.Num() == 0,
		FString::Join(MissingLines, TEXT(", ")));
	AddCheck(TEXT("every scene command is supported"), UnknownCommands.Num() == 0,
		FString::Join(UnknownCommands, TEXT(", ")));
	AddCheck(TEXT("every duel command names an opponent"), BadDuelCommands.Num() == 0,
		FString::Join(BadDuelCommands, TEXT(", ")));
	AddCheck(TEXT("every outcome reward id resolves"), MissingRewardIds.Num() == 0,
		FString::Join(MissingRewardIds, TEXT(", ")));
	AddInfo(FString::Printf(TEXT("%d scenes, %d commands, %d dialogue/choice keys, %d duel commands"),
		Scenes.Num(), SceneCommands, DialogueKeys, DuelCommands));

	// ------------------------------------------------------------ snapshot
	TSharedPtr<FJsonObject> ProfileSnapshot = MakeShared<FJsonObject>();
	TSharedPtr<FJsonObject> CalendarSnapshot = MakeShared<FJsonObject>();
	Profile->WriteSaveData(ProfileSnapshot);
	Calendar->WriteSaveData(CalendarSnapshot);
	const FString StorySnapshot = SaveState();
	const FString InventorySnapshot = Inventory ? Inventory->ExportStateJson() : FString();

	FString SavedDeckId;
	if (UObject* DeckProvider = Profile->GetDeckProvider())
	{
		if (IDAProfileDeckInterface* Decks = Cast<IDAProfileDeckInterface>(DeckProvider))
		{
			SavedDeckId = Decks->GetActiveDeckId();
		}
	}

	const bool bSavedHeadless = bHeadless;
	const bool bSavedFastForward = bFastForward;
	const bool bSavedManualAudience = bManualAudience;
	const bool bSavedSuppressAutoStart = bSuppressAutoStart;

	bool bRestored = false;
	auto RestoreSnapshot = [&]()
	{
		if (bRestored)
		{
			return;
		}
		bRestored = true;

		FString RestoreError;
		if (!StorySnapshot.IsEmpty() && !LoadState(StorySnapshot, RestoreError))
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("%s: story snapshot restore failed: %s"),
				PlaythroughPrefix, *RestoreError);
		}
		Profile->ReadSaveData(ProfileSnapshot, RestoreError);
		if (!RestoreError.IsEmpty())
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("%s: profile snapshot restore warning: %s"),
				PlaythroughPrefix, *RestoreError);
		}
		Calendar->ReadSaveData(CalendarSnapshot, RestoreError);
		if (!RestoreError.IsEmpty())
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("%s: calendar snapshot restore warning: %s"),
				PlaythroughPrefix, *RestoreError);
		}
		if (Inventory && !InventorySnapshot.IsEmpty())
		{
			Inventory->ImportStateJson(InventorySnapshot, RestoreError);
			if (!RestoreError.IsEmpty())
			{
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("%s: inventory snapshot restore warning: %s"),
					PlaythroughPrefix, *RestoreError);
			}
		}
		if (!SavedDeckId.IsEmpty())
		{
			if (UObject* DeckProvider = Profile->GetDeckProvider())
			{
				if (IDAProfileDeckInterface* Decks = Cast<IDAProfileDeckInterface>(DeckProvider))
				{
					Decks->SetActiveDeckId(SavedDeckId);
				}
			}
		}

		bSuppressAutoStart = bSavedSuppressAutoStart;
		bManualAudience = bSavedManualAudience;
		bFastForward = bSavedFastForward;
		bHeadless = bSavedHeadless;
	};
	ON_SCOPE_EXIT
	{
		RestoreSnapshot();
	};

	// ------------------------------------------------------------ fresh run
	ResetRuntimeState();
	Profile->InitializeNewGame(TEXT("ALEX"));
	Calendar->SetDate(1, 0, 1, EDADayPeriod::AM);
	if (Inventory)
	{
		Inventory->ResetCollection();
	}

	bSuppressAutoStart = true;
	bManualAudience = true;
	bFastForward = true;

	StartOpeningFresh();
	bHeadless = true;

	FString OpeningError;
	FString Reason;
	FStoryPlayEventResult OpeningRunResult;
	OpeningRunResult.EventId = TEXT("E01");

	if (!bRunning)
	{
		OpeningError = TEXT("StartOpeningFresh did not start E01");
	}
	else
	{
		PlaythroughMissingDialogue = 0;
		PlaythroughMissingScene = 0;
		PlaythroughUnknownCommand = 0;
		PlaythroughUnknownOutcome = 0;
		PlaythroughDialogueCommands = 0;
		PlaythroughChoiceCommands = 0;
		PlaythroughDuelCommands = 0;
		PlaythroughDuelResolved = 0;
		PlaythroughRewardCommands = 0;
		PlaythroughFlagCommands = 0;
		PlaythroughOutcomesApplied = 0;

		OpeningRunResult.bStarted = true;
		OpeningRunResult.DPBefore = Profile->GetDP();

		int32 Steps = 0;
		while (bRunning && Steps++ < 8192)
		{
			if (bWaitingForChoice)
			{
				Choose(0);
			}
			else if (bWaitingForDuel)
			{
				NotifyDuelResult(true, false);
			}
			else if (bWaitingForTimer || bWaitingForDialogue)
			{
				Advance();
			}
			else if (bPendingContinue)
			{
				bPendingContinue = false;
				PumpQueue();
			}
			else
			{
				PumpQueue();
			}
		}
		OpeningRunResult.DPAfter = Profile->GetDP();
		OpeningRunResult.bCompleted = IsEventCompleteRuntime(TEXT("E01"));
		OpeningRunResult.DialogueCommands = PlaythroughDialogueCommands;
		OpeningRunResult.ChoiceCommands = PlaythroughChoiceCommands;
		OpeningRunResult.DuelCommands = PlaythroughDuelCommands;
		OpeningRunResult.DuelResolved = PlaythroughDuelResolved;
		OpeningRunResult.Rewards = PlaythroughRewardCommands;
		OpeningRunResult.Flags = PlaythroughFlagCommands;
		OpeningRunResult.Outcomes = PlaythroughOutcomesApplied;
		OpeningRunResult.MissingDialogue = PlaythroughMissingDialogue;
		OpeningRunResult.MissingScene = PlaythroughMissingScene;
		OpeningRunResult.UnknownCommand = PlaythroughUnknownCommand;
		OpeningRunResult.UnknownOutcome = PlaythroughUnknownOutcome;

		if (Steps >= 8192)
		{
			OpeningError = TEXT("E01 command guard exceeded");
		}
		else if (!OpeningRunResult.bCompleted)
		{
			OpeningError = TEXT("E01 did not complete");
		}
		if (!OpeningError.IsEmpty() && bRunning)
		{
			FinishEvent(false, false);
		}
	}

	// ------------------------------------------------------------ results map
	TArray<FString> OrderedIds = FullCampaignEventIds.Array();
	OrderedIds.Sort([this](const FString& A, const FString& B)
	{
		const int32 OrderA = EventSortOrder(EventGraph.FindEvent(A));
		const int32 OrderB = EventSortOrder(EventGraph.FindEvent(B));
		return OrderA != OrderB ? OrderA < OrderB : A < B;
	});

	TMap<FString, FStoryPlayEventResult> Results;
	for (const FString& EventId : OrderedIds)
	{
		FStoryPlayEventResult& Result = Results.Add(EventId, FStoryPlayEventResult());
		Result.EventId = EventId;
		if (const FDAEventDefinition* Event = EventGraph.FindEvent(EventId))
		{
			Result.Title = Event->Title;
		}
	}
	// Keep references stable even if a data requirement points at a supporting
	// event such as E01b; Map reallocation while a result reference is held would
	// otherwise be a use-after-free in the recursive forced pass.
	for (const FDAEventDefinition& Event : EventGraph.GetEvents())
	{
		if (!Results.Contains(Event.Id))
		{
			FStoryPlayEventResult& Result = Results.Add(Event.Id, FStoryPlayEventResult());
			Result.EventId = Event.Id;
			Result.Title = Event.Title;
		}
	}

	TSet<FString> RunCompleted;
	bool bOpeningOk = OpeningError.IsEmpty();

	// E01 is played by the opening flow, not by a second StartEvent call.
	{
		FStoryPlayEventResult& Result = Results.FindOrAdd(TEXT("E01"));
		Result = OpeningRunResult;
		Result.EventId = TEXT("E01");
		if (const FDAEventDefinition* Event = EventGraph.FindEvent(TEXT("E01")))
		{
			Result.Title = Event->Title;
		}
		Result.bCompleted = IsEventCompleteRuntime(TEXT("E01"));
		if (!Result.bCompleted && !OpeningError.IsEmpty())
		{
			Result.Failure = OpeningError;
		}
		if (Result.bCompleted)
		{
			RunCompleted.Add(TEXT("E01"));
		}
	}

	// E01b is the first free-roam checkpoint; it is not one of the 35 canon ids.
	bool bE01bComplete = false;
	if (bOpeningOk)
	{
		if (IsEventCompleteRuntime(TEXT("E01b")))
		{
			bE01bComplete = true;
		}
		else if (CanStartEvent(TEXT("E01b"), Reason))
		{
			StartEvent(TEXT("E01b"));
			int32 Steps = 0;
			while (bRunning && Steps++ < 8192)
			{
				if (bWaitingForChoice)
				{
					Choose(0);
				}
				else if (bWaitingForDuel)
				{
					NotifyDuelResult(true, false);
				}
				else if (bWaitingForTimer || bWaitingForDialogue)
				{
					Advance();
				}
				else if (bPendingContinue)
				{
					bPendingContinue = false;
					PumpQueue();
				}
				else
				{
					PumpQueue();
				}
			}
			bE01bComplete = IsEventCompleteRuntime(TEXT("E01b"));
			if (!bE01bComplete)
			{
				OpeningError = TEXT("E01b did not complete");
				if (bRunning)
				{
					FinishEvent(false, false);
				}
			}
		}
		else
		{
			OpeningError = FString::Printf(TEXT("E01b cannot start: %s"), *Reason);
		}
	}
	bOpeningOk = bOpeningOk && bE01bComplete;
	AddCheck(TEXT("opening E01/E01b completed"), bOpeningOk, OpeningError);

	// ------------------------------------------------------------ simulated progress
	int32 SimulatedWins = 0;
	auto SetCounterAtLeast = [Profile, &SimulatedWins](const TCHAR* Counter, int32 Value)
	{
		if (Profile->GetCounter(Counter) < Value)
		{
			Profile->SetCounter(Counter, Value);
			++SimulatedWins;
		}
	};

	SetCounterAtLeast(TEXT("wins_total"), 220);
	SetCounterAtLeast(TEXT("duels_total"), 220);
	SetCounterAtLeast(TEXT("timed_clears"), 60);
	SetCounterAtLeast(TEXT("written_correct"), 130);
	SetCounterAtLeast(TEXT("written_total"), 200);
	SetCounterAtLeast(TEXT("wins_jaden"), 30);
	SetCounterAtLeast(TEXT("wins_syrus"), 30);
	SetCounterAtLeast(TEXT("wins_chumley"), 30);
	SetCounterAtLeast(TEXT("wins_bastion"), 30);
	SetCounterAtLeast(TEXT("wins_zane"), 30);
	SetCounterAtLeast(TEXT("wins_chazz"), 30);
	SetCounterAtLeast(TEXT("wins_alexis"), 30);
	SetCounterAtLeast(TEXT("wins_jasmine"), 30);
	SetCounterAtLeast(TEXT("wins_mindy"), 30);
	SetCounterAtLeast(TEXT("wins_crowler"), 30);
	SetCounterAtLeast(TEXT("wins_banner"), 30);
	SetCounterAtLeast(TEXT("wins_blair"), 30);
	SetCounterAtLeast(TEXT("wins_brier"), 30);
	SetCounterAtLeast(TEXT("wins_beauregard"), 30);
	SetCounterAtLeast(TEXT("wins_topher"), 30);
	SetCounterAtLeast(TEXT("wins_conklin"), 30);
	SetCounterAtLeast(TEXT("wins_damon"), 30);
	SetCounterAtLeast(TEXT("wins_dimitri"), 30);
	SetCounterAtLeast(TEXT("wins_gerard"), 30);
	SetCounterAtLeast(TEXT("wins_fontaine"), 30);
	AddInfo(FString::Printf(TEXT("simulated external progress: 220 wins, 60 timed clears, 130 written answers (%d counters set)"),
		SimulatedWins));

	// ------------------------------------------------------------ helpers
	auto ResetStats = [this]()
	{
		PlaythroughMissingDialogue = 0;
		PlaythroughMissingScene = 0;
		PlaythroughUnknownCommand = 0;
		PlaythroughUnknownOutcome = 0;
		PlaythroughDialogueCommands = 0;
		PlaythroughChoiceCommands = 0;
		PlaythroughDuelCommands = 0;
		PlaythroughDuelResolved = 0;
		PlaythroughRewardCommands = 0;
		PlaythroughFlagCommands = 0;
		PlaythroughOutcomesApplied = 0;
	};

	auto CaptureStats = [this](FStoryPlayEventResult& Result)
	{
		Result.DialogueCommands = PlaythroughDialogueCommands;
		Result.ChoiceCommands = PlaythroughChoiceCommands;
		Result.DuelCommands = PlaythroughDuelCommands;
		Result.DuelResolved = PlaythroughDuelResolved;
		Result.Rewards = PlaythroughRewardCommands;
		Result.Flags = PlaythroughFlagCommands;
		Result.Outcomes = PlaythroughOutcomesApplied;
		Result.MissingDialogue = PlaythroughMissingDialogue;
		Result.MissingScene = PlaythroughMissingScene;
		Result.UnknownCommand = PlaythroughUnknownCommand;
		Result.UnknownOutcome = PlaythroughUnknownOutcome;
	};

	TFunction<bool(const FString&, FString&)> FindAndSetDateForEvent;
	FindAndSetDateForEvent = [this, Calendar](const FString& EventId, FString& OutError) -> bool
	{
		FString StartReason;
		if (CanStartEvent(EventId, StartReason))
		{
			return true;
		}

		// The forced pass may need A02's Year 2 for canon events such as E11
		// (Jan 1), E28 (Feb 14) and E28b (Mar 14). The natural 365-day pass
		// reports those as beyond-window before we get here.
		const EDADayPeriod Periods[] = { EDADayPeriod::AM, EDADayPeriod::PM, EDADayPeriod::Night };
		for (int32 Offset = 0; Offset < 731; ++Offset)
		{
			int32 Year = 1;
			int32 Month = 0;
			int32 Day = 1 + Offset;
			while (Day > Calendar->GetDaysInMonth(Year, Month))
			{
				Day -= Calendar->GetDaysInMonth(Year, Month);
				++Month;
				if (Month > 11)
				{
					Month = 0;
					++Year;
				}
			}
			for (EDADayPeriod Period : Periods)
			{
				Calendar->SetDate(Year, Month, Day, Period);
				if (CanStartEvent(EventId, StartReason))
				{
					return true;
				}
			}
		}

		OutError = FString::Printf(TEXT("no valid calendar date in the two-year scan: %s"),
			StartReason.IsEmpty() ? TEXT("requirements not met") : *StartReason);
		return false;
	};

	TFunction<bool(FString&)> DriveCurrentEvent;
	DriveCurrentEvent = [this](FString& OutError) -> bool
	{
		int32 Steps = 0;
		while (bRunning)
		{
			if (++Steps > 16384)
			{
				OutError = FString::Printf(TEXT("command guard exceeded in %s"), *CurrentSceneId);
				return false;
			}

			if (bWaitingForChoice)
			{
				if (!ActiveChoices.IsValidIndex(0))
				{
					OutError = FString::Printf(TEXT("choice %s has no valid options"), *ActiveChoiceLineKey);
					return false;
				}
				Choose(0);
				if (bWaitingForChoice)
				{
					OutError = FString::Printf(TEXT("choice %s did not resolve"), *ActiveChoiceLineKey);
					return false;
				}
			}
			else if (bWaitingForDuel)
			{
				if (PendingDuel.OpponentId.IsEmpty())
				{
					OutError = TEXT("duel command had no opponent");
					return false;
				}
				NotifyDuelResult(true, false);
				if (bWaitingForDuel)
				{
					OutError = FString::Printf(TEXT("duel vs %s did not resolve"), *PendingDuel.OpponentId);
					return false;
				}
			}
			else if (bWaitingForTimer || bWaitingForDialogue)
			{
				Advance();
				if (bWaitingForDialogue && bPendingTextInput)
				{
					OutError = TEXT("text input did not resolve");
					return false;
				}
			}
			else if (bPendingContinue)
			{
				bPendingContinue = false;
				PumpQueue();
			}
			else
			{
				PumpQueue();
				if (!bRunning)
				{
					break;
				}
				if (!bWaitingForDialogue && !bWaitingForChoice && !bWaitingForDuel
					&& !bWaitingForTimer && !bPendingContinue)
				{
					OutError = FString::Printf(TEXT("soft lock: running in %s with no queue progress"), *CurrentSceneId);
					return false;
				}
			}
		}
		return true;
	};

	TFunction<void(const FString&, FStoryPlayEventResult&)> VerifyEventEffects;
	VerifyEventEffects = [this, Profile, Calendar, Inventory](const FString& EventId, FStoryPlayEventResult& Result)
	{
		const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
		if (!Event)
		{
			Result.EffectFailures.Add(TEXT("event definition is missing"));
			return;
		}

		int32 ExpectedDP = Result.DPBefore;
		for (const TSharedPtr<FJsonObject>& Outcome : Event->Outcomes)
		{
			if (!Outcome.IsValid())
			{
				continue;
			}
			const TArray<TSharedPtr<FJsonObject>> Conditions = PlayReadObjectArray(Outcome, TEXT("conditions"));
			if (Conditions.Num() > 0 && !EvaluateConditions(Conditions))
			{
				continue;
			}

			const FString Type = PlayReadString(Outcome, TEXT("type"));
			if (Type == TEXT("grant_dp"))
			{
				ExpectedDP += PlayReadInt(Outcome, TEXT("amount"), 0);
			}
			else if (Type == TEXT("grant_dp_from_last_lp") || Type == TEXT("dp_equal_remaining_lp"))
			{
				ExpectedDP += FMath::Max(0, Profile->GetCounter(TEXT("last_duel_player_lp")));
			}
			else if (Type == TEXT("double_dp") || Type == TEXT("dp_multiplier"))
			{
				const int32 Multiplier = FMath::Max(1, PlayReadInt(Outcome, TEXT("multiplier"), 2));
				ExpectedDP += ExpectedDP * (Multiplier - 1);
			}
			else if (Type == TEXT("reward") || Type == TEXT("grant_reward"))
			{
				const FString RewardId = PlayReadString(Outcome, TEXT("reward_id"),
					PlayReadString(Outcome, TEXT("id")));
				if (const TSharedPtr<FJsonObject>* RewardPtr = Rewards.Find(RewardId))
				{
					const TSharedPtr<FJsonObject>& Reward = *RewardPtr;
					if (PlayReadString(Reward, TEXT("type")) == TEXT("dp"))
					{
						const int32 Amount = PlayReadInt(Reward, TEXT("amount"),
							PlayReadInt(Reward, TEXT("dp"), 0));
						if (RewardId == TEXT("opening_starting_dp"))
						{
							ExpectedDP = FMath::Max(ExpectedDP, Amount);
						}
						else
						{
							ExpectedDP += Amount;
						}
					}
				}
			}
		}

		if (Result.DPAfter != ExpectedDP)
		{
			Result.EffectFailures.Add(FString::Printf(TEXT("DP expected %d, got %d"), ExpectedDP, Result.DPAfter));
		}

		for (const TSharedPtr<FJsonObject>& Outcome : Event->Outcomes)
		{
			if (!Outcome.IsValid())
			{
				continue;
			}
			const TArray<TSharedPtr<FJsonObject>> Conditions = PlayReadObjectArray(Outcome, TEXT("conditions"));
			if (Conditions.Num() > 0 && !EvaluateConditions(Conditions))
			{
				continue;
			}

			const FString Type = PlayReadString(Outcome, TEXT("type"));
			if (Type == TEXT("set_flag") || Type == TEXT("flag"))
			{
				const FString Flag = PlayReadString(Outcome, TEXT("flag"), PlayReadString(Outcome, TEXT("id")));
				const bool bExpected = PlayReadBool(Outcome, TEXT("value"), true);
				if (Profile->GetFlag(Flag) != bExpected)
				{
					Result.EffectFailures.Add(FString::Printf(TEXT("flag %s expected %s"), *Flag,
						bExpected ? TEXT("true") : TEXT("false")));
				}
			}
			else if (Type == TEXT("grant_card"))
			{
				const int32 CardId = PlayReadInt(Outcome, TEXT("card_id"), PlayReadInt(Outcome, TEXT("card"), 0));
				const int32 Count = FMath::Max(1, PlayReadInt(Outcome, TEXT("count"), 1));
				const int32 Owned = Inventory ? Inventory->GetCount(CardId) : Profile->GetCounter(FString::Printf(TEXT("card_%d"), CardId));
				if (Owned < Count)
				{
					Result.EffectFailures.Add(FString::Printf(TEXT("card %d count %d < %d"), CardId, Owned, Count));
				}
			}
			else if (Type == TEXT("grant_pack"))
			{
				const FString PackId = PlayReadString(Outcome, TEXT("pack_id"), PlayReadString(Outcome, TEXT("pack")));
				if (!PackId.IsEmpty() && !PendingPackGrants.Contains(PackId))
				{
					Result.EffectFailures.Add(FString::Printf(TEXT("pack %s was not recorded"), *PackId));
				}
			}
			else if (Type == TEXT("unlock_email"))
			{
				TArray<FString> Contacts = PlayReadStringArray(Outcome, TEXT("contacts"));
				const FString Single = PlayReadString(Outcome, TEXT("contact"));
				if (!Single.IsEmpty())
				{
					Contacts.AddUnique(Single);
				}
				for (const FString& Contact : Contacts)
				{
					if (!Profile->IsEmailUnlocked(Contact))
					{
						Result.EffectFailures.Add(FString::Printf(TEXT("email %s is not unlocked"), *Contact));
					}
				}
			}
			else if (Type == TEXT("grant_dp") || Type == TEXT("double_dp") || Type == TEXT("dp_multiplier")
				|| Type == TEXT("grant_dp_from_last_lp") || Type == TEXT("dp_equal_remaining_lp"))
			{
				// Covered by the DP expectation above.
			}
			else if (Type == TEXT("set_title"))
			{
				const FString Title = PlayReadString(Outcome, TEXT("title"));
				if (!Profile->GetTitle().Equals(Title, ESearchCase::IgnoreCase))
				{
					Result.EffectFailures.Add(FString::Printf(TEXT("title expected %s, got %s"), *Title, *Profile->GetTitle()));
				}
			}
			else if (Type == TEXT("set_dorm") || Type == TEXT("dorm_unlock"))
			{
				const FString Dorm = PlayReadString(Outcome, TEXT("dorm"), PlayReadString(Outcome, TEXT("value")));
				if (Profile->GetDorm() != DuelAcademyProfile::ParseDorm(Dorm))
				{
					Result.EffectFailures.Add(FString::Printf(TEXT("dorm expected %s"), *Dorm));
				}
			}
			else if (Type == TEXT("set_calendar"))
			{
				const int32 Year = PlayReadInt(Outcome, TEXT("year"), Calendar->GetYear());
				int32 MonthIndex = PlayReadInt(Outcome, TEXT("month_index"), INDEX_NONE);
				if (MonthIndex == INDEX_NONE)
				{
					MonthIndex = PlayMonthNumberToIndex(PlayReadInt(Outcome, TEXT("month"), Calendar->GetMonthNumber()));
				}
				const int32 Day = PlayReadInt(Outcome, TEXT("day"), 1);
				if (Calendar->GetYear() != Year || Calendar->GetMonthIndex() != MonthIndex || Calendar->GetDay() != Day)
				{
					Result.EffectFailures.Add(FString::Printf(TEXT("calendar expected %d-%d-%d, got %s"),
						Year, MonthIndex, Day, *Calendar->GetFullDateText()));
				}
			}
			else if (Type == TEXT("add_counter") || Type == TEXT("counter"))
			{
				const FString Counter = PlayReadString(Outcome, TEXT("counter"), PlayReadString(Outcome, TEXT("id")));
				const int32 Amount = PlayReadInt(Outcome, TEXT("amount"), 1);
				if (!StoryTestIsA02OwnedCounter(Counter) && Profile->GetCounter(Counter) < Amount)
				{
					Result.EffectFailures.Add(FString::Printf(TEXT("counter %s is %d < %d"),
						*Counter, Profile->GetCounter(Counter), Amount));
				}
			}
			else if (Type == TEXT("complete_event"))
			{
				const FString CompletedId = PlayReadString(Outcome, TEXT("event"), PlayReadString(Outcome, TEXT("id")));
				if (!IsEventCompleteRuntime(CompletedId))
				{
					Result.EffectFailures.Add(FString::Printf(TEXT("event %s was not completed"), *CompletedId));
				}
			}
			else if (Type == TEXT("unlock_duel"))
			{
				TArray<FString> Duels = PlayReadStringArray(Outcome, TEXT("opponents"));
				if (Duels.Num() == 0)
				{
					Duels = PlayReadStringArray(Outcome, TEXT("duels"));
				}
				if (Duels.Num() == 0)
				{
					Duels.Add(PlayReadString(Outcome, TEXT("id"), PlayReadString(Outcome, TEXT("opponent"))));
				}
				for (const FString& DuelId : Duels)
				{
					if (!DuelId.IsEmpty() && !IsDuelUnlocked(DuelId))
					{
						Result.EffectFailures.Add(FString::Printf(TEXT("duel %s is not unlocked"), *DuelId));
					}
				}
			}
			else if (Type == TEXT("item"))
			{
				const FString ItemName = PlayReadString(Outcome, TEXT("name"), PlayReadString(Outcome, TEXT("id")));
				const FString Flag = FString::Printf(TEXT("item_%s"), *DuelAcademyProfile::NormalizeId(ItemName));
				if (!Profile->GetFlag(Flag))
				{
					Result.EffectFailures.Add(FString::Printf(TEXT("item flag %s is not set"), *Flag));
				}
			}
			else if (Type == TEXT("name_change"))
			{
				if (!Profile->GetFlag(TEXT("name_change_unlocked")))
				{
					Result.EffectFailures.Add(TEXT("name_change_unlocked is not set"));
				}
			}
			else if (Type == TEXT("exam_exemption"))
			{
				if (!Profile->GetFlag(TEXT("exam_exempt_next")))
				{
					Result.EffectFailures.Add(TEXT("exam_exempt_next is not set"));
				}
			}
			else if (Type == TEXT("grant_deck"))
			{
				const FString DeckId = PlayReadString(Outcome, TEXT("deck_id"), PlayReadString(Outcome, TEXT("deck")));
				if (!DeckId.IsEmpty() && !SelectedStarterDeck.Equals(DeckId, ESearchCase::IgnoreCase))
				{
					Result.EffectFailures.Add(FString::Printf(TEXT("deck %s was not selected"), *DeckId));
				}
			}
			else if (Type == TEXT("reward") || Type == TEXT("grant_reward"))
			{
				const FString RewardId = PlayReadString(Outcome, TEXT("reward_id"),
					PlayReadString(Outcome, TEXT("id")));
				if (const TSharedPtr<FJsonObject>* RewardPtr = Rewards.Find(RewardId))
				{
					const TSharedPtr<FJsonObject>& Reward = *RewardPtr;
					const FString RewardType = PlayReadString(Reward, TEXT("type"));
					if (RewardType == TEXT("email_unlock"))
					{
						TArray<FString> Contacts = PlayReadStringArray(Reward, TEXT("contacts"));
						const FString Single = PlayReadString(Reward, TEXT("contact"));
						if (!Single.IsEmpty())
						{
							Contacts.AddUnique(Single);
						}
						for (const FString& Contact : Contacts)
						{
							if (!Profile->IsEmailUnlocked(Contact))
							{
								Result.EffectFailures.Add(FString::Printf(TEXT("reward email %s is not unlocked"), *Contact));
							}
						}
					}
					else if (RewardType == TEXT("deck_grant"))
					{
						const FString DeckId = PlayReadString(Reward, TEXT("deck_id"));
						if (!DeckId.IsEmpty() && !SelectedStarterDeck.Equals(DeckId, ESearchCase::IgnoreCase))
						{
							Result.EffectFailures.Add(FString::Printf(TEXT("reward deck %s was not selected"), *DeckId));
						}
					}
				}
			}
			else if (Type == TEXT("set_objective") || Type == TEXT("temporary_title")
				|| Type == TEXT("restore_title") || Type == TEXT("next_event"))
			{
				// Presentation/flow outcomes; the story log records them.
			}
			else if (!Type.IsEmpty())
			{
				Result.EffectFailures.Add(FString::Printf(TEXT("unhandled outcome type %s"), *Type));
			}
		}
	};

	TFunction<bool(const TSharedPtr<FJsonObject>&, TArray<FString>&, int32, FString&)> ForceCondition;
	TFunction<bool(const FString&, TArray<FString>&, int32, FString&)> ForceEventState;
	TFunction<bool(const FString&, int32)> RunEventForced;

	ForceCondition = [this, Profile, Calendar, Inventory, TitleSystem, &RunEventForced, &ForceCondition](
		const TSharedPtr<FJsonObject>& Condition, TArray<FString>& Gates, int32 Depth, FString& OutError) -> bool
	{
		if (!Condition.IsValid())
		{
			return true;
		}

		const FString Kind = PlayReadString(Condition, TEXT("type"));
		if (Kind.IsEmpty() || Kind == TEXT("all") || Kind == TEXT("any"))
		{
			TArray<TSharedPtr<FJsonObject>> Children = PlayReadObjectArray(Condition, TEXT("conditions"));
			if (Children.Num() == 0)
			{
				Children = PlayReadObjectArray(Condition, TEXT("all"));
			}
			if (Children.Num() == 0)
			{
				Children = PlayReadObjectArray(Condition, TEXT("any"));
			}
			if (Children.Num() == 0)
			{
				return true;
			}
			if (Kind == TEXT("any") || (Kind.IsEmpty() && PlayReadObjectArray(Condition, TEXT("any")).Num() > 0))
			{
				FString Reason;
				if (FDAEventGraph::EvaluateCondition(Condition, Profile, Calendar, Reason))
				{
					return true;
				}
				for (const TSharedPtr<FJsonObject>& Child : Children)
				{
					if (!ForceCondition(Child, Gates, Depth, OutError))
					{
						continue;
					}
					if (FDAEventGraph::EvaluateCondition(Condition, Profile, Calendar, Reason))
					{
						return true;
					}
				}
				OutError = TEXT("no branch of an any-condition could be satisfied");
				return false;
			}

			for (const TSharedPtr<FJsonObject>& Child : Children)
			{
				if (!ForceCondition(Child, Gates, Depth, OutError))
				{
					return false;
				}
			}
			return true;
		}

		if (Kind == TEXT("new_game"))
		{
			if (!Profile->GetFlag(TEXT("new_game_started")))
			{
				Profile->SetFlag(TEXT("new_game_started"), true);
				Gates.Add(TEXT("new_game_started"));
			}
			return true;
		}

		if (Kind == TEXT("flag"))
		{
			const FString Flag = PlayReadString(Condition, TEXT("flag"), PlayReadString(Condition, TEXT("id")));
			const bool bExpected = PlayReadBool(Condition, TEXT("value"), true);
			if (Flag.IsEmpty())
			{
				return true;
			}
			if (Profile->GetFlag(Flag) != bExpected)
			{
				Profile->SetFlag(Flag, bExpected);
				Gates.Add(FString::Printf(TEXT("flag %s=%s"), *Flag, bExpected ? TEXT("true") : TEXT("false")));
			}
			return true;
		}

		if (Kind == TEXT("counter"))
		{
			const FString Counter = PlayReadString(Condition, TEXT("counter"), PlayReadString(Condition, TEXT("id")));
			const int32 Expected = PlayReadInt(Condition, TEXT("value"), 0);
			const FString Op = PlayReadString(Condition, TEXT("op"), TEXT(">="));
			const int32 Current = Profile->GetCounter(Counter);
			int32 Target = Current;
			if (Op == TEXT(">=")) Target = FMath::Max(Current, Expected);
			else if (Op == TEXT(">")) Target = FMath::Max(Current, Expected + 1);
			else if (Op == TEXT("==")) Target = Expected;
			else if (Op == TEXT("<=")) Target = FMath::Min(Current, Expected);
			else if (Op == TEXT("<")) Target = FMath::Min(Current, FMath::Max(0, Expected - 1));
			else if (Op == TEXT("!=")) Target = Current == Expected ? Expected + 1 : Current;
			if (Target != Current)
			{
				Profile->SetCounter(Counter, Target);
				Gates.Add(FString::Printf(TEXT("counter %s=%d"), *Counter, Target));
			}
			return true;
		}

		if (Kind == TEXT("wins_against_each"))
		{
			const int32 Wins = PlayReadInt(Condition, TEXT("count"), 10);
			static const TCHAR* const Duelists[] = {
				TEXT("jaden"), TEXT("syrus"), TEXT("chumley"), TEXT("bastion"), TEXT("chazz"),
				TEXT("zane"), TEXT("alexis"), TEXT("jasmine"), TEXT("mindy"), TEXT("crowler"),
				TEXT("banner"), TEXT("blair"), TEXT("brier"), TEXT("beauregard"), TEXT("topher"),
				TEXT("conklin"), TEXT("damon"), TEXT("dimitri"), TEXT("gerard"), TEXT("fontaine")
			};
			for (const TCHAR* Duelist : Duelists)
			{
				const FString Key = FString::Printf(TEXT("wins_%s"), Duelist);
				if (Profile->GetCounter(Key) < Wins)
				{
					Profile->SetCounter(Key, Wins);
					Gates.Add(FString::Printf(TEXT("counter %s=%d"), *Key, Wins));
				}
			}
			return true;
		}

		if (Kind == TEXT("written_correct_percent"))
		{
			const int32 Percent = FMath::Clamp(PlayReadInt(Condition, TEXT("percent"), 60), 0, 100);
			int32 Total = Profile->GetCounter(TEXT("written_total"));
			if (Total <= 0)
			{
				Total = 200;
				Profile->SetCounter(TEXT("written_total"), Total);
			}
			const int32 Needed = FMath::DivideAndRoundUp(Percent * Total, 100);
			if (Profile->GetCounter(TEXT("written_correct")) < Needed)
			{
				Profile->SetCounter(TEXT("written_correct"), Needed);
				Gates.Add(FString::Printf(TEXT("written_correct=%d/%d"), Needed, Total));
			}
			return true;
		}

		if (Kind == TEXT("after_ending"))
		{
			if (!Profile->GetFlag(TEXT("post_game")))
			{
				Profile->SetFlag(TEXT("post_game"), true);
				Gates.Add(TEXT("post_game"));
			}
			return true;
		}

		if (Kind == TEXT("event") || Kind == TEXT("event_complete"))
		{
			const FString EventId = PlayReadString(Condition, TEXT("event"), PlayReadString(Condition, TEXT("id")));
			if (EventId.IsEmpty() || IsEventCompleteRuntime(EventId))
			{
				return true;
			}
			if (!RunEventForced(EventId, Depth + 1))
			{
				OutError = FString::Printf(TEXT("prerequisite event %s could not be completed"), *EventId);
				return false;
			}
			Gates.Add(FString::Printf(TEXT("event %s completed"), *EventId));
			return true;
		}

		if (Kind == TEXT("card"))
		{
			const int32 CardId = PlayReadInt(Condition, TEXT("id"), PlayReadInt(Condition, TEXT("card_id"), 0));
			const int32 MinCount = FMath::Max(1, PlayReadInt(Condition, TEXT("min_count"), 1));
			const int32 Owned = Inventory ? Inventory->GetCount(CardId) : Profile->GetCounter(FString::Printf(TEXT("card_%d"), CardId));
			if (Owned < MinCount)
			{
				if (Inventory)
				{
					Inventory->AddCard(CardId, MinCount - Owned);
				}
				else
				{
					Profile->SetCounter(FString::Printf(TEXT("card_%d"), CardId), MinCount);
				}
				Gates.Add(FString::Printf(TEXT("card %d x%d"), CardId, MinCount));
			}
			return true;
		}

		if (Kind == TEXT("title"))
		{
			const FString Title = PlayReadString(Condition, TEXT("value"));
			FString Reason;
			if (FDAEventGraph::EvaluateCondition(Condition, Profile, Calendar, Reason))
			{
				return true;
			}
			if (Title.Equals(TEXT("Dropout Boy"), ESearchCase::IgnoreCase) && TitleSystem)
			{
				TitleSystem->ApplyExamOutcome(Profile, 0, 300, true);
			}
			else if (TitleSystem)
			{
				TitleSystem->ForceTitle(Profile, Title, true);
			}
			else
			{
				Profile->SetTitle(Title);
			}
			Gates.Add(FString::Printf(TEXT("title %s"), *Title));
			return true;
		}

		if (Kind == TEXT("dorm"))
		{
			const FString Dorm = PlayReadString(Condition, TEXT("value"));
			const EDADorm Target = DuelAcademyProfile::ParseDorm(Dorm);
			if (Profile->GetDorm() != Target)
			{
				Profile->SetDorm(Target);
				Gates.Add(FString::Printf(TEXT("dorm %s"), *Dorm));
			}
			return true;
		}

		// Calendar conditions are satisfied by FindAndSetDateForEvent.
		if (Kind == TEXT("date") || Kind == TEXT("date_at_least") || Kind == TEXT("weekday")
			|| Kind == TEXT("period") || Kind == TEXT("exam_day"))
		{
			return true;
		}

		// Caller-driven/unsupported conditions pass in the event graph too.
		return true;
	};

	ForceEventState = [this, Profile, Calendar, &ForceCondition](
		const FString& EventId, TArray<FString>& Gates, int32 Depth, FString& OutError) -> bool
	{
		const FDAEventDefinition* Event = EventGraph.FindEvent(EventId);
		if (!Event)
		{
			OutError = FString::Printf(TEXT("unknown event %s"), *EventId);
			return false;
		}

		for (int32 PassIndex = 0; PassIndex < 5; ++PassIndex)
		{
			bool bAllSatisfied = true;
			for (const TSharedPtr<FJsonObject>& Requirement : Event->Requirements)
			{
				if (!ForceCondition(Requirement, Gates, Depth, OutError))
				{
					bAllSatisfied = false;
				}
			}
			if (Event->Trigger.IsValid())
			{
				const FString TriggerType = PlayReadString(Event->Trigger, TEXT("type"));
				if (TriggerType == TEXT("flag") || TriggerType == TEXT("event")
					|| TriggerType == TEXT("event_complete"))
				{
					if (!ForceCondition(Event->Trigger, Gates, Depth, OutError))
					{
						bAllSatisfied = false;
					}
				}
			}
			if (bAllSatisfied)
			{
				return true;
			}
		}

		OutError = OutError.IsEmpty() ? TEXT("requirements could not be satisfied") : OutError;
		return false;
	};

	RunEventForced = [this, Profile, Calendar, &Results, &RunCompleted,
		&ForceEventState, &FindAndSetDateForEvent, &DriveCurrentEvent, &VerifyEventEffects,
		&ResetStats, &CaptureStats](const FString& EventId, int32 Depth) -> bool
	{
		if (RunCompleted.Contains(EventId))
		{
			return true;
		}
		if (Depth > 8)
		{
			return false;
		}

		FStoryPlayEventResult& Result = Results.FindOrAdd(EventId);
		Result.EventId = EventId;
		Result.Failure.Reset();
		Result.EffectFailures.Reset();
		if (const FDAEventDefinition* Event = EventGraph.FindEvent(EventId))
		{
			Result.Title = Event->Title;
		}

		TArray<FString> Gates;
		FString Error;
		if (!ForceEventState(EventId, Gates, Depth, Error))
		{
			Result.Failure = Error;
			return false;
		}
		if (!FindAndSetDateForEvent(EventId, Error))
		{
			Result.Failure = Error;
			return false;
		}
		if (Calendar->GetAbsoluteDay() > Calendar->GetAbsoluteDayFor(1, 9, 30))
		{
			Gates.AddUnique(TEXT("calendar beyond 365 days (Year 2)"));
		}

		ResetStats();
		Result.DPBefore = Profile->GetDP();
		StartEvent(EventId);
		if (!bRunning || !GetCurrentEventId().Equals(EventId))
		{
			Result.Failure = FString::Printf(TEXT("StartEvent(%s) was rejected"), *EventId);
			CaptureStats(Result);
			return false;
		}

		Result.bStarted = true;
		Result.bForced = true;
		for (const FString& Gate : Gates)
		{
			Result.ForcedGates.AddUnique(Gate);
		}

		if (!DriveCurrentEvent(Error))
		{
			Result.Failure = Error;
			if (bRunning)
			{
				FinishEvent(false, false);
			}
			return false;
		}
		Result.DPAfter = Profile->GetDP();
		CaptureStats(Result);
		Result.bCompleted = IsEventCompleteRuntime(EventId);
		if (!Result.bCompleted)
		{
			Result.Failure = TEXT("event did not set its completion flag");
			return false;
		}

		RunCompleted.Add(EventId);
		VerifyEventEffects(EventId, Result);
		return true;
	};

	if (FStoryPlayEventResult* E01Result = Results.Find(TEXT("E01")))
	{
		if (E01Result->bCompleted)
		{
			VerifyEventEffects(TEXT("E01"), *E01Result);
		}
	}

	// ------------------------------------------------------------ natural year
	const int32 StartAbsoluteDay = Calendar->GetAbsoluteDay();
	TSet<int32> MonthsSeen;
	bool bSawStayFlag = false;
	bool bSawWalkFlag = false;
	bool bSawPostGame = false;

	auto ApplyWorldProgress = [&](int32 DayOffset)
	{
		if (DayOffset >= 42 && !bSawStayFlag)
		{
			Profile->SetFlag(TEXT("stayed_in_room_three_weekends"), true);
			bSawStayFlag = true;
			AddInfo(FString::Printf(TEXT("simulated world flag stayed_in_room_three_weekends @ %s"),
				*Calendar->GetFullDateText()));
		}
		if (DayOffset >= 84 && !bSawWalkFlag)
		{
			Profile->SetFlag(TEXT("walk_home_partner_3"), true);
			bSawWalkFlag = true;
			AddInfo(FString::Printf(TEXT("simulated world flag walk_home_partner_3 @ %s"),
				*Calendar->GetFullDateText()));
		}
		if (DayOffset >= 300 && !bSawPostGame && RunCompleted.Num() >= 34)
		{
			// The ending flow should only open E33 once the other 34 canonical
			// events (including E29-E32) are done, so the final title is stable.
			Profile->SetFlag(TEXT("post_game"), true);
			bSawPostGame = true;
			AddInfo(FString::Printf(TEXT("simulated world flag post_game @ %s"),
				*Calendar->GetFullDateText()));
		}
	};

	int32 NaturalCompleted = 0;
	for (int32 DayOffset = 0; DayOffset < 365; ++DayOffset)
	{
		if (DayOffset > 0)
		{
			Calendar->AdvanceDay();
		}
		ApplyWorldProgress(DayOffset);

		for (int32 PeriodIndex = 0; PeriodIndex < 3; ++PeriodIndex)
		{
			if (PeriodIndex > 0)
			{
				Calendar->AdvancePeriod();
			}
			MonthsSeen.Add(Calendar->GetMonthIndex());

			for (const FString& EventId : OrderedIds)
			{
				if (RunCompleted.Contains(EventId))
				{
					continue;
				}

				FStoryPlayEventResult& Result = Results.FindOrAdd(EventId);
				FString StartReason;
				if (Result.StartAttempts >= 3)
				{
					continue;
				}

				if (!CanStartEvent(EventId, StartReason))
				{
					if (const FDAEventDefinition* Event = EventGraph.FindEvent(EventId))
					{
						FString TriggerReason;
						const bool bTriggerOk = EventGraph.EvaluateTrigger(*Event, Profile, Calendar, TriggerReason);
						TArray<FString> RequirementReasons;
						for (const TSharedPtr<FJsonObject>& Requirement : Event->Requirements)
						{
							DescribeCondition(Requirement, Profile, Calendar, RequirementReasons);
						}

						// Prefer a real requirement blocker over the date window:
						// once the trigger is valid, the remaining reason is what
						// actually stops the event during its playable window.
						if (bTriggerOk && RequirementReasons.Num() > 0)
						{
							Result.NaturalBlockers = JoinReasons(RequirementReasons);
							Result.NaturalBlockerDate = Calendar->GetFullDateText();
						}
						else if (bTriggerOk)
						{
							Result.NaturalBlockers = StartReason;
							Result.NaturalBlockerDate = Calendar->GetFullDateText();
						}
						else if (Result.NaturalBlockers.IsEmpty())
						{
							TArray<FString> Blockers;
							if (!TriggerReason.IsEmpty())
							{
								Blockers.Add(FString::Printf(TEXT("trigger: %s"), *TriggerReason));
							}
							Blockers.Append(RequirementReasons);
							Result.NaturalBlockers = JoinReasons(Blockers);
							Result.NaturalBlockerDate = Calendar->GetFullDateText();
						}
					}
					else
					{
						Result.NaturalBlockers = StartReason;
						Result.NaturalBlockerDate = Calendar->GetFullDateText();
					}
					continue;
				}

				++Result.StartAttempts;
				ResetStats();
				Result.Failure.Reset();
				Result.EffectFailures.Reset();
				Result.DPBefore = Profile->GetDP();
				StartEvent(EventId);
				if (!bRunning)
				{
					Result.Failure = FString::Printf(TEXT("StartEvent(%s) started no scene"), *EventId);
					CaptureStats(Result);
					continue;
				}
				Result.bStarted = true;

				FString DriveError;
				if (!DriveCurrentEvent(DriveError))
				{
					Result.Failure = DriveError;
					if (bRunning)
					{
						FinishEvent(false, false);
					}
					continue;
				}
				Result.DPAfter = Profile->GetDP();
				CaptureStats(Result);
				if (IsEventCompleteRuntime(EventId))
				{
					Result.bCompleted = true;
					RunCompleted.Add(EventId);
					VerifyEventEffects(EventId, Result);
				}
				else if (Result.Failure.IsEmpty())
				{
					Result.Failure = TEXT("event reached the queue end without completing");
				}
			}
		}
	}

	NaturalCompleted = RunCompleted.Num();
	AddInfo(FString::Printf(TEXT("natural 365-day timeline: %d/35 events completed"), NaturalCompleted));

	for (const FString& EventId : OrderedIds)
	{
		if (RunCompleted.Contains(EventId))
		{
			continue;
		}
		const FStoryPlayEventResult& Result = Results.FindRef(EventId);
		AddInfo(FString::Printf(TEXT("natural blocker %s @ %s: %s"), *EventId,
			Result.NaturalBlockerDate.IsEmpty() ? TEXT("<never>") : *Result.NaturalBlockerDate,
			Result.NaturalBlockers.IsEmpty() ? TEXT("<none recorded>") : *Result.NaturalBlockers));
	}

	const int32 EndAbsoluteDay = Calendar->GetAbsoluteDay();
	AddCheck(TEXT("calendar advanced a full school year"), EndAbsoluteDay - StartAbsoluteDay >= 364,
		FString::Printf(TEXT("%d days"), EndAbsoluteDay - StartAbsoluteDay));
	AddCheck(TEXT("calendar visited all 12 months"), MonthsSeen.Num() == 12,
		FString::FromInt(MonthsSeen.Num()));

	// ------------------------------------------------------------ forced runtime pass
	// Pass A is intentionally allowed to fail on exclusive dorm/title gates. Pass B
	// satisfies exactly the data-declared gates through A02 APIs, then replays the
	// event through the real scene queue so runtime coverage is still 35/35.
	Calendar->SetDate(1, 0, 1, EDADayPeriod::AM);
	for (int32 ForcedPass = 0; ForcedPass < 2; ++ForcedPass)
	{
		for (const FString& EventId : OrderedIds)
		{
			if (RunCompleted.Contains(EventId))
			{
				continue;
			}
			RunEventForced(EventId, 0);
		}
	}

	for (const FString& EventId : OrderedIds)
	{
		FStoryPlayEventResult& Result = Results.FindOrAdd(EventId);
		if (Result.ForcedGates.Num() > 0)
		{
			AddInfo(FString::Printf(TEXT("forced gates %s: %s"), *EventId,
				*FString::Join(Result.ForcedGates, TEXT(", "))));
		}
	}

	// ------------------------------------------------------------ email / packs
	int32 ExpectedEmails = 0;
	int32 UnlockedEmails = 0;
	int32 ReadMessages = 0;
	int32 PendingRequests = 0;
	int32 UnlockedDuelRequests = 0;
	int32 ExpectedRequests = 0;

	for (const FString& ContactId : GetEmailContactIds())
	{
		const TSharedPtr<FJsonObject>* ContactPtr = EmailContacts.Find(ContactId);
		if (!ContactPtr || !ContactPtr->IsValid())
		{
			continue;
		}
		const TArray<FString> UnlockedBy = PlayReadStringArray(*ContactPtr, TEXT("unlocked_by"));
		bool bShouldUnlock = false;
		for (const FString& EventId : UnlockedBy)
		{
			if (RunCompleted.Contains(EventId))
			{
				bShouldUnlock = true;
				break;
			}
		}
		if (!bShouldUnlock)
		{
			continue;
		}

		++ExpectedEmails;
		if (Profile->IsEmailUnlocked(ContactId))
		{
			++UnlockedEmails;
		}
		for (const FString& MessageId : GetEmailMessageIds(ContactId))
		{
			Profile->MarkEmailRead(ContactId, MessageId);
			if (Profile->IsEmailRead(ContactId, MessageId))
			{
				++ReadMessages;
			}
		}
		for (const TSharedPtr<FJsonObject>& Request : PlayReadObjectArray(*ContactPtr, TEXT("duel_requests")))
		{
			++ExpectedRequests;
			const FString RequestId = PlayReadString(Request, TEXT("id"));
			const FString OpponentId = PlayReadString(Request, TEXT("opponent"));
			const FDAEmailState State = Profile->GetEmailState(ContactId);
			if (State.PendingDuelRequests.Contains(RequestId))
			{
				++PendingRequests;
			}
			if (!OpponentId.IsEmpty() && IsDuelUnlocked(OpponentId))
			{
				++UnlockedDuelRequests;
			}
		}
	}

	AddCheck(TEXT("6 email contacts unlocked"), ExpectedEmails == 6 && UnlockedEmails == 6,
		FString::Printf(TEXT("%d/%d"), UnlockedEmails, ExpectedEmails));
	AddCheck(TEXT("email read state applied"), ReadMessages == 6,
		FString::FromInt(ReadMessages));
	AddCheck(TEXT("6 email duel requests pending"), ExpectedRequests == 6 && PendingRequests == 6,
		FString::Printf(TEXT("%d/%d"), PendingRequests, ExpectedRequests));
	AddCheck(TEXT("email duel requests unlocked for A07"), UnlockedDuelRequests == ExpectedRequests,
		FString::Printf(TEXT("%d/%d"), UnlockedDuelRequests, ExpectedRequests));

	bool bConsumedRequest = false;
	for (const FString& ContactId : GetEmailContactIds())
	{
		FString RequestId;
		if (Profile->ConsumeDuelRequest(ContactId, RequestId))
		{
			if (!RequestId.IsEmpty())
			{
				Profile->AddDuelRequest(ContactId, RequestId);
				bConsumedRequest = true;
			}
			break;
		}
	}
	AddCheck(TEXT("duel request consume/restore"), bConsumedRequest, FString());

	const bool bE10Pack = PendingPackGrants.Contains(TEXT("master_fusions"))
		|| PendingPackGrants.Contains(TEXT("special_ways"))
		|| PendingPackGrants.Contains(TEXT("basic_1a"));
	AddCheck(TEXT("E10 pack grant recorded"), bE10Pack, FString::Join(GetPendingPackGrants(), TEXT(", ")));
	AddCheck(TEXT("E32 pack grant recorded"), PendingPackGrants.Contains(TEXT("dorothys_gift")),
		FString::Join(GetPendingPackGrants(), TEXT(", ")));
	AddCheck(TEXT("pending pack consume API"), ConsumePendingPackGrant(TEXT("dorothys_gift")), FString());

	const bool bOpeningFlags = Profile->GetFlag(TEXT("first_free_roam"))
		&& Profile->GetFlag(TEXT("opening_complete"))
		&& Profile->GetFlag(TEXT("tutorial_complete"))
		&& Profile->GetFlag(TEXT("starter_deck_chosen"));
	AddCheck(TEXT("opening flags preserved"), bOpeningFlags && bE01bComplete, FString());
	AddCheck(TEXT("E33 King of Games title applied"),
		Profile->GetTitle().Equals(TEXT("King of Games"), ESearchCase::IgnoreCase), Profile->GetTitle());

	// ------------------------------------------------------------ per-event report
	int32 StartedCount = 0;
	int32 CompletedCount = 0;
	int32 TotalDuelCommands = 0;
	int32 TotalDuelResolved = 0;
	int32 FullCampaignDuelCommands = 0;
	int32 FullCampaignDuelResolved = 0;
	int32 TotalMissingDialogue = 0;
	int32 TotalMissingScene = 0;
	int32 TotalUnknownCommands = 0;
	int32 TotalUnknownOutcomes = 0;
	int32 EventFailures = 0;

	for (const FString& EventId : OrderedIds)
	{
		FStoryPlayEventResult& Result = Results.FindOrAdd(EventId);
		if (Result.bStarted)
		{
			++StartedCount;
		}
		if (Result.bCompleted)
		{
			++CompletedCount;
		}
		TotalDuelCommands += Result.DuelCommands;
		TotalDuelResolved += Result.DuelResolved;
		if (EventId != TEXT("E01"))
		{
			FullCampaignDuelCommands += Result.DuelCommands;
			FullCampaignDuelResolved += Result.DuelResolved;
		}
		TotalMissingDialogue += Result.MissingDialogue;
		TotalMissingScene += Result.MissingScene;
		TotalUnknownCommands += Result.UnknownCommand;
		TotalUnknownOutcomes += Result.UnknownOutcome;

		const bool bPassed = Result.Passed();
		const FString Detail = FString::Printf(TEXT("duels %d/%d, dialogue %d, choices %d, outcomes %d"),
			Result.DuelResolved, Result.DuelCommands, Result.DialogueCommands,
			Result.ChoiceCommands, Result.Outcomes);
		if (bPassed)
		{
			Report.Add(FString::Printf(TEXT("PASS event %s (%s): %s"), *EventId, *Result.Title, *Detail));
		}
		else
		{
			++EventFailures;
			TArray<FString> Failures;
			if (!Result.bStarted)
			{
				Failures.Add(TEXT("not started"));
			}
			if (!Result.bCompleted)
			{
				Failures.Add(TEXT("not completed"));
			}
			if (!Result.Failure.IsEmpty())
			{
				Failures.Add(Result.Failure);
			}
			Failures.Append(Result.EffectFailures);
			Report.Add(FString::Printf(TEXT("FAIL event %s (%s): %s [%s]"), *EventId, *Result.Title,
				*FString::Join(Failures, TEXT("; ")), *Detail));
		}
	}

	AddCheck(TEXT("all 35 events started"), StartedCount == 35, FString::FromInt(StartedCount));
	AddCheck(TEXT("all 35 events completed"), CompletedCount == 35, FString::FromInt(CompletedCount));
	AddCheck(TEXT("39/39 full-campaign duel commands resolved"),
		FullCampaignDuelCommands == 39 && FullCampaignDuelResolved == 39,
		FString::Printf(TEXT("%d/%d"), FullCampaignDuelResolved, FullCampaignDuelCommands));
	AddCheck(TEXT("all story duels resolved"), TotalDuelCommands == TotalDuelResolved,
		FString::Printf(TEXT("%d/%d including the E01 tutorial"), TotalDuelResolved, TotalDuelCommands));
	AddCheck(TEXT("no missing scenes"), TotalMissingScene == 0, FString::FromInt(TotalMissingScene));
	AddCheck(TEXT("no missing dialogue/choice keys"), TotalMissingDialogue == 0, FString::FromInt(TotalMissingDialogue));
	AddCheck(TEXT("no unknown command types"), TotalUnknownCommands == 0, FString::FromInt(TotalUnknownCommands));
	AddCheck(TEXT("no unknown outcome types"), TotalUnknownOutcomes == 0, FString::FromInt(TotalUnknownOutcomes));

	const bool bAllPass = Failed == 0 && EventFailures == 0 && CompletedCount == 35;
	const double Elapsed = FPlatformTime::Seconds() - StartTime;

	Report.Add(FString::Printf(
		TEXT("SUMMARY %s: %d/%d events started, %d/%d events completed, %d/%d story duels resolved (%d/%d full campaign), %d/%d email contacts, %d pending packs, %d checks passed, %d checks failed, %d event failures"),
		bAllPass ? TEXT("PASS") : TEXT("FAIL"), StartedCount, 35, CompletedCount, 35,
		TotalDuelResolved, TotalDuelCommands, FullCampaignDuelResolved, FullCampaignDuelCommands,
		UnlockedEmails, ExpectedEmails, PendingPackGrants.Num(), Passed, Failed, EventFailures));

	RestoreSnapshot();

	LastPlaythroughReport = FString::Join(Report, TEXT("\n"));
	LastPlaythroughReport += FString::Printf(TEXT("\n%s in %.3fs"),
		bAllPass ? TEXT("PASS") : TEXT("FAIL"), Elapsed);

	for (const FString& Line : Report)
	{
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s: %s"), PlaythroughPrefix, *Line);
	}
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s: %s in %.3fs"), PlaythroughPrefix,
		bAllPass ? TEXT("PASS") : TEXT("FAIL"), Elapsed);

	return bAllPass;
}

void UDAStoryPlaythroughTestSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	if (FParse::Param(FCommandLine::Get(), TEXT("DAStoryPlaythroughTest")))
	{
		TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateUObject(this, &UDAStoryPlaythroughTestSubsystem::Tick), 2.0f);
	}
}

void UDAStoryPlaythroughTestSubsystem::Deinitialize()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}
	Super::Deinitialize();
}

bool UDAStoryPlaythroughTestSubsystem::Tick(float DeltaTime)
{
	if (bFinished)
	{
		return false;
	}

	WaitSeconds += DeltaTime;
	if (WaitSeconds > 60.f)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("%s: timed out waiting for the story/world."), PlaythroughPrefix);
		bFinished = true;
		TickerHandle.Reset();
		FPlatformMisc::RequestExit(false);
		return false;
	}

	UGameInstance* GameInstance = GetGameInstance();
	UWorld* World = GameInstance ? GameInstance->GetWorld() : nullptr;
	if (!World || !World->HasBegunPlay())
	{
		return true;
	}

	UDAStorySubsystem* Story = GameInstance->GetSubsystem<UDAStorySubsystem>();
	UDAProfileSubsystem* Profile = GameInstance->GetSubsystem<UDAProfileSubsystem>();
	UDACalendarSubsystem* Calendar = GameInstance->GetSubsystem<UDACalendarSubsystem>();
	if (!Story || !Profile || !Calendar || !Story->IsFullCampaignLoaded())
	{
		return true;
	}
	if (Story->IsRunning())
	{
		return true;
	}

	const bool bPass = Story->RunStoryPlaythroughTest();
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s: %s"), PlaythroughPrefix,
		bPass ? TEXT("PASS") : TEXT("FAIL"));

	bFinished = true;
	if (TickerHandle.IsValid())
	{
		TickerHandle.Reset();
	}
	FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float)
	{
		FPlatformMisc::RequestExit(false);
		return false;
	}), 1.0f);
	return false;
}

namespace
{
	FAutoConsoleCommandWithWorldAndArgs GDAStoryPlaythroughTestCommand(
		TEXT("da.StoryPlaythroughTest"),
		TEXT("Run the headless 35-event in-engine story playthrough harness."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>&, UWorld* World)
		{
			if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(World))
			{
				const bool bPass = Story->RunStoryPlaythroughTest();
				UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s: %s"), PlaythroughPrefix,
					bPass ? TEXT("PASS") : TEXT("FAIL"));
			}
			else
			{
				UE_LOG(LogDuelAcademyIsland, Error, TEXT("%s: story subsystem not found."), PlaythroughPrefix);
			}
		}));
}
