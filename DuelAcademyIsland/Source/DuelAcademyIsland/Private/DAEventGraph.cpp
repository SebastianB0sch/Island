// Duel Academy Island - story event graph implementation.

#include "DAEventGraph.h"

#include "DAInventorySubsystem.h"
#include "DAProfileSubsystem.h"
#include "DACalendarSubsystem.h"
#include "DAJson.h"
#include "DuelAcademyIsland.h"

#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"

namespace
{
	/** Maps "Slifer Red", "Slifer" and save keys onto one comparable token. */
	FString NormalizeDormKey(const FString& Value)
	{
		const FString Lower = Value.ToLower();
		if (Lower.Contains(TEXT("slifer")))
		{
			return TEXT("slifer");
		}
		if (Lower.Contains(TEXT("obelisk")))
		{
			return TEXT("obelisk");
		}
		if (Lower.Contains(TEXT("yellow")) || Lower == TEXT("ra"))
		{
			return TEXT("ra");
		}
		if (Lower.Contains(TEXT("white")) || Lower.Contains(TEXT("society")))
		{
			return TEXT("white");
		}
		return Lower;
	}

	bool CompareInt(int32 Left, const FString& Op, int32 Right)
	{
		if (Op == TEXT("!=")) return Left != Right;
		if (Op == TEXT(">"))  return Left > Right;
		if (Op == TEXT(">=")) return Left >= Right;
		if (Op == TEXT("<"))  return Left < Right;
		if (Op == TEXT("<=")) return Left <= Right;
		return Left == Right;
	}
}

bool FDAEventGraph::LoadFromJson(const TSharedPtr<FJsonObject>& Root, FString& OutError)
{
	Events.Reset();
	EventIndex.Reset();

	int32 Added = 0;
	return MergeFromJson(Root, TSet<FString>(), OutError, Added);
}

bool FDAEventGraph::MergeFromJson(const TSharedPtr<FJsonObject>& Root, const TSet<FString>& ExcludedIds,
	FString& OutError, int32& OutAdded)
{
	OutAdded = 0;

	if (!Root.IsValid())
	{
		OutError = TEXT("event graph root is null");
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* EventValues = nullptr;
	if (!Root->TryGetArrayField(TEXT("events"), EventValues) || !EventValues)
	{
		OutError = TEXT("event graph has no events array");
		return false;
	}

	for (const TSharedPtr<FJsonValue>& Value : *EventValues)
	{
		const TSharedPtr<FJsonObject> Object = Value.IsValid() ? Value->AsObject() : TSharedPtr<FJsonObject>();
		if (!Object.IsValid())
		{
			continue;
		}

		FDAEventDefinition Event;
		Event.Id = DAJson::ReadString(Object, TEXT("id"));
		Event.Title = DAJson::ReadString(Object, TEXT("title"), Event.Id);
		Event.Scene = DAJson::ReadString(Object, TEXT("scene"));
		Event.Priority = DAJson::ReadInt(Object, TEXT("priority"), 0);
		Event.bOnce = DAJson::ReadBool(Object, TEXT("once"), true);
		Event.bRepeatable = DAJson::ReadBool(Object, TEXT("repeatable"), false);
		Event.bOptional = DAJson::ReadBool(Object, TEXT("optional"), false);
		Event.bCanonEvent = DAJson::ReadBool(Object, TEXT("canon_event"), false);
		Event.Raw = Object;

		const TSharedPtr<FJsonObject>* TriggerObject = nullptr;
		if (Object->TryGetObjectField(TEXT("trigger"), TriggerObject) && TriggerObject)
		{
			Event.Trigger = *TriggerObject;
		}

		Event.Requirements = DAJson::ReadObjectArray(Object, TEXT("requirements"));
		if (Event.Requirements.Num() == 0)
		{
			Event.Requirements = DAJson::ReadObjectArray(Object, TEXT("requires"));
		}
		Event.Outcomes = DAJson::ReadObjectArray(Object, TEXT("outcomes"));

		if (Event.Id.IsEmpty())
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: event without id skipped."));
			continue;
		}
		if (ExcludedIds.Contains(Event.Id))
		{
			UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: event %s excluded from merge."), *Event.Id);
			continue;
		}
		if (EventIndex.Contains(Event.Id))
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: duplicate event id %s skipped."), *Event.Id);
			continue;
		}

		EventIndex.Add(Event.Id, Events.Num());
		Events.Add(Event);
		++OutAdded;
	}

	OutError.Reset();
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: merged %d event definitions (%d total)."), OutAdded, Events.Num());
	return true;
}

