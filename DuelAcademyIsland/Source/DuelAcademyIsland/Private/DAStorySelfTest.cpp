// Duel Academy Island - full-campaign story audit.
//
// Test-only implementation moved out of DAStorySubsystem.cpp so the runtime
// translation unit stays focused on the scene queue. Declarations remain on
// UDAStorySubsystem.

#include "DAStorySubsystem.h"

#include "DAEventGraph.h"
#include "DAProfileSubsystem.h"
#include "DACalendarSubsystem.h"
#include "DAInventorySubsystem.h"
#include "DASaveGame.h"
#include "DASettings.h"
#include "DuelAcademyIsland.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"
#include "HAL/PlatformTime.h"
#include "Templates/Function.h"

namespace
{
	FString SelfTestReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, const FString& Fallback = FString())
	{
		FString Value;
		if (Object.IsValid() && Object->TryGetStringField(Field, Value))
		{
			return Value;
		}
		return Fallback;
	}

	int32 SelfTestReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Fallback = 0)
	{
		int32 Value = Fallback;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return Value;
	}

	TArray<TSharedPtr<FJsonObject>> SelfTestReadObjectArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
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

	TArray<FString> SelfTestReadStringArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
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
}

// ---------------------------------------------------------------------------
// Full-campaign audit
// ---------------------------------------------------------------------------

void UDAStorySubsystem::CollectConditionState(const TSharedPtr<FJsonObject>& Condition,
	TSet<FString>& OutFlags, TSet<FString>& OutCounters, TSet<FString>& OutEvents) const
{
	if (!Condition.IsValid())
	{
		return;
	}

	const FString Kind = SelfTestReadString(Condition, TEXT("type"));
	if (Kind == TEXT("flag"))
	{
		const FString Flag = SelfTestReadString(Condition, TEXT("flag"), SelfTestReadString(Condition, TEXT("id")));
		if (!Flag.IsEmpty())
		{
			OutFlags.Add(Flag);
		}
	}
	else if (Kind == TEXT("counter"))
	{
		const FString Counter = SelfTestReadString(Condition, TEXT("counter"), SelfTestReadString(Condition, TEXT("id")));
		if (!Counter.IsEmpty())
		{
			OutCounters.Add(Counter);
		}
	}
	else if (Kind == TEXT("event") || Kind == TEXT("event_complete"))
	{
		const FString EventId = SelfTestReadString(Condition, TEXT("id"), SelfTestReadString(Condition, TEXT("event")));
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
		for (const TSharedPtr<FJsonObject>& Child : SelfTestReadObjectArray(Condition, Field))
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

		for (const FString& Key : SelfTestReadStringArray(EventRaw, TEXT("dialogue_keys")))
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

		const FString EventAnchor = SelfTestReadString(EventRaw, TEXT("anchor"));
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
				const FString Type = SelfTestReadString(Reward, TEXT("type"));
				if (!KnownRewardTypes.Contains(Type))
				{
					BadRewards.Add(FString::Printf(TEXT("%s:%s"), *EventId, *Type));
				}
				if (Type == TEXT("pack"))
				{
					const FString PackId = SelfTestReadString(Reward, TEXT("pack"), SelfTestReadString(Reward, TEXT("pack_id")));
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
			const FString Type = SelfTestReadString(Outcome, TEXT("type"));
			if (!KnownOutcomeTypes.Contains(Type))
			{
				BadOutcomes.Add(FString::Printf(TEXT("%s:%s"), *EventId, *Type));
			}
			if (Type == TEXT("reward") || Type == TEXT("grant_reward"))
			{
				const FString RewardId = SelfTestReadString(Outcome, TEXT("reward_id"), SelfTestReadString(Outcome, TEXT("id")));
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
				for (const FString& DeckId : SelfTestReadStringArray(Duelist, TEXT("decks")))
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
					ValidateDuel(EventId, SelfTestReadString(Duel, TEXT("opponent_id"), SelfTestReadString(Duel, TEXT("opponent"))),
						SelfTestReadString(Duel, TEXT("opponent_deck_id"), SelfTestReadString(Duel, TEXT("deck"))));
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
						SelfTestReadString(Request, TEXT("opponent")), SelfTestReadString(Request, TEXT("deck")));
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

	// ---------------------------------------------------------------- save transaction
	// A malformed provider section must be rejected before profile/calendar state
	// is applied. This is the save-fuzz failure case for a registered provider.
	if (UGameInstance* GameInstance = GetGameInstance())
	{
		UDASaveSubsystem* Save = GameInstance->GetSubsystem<UDASaveSubsystem>();
		UDASettings* Settings = GameInstance->GetSubsystem<UDASettings>();
		if (Save && Settings)
		{
			TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
			Root->SetNumberField(TEXT("version"), UDASaveSubsystem::CurrentVersion);
			Profile->WriteSaveData(Root);
			Calendar->WriteSaveData(Root);
			TSharedPtr<FJsonObject> SettingsObject = MakeShared<FJsonObject>();
			Settings->WriteSaveData(SettingsObject);
			Root->SetObjectField(TEXT("settings"), SettingsObject);

			TSharedPtr<FJsonObject> BadStory = MakeShared<FJsonObject>();
			BadStory->SetNumberField(TEXT("version"), 1);
			BadStory->SetStringField(TEXT("state"), TEXT("{malformed"));
			Root->SetObjectField(TEXT("story"), BadStory);

			const FString NameBefore = Profile->GetPlayerName();
			const int32 DPBefore = Profile->GetDP();
			FString SaveError;
			const bool bRejected = !Save->LoadPayloadJsonWithContext(
				UDASaveSubsystem::SerializeCanonicalJson(Root), Profile, Calendar, Settings, SaveError);
			AddCheck(TEXT("malformed story provider is rejected"), bRejected, SaveError);
			AddCheck(TEXT("failed provider load leaves the profile intact"),
				Profile->GetPlayerName().Equals(NameBefore) && Profile->GetDP() == DPBefore,
				FString::Printf(TEXT("%s/%d"), *Profile->GetPlayerName(), Profile->GetDP()));
		}
		else
		{
			AddInfo(TEXT("save/settings subsystem unavailable; provider failure case skipped"));
		}
	}

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