const FDAEventDefinition* FDAEventGraph::FindEvent(const FString& EventId) const
{
	const int32* Index = EventIndex.Find(EventId);
	return Index ? &Events[*Index] : nullptr;
}

FString FDAEventGraph::EventCompletionFlag(const FString& EventId)
{
	FString Tail = EventId.ToLower();
	if (Tail.Len() > 1 && Tail[0] == TEXT('e') && FChar::IsDigit(Tail[1]))
	{
		Tail = Tail.RightChop(1);
	}
	return FString::Printf(TEXT("event_%s_cleared"), *Tail);
}

bool FDAEventGraph::IsEventComplete(const FString& EventId, const UDAProfileSubsystem* Profile) const
{
	return Profile && Profile->GetFlag(EventCompletionFlag(EventId));
}

bool FDAEventGraph::EvaluateConditionArray(const TArray<TSharedPtr<FJsonObject>>& Conditions,
	const UDAProfileSubsystem* Profile, const UDACalendarSubsystem* Calendar, FString& OutReason)
{
	for (const TSharedPtr<FJsonObject>& Condition : Conditions)
	{
		if (!EvaluateCondition(Condition, Profile, Calendar, OutReason))
		{
			return false;
		}
	}
	OutReason.Reset();
	return true;
}

bool FDAEventGraph::EvaluateCondition(const TSharedPtr<FJsonObject>& Condition,
	const UDAProfileSubsystem* Profile, const UDACalendarSubsystem* Calendar, FString& OutReason)
{
	if (!Condition.IsValid())
	{
		OutReason.Reset();
		return true;
	}

	const bool bNegate = DAJson::ReadBool(Condition, TEXT("negate"), false);
	const FString Kind = DAJson::ReadString(Condition, TEXT("type"));

	bool bResult = false;

	if (Kind.IsEmpty())
	{
		const TArray<TSharedPtr<FJsonObject>> AllConditions = DAJson::ReadObjectArray(Condition, TEXT("all"));
		const TArray<TSharedPtr<FJsonObject>> AnyConditions = DAJson::ReadObjectArray(Condition, TEXT("any"));
		if (AllConditions.Num() > 0)
		{
			bResult = EvaluateConditionArray(AllConditions, Profile, Calendar, OutReason);
		}
		else if (AnyConditions.Num() > 0)
		{
			bResult = false;
			for (const TSharedPtr<FJsonObject>& Child : AnyConditions)
			{
				FString ChildReason;
				if (EvaluateCondition(Child, Profile, Calendar, ChildReason))
				{
					bResult = true;
					break;
				}
			}
		}
		else
		{
			bResult = true;
		}
	}
	else if (Kind == TEXT("all") || Kind == TEXT("any"))
	{
		TArray<TSharedPtr<FJsonObject>> Nested = DAJson::ReadObjectArray(Condition, TEXT("conditions"));
		if (Nested.Num() == 0)
		{
			Nested = DAJson::ReadObjectArray(Condition, TEXT("all"));
		}
		if (Nested.Num() == 0)
		{
			Nested = DAJson::ReadObjectArray(Condition, TEXT("any"));
		}
		if (Kind == TEXT("any"))
		{
			bResult = false;
			for (const TSharedPtr<FJsonObject>& Child : Nested)
			{
				FString ChildReason;
				if (EvaluateCondition(Child, Profile, Calendar, ChildReason))
				{
					bResult = true;
					break;
				}
			}
		}
		else
		{
			bResult = true;
			for (const TSharedPtr<FJsonObject>& Child : Nested)
			{
				FString ChildReason;
				if (!EvaluateCondition(Child, Profile, Calendar, ChildReason))
				{
					bResult = false;
					OutReason = ChildReason;
					break;
				}
			}
		}
	}
	else if (Kind == TEXT("flag") || Kind == TEXT("new_game"))
	{
		const FString Flag = Kind == TEXT("new_game")
			? TEXT("new_game")
			: DAJson::ReadString(Condition, TEXT("id"), DAJson::ReadString(Condition, TEXT("flag")));
		bool bExpected = true;
		if (Kind == TEXT("flag"))
		{
			bExpected = DAJson::ReadBool(Condition, TEXT("value"), true);
		}
		const bool bHasFlag = Profile && (Profile->GetFlag(Flag) || (Kind == TEXT("new_game") && Profile->GetFlag(TEXT("new_game_started"))));
		bResult = bHasFlag == bExpected;
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("flag %s is not %s"), *Flag, bExpected ? TEXT("true") : TEXT("false"));
		}
	}
	else if (Kind == TEXT("counter"))
	{
		const FString Counter = DAJson::ReadString(Condition, TEXT("id"), DAJson::ReadString(Condition, TEXT("counter")));
		const int32 Value = Profile ? Profile->GetCounter(Counter) : 0;
		const int32 Expected = DAJson::ReadInt(Condition, TEXT("value"), 0);
		const FString Op = DAJson::ReadString(Condition, TEXT("op"), TEXT(">="));
		bResult = CompareInt(Value, Op, Expected);
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("counter %s is %d, expected %s %d"), *Counter, Value, *Op, Expected);
		}
	}
	else if (Kind == TEXT("event") || Kind == TEXT("event_complete"))
	{
		const FString EventId = DAJson::ReadString(Condition, TEXT("id"), DAJson::ReadString(Condition, TEXT("event")));
		const bool bComplete = Profile && Profile->GetFlag(EventCompletionFlag(EventId));
		const FString State = DAJson::ReadString(Condition, TEXT("state"), TEXT("complete"));
		bResult = State.IsEmpty() || State == TEXT("complete") ? bComplete : true;
		if (!bResult)
		{
			bResult = bComplete;
			if (!bResult)
			{
				OutReason = FString::Printf(TEXT("event %s is not complete"), *EventId);
			}
		}
		else if (State.Equals(TEXT("incomplete"), ESearchCase::IgnoreCase))
		{
			bResult = !bComplete;
			if (!bResult)
			{
				OutReason = FString::Printf(TEXT("event %s is already complete"), *EventId);
			}
		}
		else
		{
			bResult = true;
		}
	}
	else if (Kind == TEXT("date") || Kind == TEXT("date_at_least"))
	{
		if (!Calendar)
		{
			OutReason = TEXT("calendar is unavailable");
			return false;
		}
		const int32 TargetYear = DAJson::ReadInt(Condition, TEXT("year"), Calendar->GetYear());
		const int32 MonthNumber = DAJson::ReadInt(Condition, TEXT("month"),
			DAJson::ReadInt(Condition, TEXT("calendar_month"), Calendar->GetMonthNumber()));
		const int32 TargetMonthIndex = DAJson::ReadInt(Condition, TEXT("month_index"), UDACalendarSubsystem::MonthNumberToIndex(MonthNumber));
		const bool bHasDay = Condition->HasField(TEXT("day"));
		const int32 TargetDay = DAJson::ReadInt(Condition, TEXT("day"), 1);
		const int32 TargetAbsolute = Calendar->GetAbsoluteDayFor(TargetYear, TargetMonthIndex, TargetDay);
		const int32 CurrentAbsolute = Calendar->GetAbsoluteDay();
		const FString Op = DAJson::ReadString(Condition, TEXT("op"), Kind == TEXT("date_at_least") ? TEXT(">=") : TEXT("=="));
		if (!bHasDay && Op == TEXT("=="))
		{
			// A date without a day means "any time in this month" (E09 festival).
			bResult = Calendar->GetYear() == TargetYear && Calendar->GetMonthIndex() == TargetMonthIndex;
		}
		else
		{
			bResult = CompareInt(CurrentAbsolute, Op, TargetAbsolute);
		}

		const FString ExpectedWeekday = DAJson::ReadString(Condition, TEXT("weekday"));
		if (bResult && !ExpectedWeekday.IsEmpty())
		{
			bResult = Calendar->GetWeekdayName(Calendar->GetWeekday()).Equals(ExpectedWeekday, ESearchCase::IgnoreCase);
		}
		const FString ExpectedPeriod = DAJson::ReadString(Condition, TEXT("period"));
		if (bResult && !ExpectedPeriod.IsEmpty())
		{
			bResult = Calendar->GetPeriodName(Calendar->GetPeriod()).Equals(ExpectedPeriod, ESearchCase::IgnoreCase);
		}
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("date is not %s %04d-%02d-%02d"), *Op, TargetYear, MonthNumber, TargetDay);
		}
	}
	else if (Kind == TEXT("weekday"))
	{
		const FString Expected = DAJson::ReadString(Condition, TEXT("value"));
		bResult = Calendar && Calendar->GetWeekdayName(Calendar->GetWeekday()).Equals(Expected, ESearchCase::IgnoreCase);
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("weekday is not %s"), *Expected);
		}
	}
	else if (Kind == TEXT("period"))
	{
		const FString Expected = DAJson::ReadString(Condition, TEXT("value"));
		bResult = Calendar && Calendar->GetPeriodName(Calendar->GetPeriod()).Equals(Expected, ESearchCase::IgnoreCase);
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("period is not %s"), *Expected);
		}
	}
	else if (Kind == TEXT("dorm"))
	{
		const FString Expected = NormalizeDormKey(DAJson::ReadString(Condition, TEXT("value")));
		const FString Actual = NormalizeDormKey(Profile ? DuelAcademyProfile::DormToSaveKey(Profile->GetDorm()) : FString());
		bResult = Actual.Equals(Expected, ESearchCase::IgnoreCase);
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("dorm is %s, expected %s"), *Actual, *Expected);
		}
	}
	else if (Kind == TEXT("exam_day"))
	{
		bResult = Calendar && Calendar->IsExamDay();
		if (!bResult)
		{
			OutReason = TEXT("today is not an exam day");
		}
	}
	else if (Kind == TEXT("title"))
	{
		const FString Expected = DAJson::ReadString(Condition, TEXT("value"));
		const FString Actual = Profile ? Profile->GetTitle() : FString();
		bResult = Actual.Equals(Expected, ESearchCase::IgnoreCase) || Actual.Contains(Expected, ESearchCase::IgnoreCase);
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("title is %s, expected %s"), *Actual, *Expected);
		}
	}
	else if (Kind == TEXT("card"))
	{
		const int32 CardId = DAJson::ReadInt(Condition, TEXT("id"), DAJson::ReadInt(Condition, TEXT("card_id"), 0));
		const int32 MinCount = DAJson::ReadInt(Condition, TEXT("min_count"), 1);
		int32 Count = 0;
		if (Profile)
		{
			if (UGameInstance* GI = Profile->GetGameInstance())
			{
				if (UDAInventorySubsystem* Inventory = GI->GetSubsystem<UDAInventorySubsystem>())
				{
					Count = Inventory->GetCount(CardId);
				}
			}
			// The profile counter is a fallback for headless tests and for lanes
			// that have not registered the A06 inventory provider yet.
			Count = FMath::Max(Count, Profile->GetCounter(FString::Printf(TEXT("card_%d"), CardId)));
		}
		bResult = Count >= MinCount;
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("card %d count is %d, expected >= %d"), CardId, Count, MinCount);
		}
	}
	else if (Kind == TEXT("wins_against_each"))
	{
		const int32 WinsPerDuelist = DAJson::ReadInt(Condition, TEXT("count"), 10);
		const int32 RequiredDuelists = DAJson::ReadInt(Condition, TEXT("duelists"), 20);
		static const TCHAR* const Duelists[] = {
			TEXT("jaden"), TEXT("syrus"), TEXT("chumley"), TEXT("bastion"), TEXT("chazz"),
			TEXT("zane"), TEXT("alexis"), TEXT("jasmine"), TEXT("mindy"), TEXT("crowler"),
			TEXT("banner"), TEXT("blair"), TEXT("brier"), TEXT("beauregard"), TEXT("topher"),
			TEXT("conklin"), TEXT("damon"), TEXT("dimitri"), TEXT("gerard"), TEXT("fontaine")
		};
		int32 Qualified = 0;
		for (const TCHAR* Duelist : Duelists)
		{
			if (Profile && Profile->GetCounter(FString::Printf(TEXT("wins_%s"), Duelist)) >= WinsPerDuelist)
			{
				++Qualified;
			}
		}
		bResult = Qualified >= RequiredDuelists;
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("only %d/%d duelists have %d wins"), Qualified, RequiredDuelists, WinsPerDuelist);
		}
	}
	else if (Kind == TEXT("written_correct_percent"))
	{
		const int32 Percent = DAJson::ReadInt(Condition, TEXT("percent"), 60);
		const int32 Correct = Profile ? Profile->GetCounter(TEXT("written_correct")) : 0;
		const int32 Total = Profile ? Profile->GetCounter(TEXT("written_total")) : 0;
		bResult = Total > 0 && static_cast<int64>(Correct) * 100 >= static_cast<int64>(Percent) * Total;
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("written score is %d/%d, expected >= %d%%"), Correct, Total, Percent);
		}
	}
	else if (Kind == TEXT("after_ending"))
	{
		bResult = Profile && Profile->GetFlag(TEXT("post_game"));
		if (!bResult)
		{
			OutReason = TEXT("the post-game has not started");
		}
	}
	else if (Kind == TEXT("random_chance"))
	{
		// Stable per-day roll: re-evaluating the same event on the same day
		// cannot flicker between available and unavailable. The next eligible
		// day rolls again, so an optional event eventually happens.
		const FString Chance = DAJson::ReadString(Condition, TEXT("value"), TEXT("1/1"));
		FString Numerator;
		FString Denominator;
		if (!Chance.Split(TEXT("/"), &Numerator, &Denominator))
		{
			Numerator = Chance;
			Denominator = TEXT("1");
		}
		const int32 Num = FMath::Max(0, FCString::Atoi(*Numerator));
		const int32 Den = FMath::Max(1, FCString::Atoi(*Denominator));
		const FString Seed = DAJson::ReadString(Condition, TEXT("seed"), TEXT("random"));
		const int32 Day = Calendar ? Calendar->GetAbsoluteDay() : 0;
		const int32 Period = Calendar ? static_cast<int32>(Calendar->GetPeriod()) : 0;
		const uint32 Roll = HashCombine(HashCombine(GetTypeHash(Seed), static_cast<uint32>(Day)),
			static_cast<uint32>(Period)) % static_cast<uint32>(Den);
		bResult = static_cast<int32>(Roll) < Num;
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("%s roll failed today (%d/%d)"), *Seed, Num, Den);
		}
	}
	else if (Kind == TEXT("talk") || Kind == TEXT("always") || Kind == TEXT("location"))
	{
		// Talk is caller-driven; location is checked by the world lane.
		bResult = true;
	}
	else if (Kind == TEXT("duel_result") || Kind == TEXT("exam_result"))
	{
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Story: %s condition is not evaluated by the event graph; treating as pass."), *Kind);
		bResult = true;
	}
	else
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: unknown condition type '%s'; treating as pass."), *Kind);
		bResult = true;
	}

	if (bNegate)
	{
		bResult = !bResult;
		if (bResult)
		{
			OutReason.Reset();
		}
	}
	if (bResult)
	{
		OutReason.Reset();
	}
	return bResult;
}

bool FDAEventGraph::EvaluateTrigger(const FDAEventDefinition& Event, const UDAProfileSubsystem* Profile,
	const UDACalendarSubsystem* Calendar, FString& OutReason) const
{
	if (!Event.Trigger.IsValid())
	{
		OutReason.Reset();
		return true;
	}

	const FString Kind = DAJson::ReadString(Event.Trigger, TEXT("type"));
	if (Kind == TEXT("new_game"))
	{
		const bool bStarted = Profile && (Profile->GetFlag(TEXT("new_game")) || Profile->GetFlag(TEXT("new_game_started")));
		if (!bStarted)
		{
			OutReason = TEXT("new game has not started");
		}
		return bStarted;
	}
	if (Kind == TEXT("date") || Kind == TEXT("flag") || Kind == TEXT("event") || Kind == TEXT("event_complete")
		|| Kind == TEXT("weekday") || Kind == TEXT("period") || Kind == TEXT("exam_day"))
	{
		return EvaluateCondition(Event.Trigger, Profile, Calendar, OutReason);
	}
	if (Kind == TEXT("talk") || Kind == TEXT("always"))
	{
		// A genuinely empty trigger (no type field and no children) silently
		// continues; the event is available whenever its requirements pass.
		OutReason.Reset();
		return true;
	}
	if (Kind == TEXT("talk") || Kind == TEXT("always"))
	{
		// Caller-driven admissions; NotifyTalkToNPC matches the NPC id before
		// StartEvent, so the graph alone cannot gate these.
		OutReason.Reset();
		return true;
	}

	// Everything else is part of the shared condition vocabulary (new_game,
	// date, date_at_least, flag, event, counter, card, dorm, title,
	// written_correct_percent, after_ending, random_chance, all/any
	// composites, ...). Evaluate it with the condition evaluator instead of
	// silently blocking the event: the old whitelist only covered a handful of
	// kinds and made counter/card/date_at_least/after_ending/random_chance
	// triggers unreachable.
	return EvaluateCondition(Event.Trigger, Profile, Calendar, OutReason);
}

bool FDAEventGraph::EvaluateRequirements(const FDAEventDefinition& Event, const UDAProfileSubsystem* Profile,
	const UDACalendarSubsystem* Calendar, FString& OutReason) const
{
	return EvaluateConditionArray(Event.Requirements, Profile, Calendar, OutReason);
}

TArray<FString> FDAEventGraph::GetAvailableEvents(const UDAProfileSubsystem* Profile,
	const UDACalendarSubsystem* Calendar) const
{
	TArray<FString> Available;
	for (const FDAEventDefinition& Event : Events)
	{
		if (Event.bOnce && IsEventComplete(Event.Id, Profile))
		{
			continue;
		}

		FString Reason;
		if (!EvaluateTrigger(Event, Profile, Calendar, Reason))
		{
			continue;
		}
		if (!EvaluateRequirements(Event, Profile, Calendar, Reason))
		{
			continue;
		}
		Available.Add(Event.Id);
	}

	Available.Sort([this](const FString& A, const FString& B)
	{
		const FDAEventDefinition* EventA = FindEvent(A);
		const FDAEventDefinition* EventB = FindEvent(B);
		return EventA && EventB ? EventA->Priority > EventB->Priority : A < B;
	});
	return Available;
}
