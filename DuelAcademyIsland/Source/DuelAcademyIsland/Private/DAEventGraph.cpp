// Duel Academy Island - story event graph implementation.

#include "DAEventGraph.h"

#include "DAInventorySubsystem.h"
#include "DAProfileSubsystem.h"
#include "DACalendarSubsystem.h"
#include "DuelAcademyIsland.h"

#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"

namespace
{
	int32 MonthNumberToIndex(int32 MonthNumber)
	{
		return ((MonthNumber - 10) % 12 + 12) % 12;
	}

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

	bool CompareInt(int32 Left, const FString& Op, int32 Right)
	{
		if (Op == TEXT("!=")) return Left != Right;
		if (Op == TEXT(">"))  return Left > Right;
		if (Op == TEXT(">=")) return Left >= Right;
		if (Op == TEXT("<"))  return Left < Right;
		if (Op == TEXT("<=")) return Left <= Right;
		return Left == Right;
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
}

bool FDAEventGraph::LoadFromJson(const TSharedPtr<FJsonObject>& Root, FString& OutError)
{
	Events.Reset();
	EventIndex.Reset();

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
		Event.Id = ReadString(Object, TEXT("id"));
		Event.Title = ReadString(Object, TEXT("title"), Event.Id);
		Event.Scene = ReadString(Object, TEXT("scene"));
		Event.Priority = ReadInt(Object, TEXT("priority"), 0);
		Event.bOnce = ReadBool(Object, TEXT("once"), true);
		Event.bRepeatable = ReadBool(Object, TEXT("repeatable"), false);
		Event.bOptional = ReadBool(Object, TEXT("optional"), false);
		Event.bCanonEvent = ReadBool(Object, TEXT("canon_event"), false);
		Event.Raw = Object;

		const TSharedPtr<FJsonObject>* TriggerObject = nullptr;
		if (Object->TryGetObjectField(TEXT("trigger"), TriggerObject) && TriggerObject)
		{
			Event.Trigger = *TriggerObject;
		}

		Event.Requirements = ReadObjectArray(Object, TEXT("requirements"));
		if (Event.Requirements.Num() == 0)
		{
			Event.Requirements = ReadObjectArray(Object, TEXT("requires"));
		}
		Event.Outcomes = ReadObjectArray(Object, TEXT("outcomes"));

		const TArray<TSharedPtr<FJsonValue>>* QueueValues = nullptr;
		if (Object->TryGetArrayField(TEXT("scene_queue"), QueueValues) && QueueValues)
		{
			for (const TSharedPtr<FJsonValue>& QueueValue : *QueueValues)
			{
				if (QueueValue.IsValid())
				{
					Event.SceneQueue.Add(QueueValue->AsString());
				}
			}
		}

		if (Event.Id.IsEmpty())
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: event without id skipped."));
			continue;
		}
		if (EventIndex.Contains(Event.Id))
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Story: duplicate event id %s skipped."), *Event.Id);
			continue;
		}

		EventIndex.Add(Event.Id, Events.Num());
		Events.Add(Event);
	}

	OutError.Reset();
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Story: loaded %d event definitions."), Events.Num());
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
	if (Tail.StartsWith(TEXT("e")))
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

	const bool bNegate = ReadBool(Condition, TEXT("negate"), false);
	const FString Kind = ReadString(Condition, TEXT("type"));

	bool bResult = false;

	if (Kind.IsEmpty())
	{
		const TArray<TSharedPtr<FJsonObject>> AllConditions = ReadObjectArray(Condition, TEXT("all"));
		const TArray<TSharedPtr<FJsonObject>> AnyConditions = ReadObjectArray(Condition, TEXT("any"));
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
		TArray<TSharedPtr<FJsonObject>> Nested = ReadObjectArray(Condition, TEXT("conditions"));
		if (Nested.Num() == 0)
		{
			Nested = ReadObjectArray(Condition, TEXT("all"));
		}
		if (Nested.Num() == 0)
		{
			Nested = ReadObjectArray(Condition, TEXT("any"));
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
			: ReadString(Condition, TEXT("id"), ReadString(Condition, TEXT("flag")));
		bool bExpected = true;
		if (Kind == TEXT("flag"))
		{
			bExpected = ReadBool(Condition, TEXT("value"), true);
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
		const FString Counter = ReadString(Condition, TEXT("id"), ReadString(Condition, TEXT("counter")));
		const int32 Value = Profile ? Profile->GetCounter(Counter) : 0;
		const int32 Expected = ReadInt(Condition, TEXT("value"), 0);
		const FString Op = ReadString(Condition, TEXT("op"), TEXT(">="));
		bResult = CompareInt(Value, Op, Expected);
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("counter %s is %d, expected %s %d"), *Counter, Value, *Op, Expected);
		}
	}
	else if (Kind == TEXT("event") || Kind == TEXT("event_complete"))
	{
		const FString EventId = ReadString(Condition, TEXT("id"), ReadString(Condition, TEXT("event")));
		const bool bComplete = Profile && Profile->GetFlag(EventCompletionFlag(EventId));
		const FString State = ReadString(Condition, TEXT("state"), TEXT("complete"));
		bResult = State.IsEmpty() || State == TEXT("complete") ? bComplete : true;
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("event %s is not complete"), *EventId);
		}
	}
	else if (Kind == TEXT("date") || Kind == TEXT("date_at_least"))
	{
		if (!Calendar)
		{
			OutReason = TEXT("calendar is unavailable");
			return false;
		}
		const int32 TargetYear = ReadInt(Condition, TEXT("year"), Calendar->GetYear());
		const int32 MonthNumber = ReadInt(Condition, TEXT("month"),
			ReadInt(Condition, TEXT("calendar_month"), Calendar->GetMonthNumber()));
		const int32 TargetMonthIndex = ReadInt(Condition, TEXT("month_index"), MonthNumberToIndex(MonthNumber));
		const int32 TargetDay = ReadInt(Condition, TEXT("day"), Calendar->GetDay());
		const int32 TargetAbsolute = Calendar->GetAbsoluteDayFor(TargetYear, TargetMonthIndex, TargetDay);
		const int32 CurrentAbsolute = Calendar->GetAbsoluteDay();
		const FString Op = ReadString(Condition, TEXT("op"), Kind == TEXT("date_at_least") ? TEXT(">=") : TEXT("=="));
		bResult = CompareInt(CurrentAbsolute, Op, TargetAbsolute);

		const FString ExpectedWeekday = ReadString(Condition, TEXT("weekday"));
		if (bResult && !ExpectedWeekday.IsEmpty())
		{
			bResult = Calendar->GetWeekdayName(Calendar->GetWeekday()).Equals(ExpectedWeekday, ESearchCase::IgnoreCase);
		}
		const FString ExpectedPeriod = ReadString(Condition, TEXT("period"));
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
		const FString Expected = ReadString(Condition, TEXT("value"));
		bResult = Calendar && Calendar->GetWeekdayName(Calendar->GetWeekday()).Equals(Expected, ESearchCase::IgnoreCase);
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("weekday is not %s"), *Expected);
		}
	}
	else if (Kind == TEXT("period"))
	{
		const FString Expected = ReadString(Condition, TEXT("value"));
		bResult = Calendar && Calendar->GetPeriodName(Calendar->GetPeriod()).Equals(Expected, ESearchCase::IgnoreCase);
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("period is not %s"), *Expected);
		}
	}
	else if (Kind == TEXT("dorm"))
	{
		const FString Expected = ReadString(Condition, TEXT("value"));
		const FString Actual = Profile ? DuelAcademyProfile::DormToSaveKey(Profile->GetDorm()) : FString();
		bResult = Actual.Equals(Expected, ESearchCase::IgnoreCase);
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("dorm is %s, expected %s"), *Actual, *Expected);
		}
	}
	else if (Kind == TEXT("title"))
	{
		const FString Expected = ReadString(Condition, TEXT("value"));
		const FString Actual = Profile ? Profile->GetTitle() : FString();
		bResult = Actual.Equals(Expected, ESearchCase::IgnoreCase) || Actual.Contains(Expected, ESearchCase::IgnoreCase);
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("title is %s, expected %s"), *Actual, *Expected);
		}
	}
	else if (Kind == TEXT("card"))
	{
		const int32 CardId = ReadInt(Condition, TEXT("id"), ReadInt(Condition, TEXT("card_id"), 0));
		const int32 MinCount = ReadInt(Condition, TEXT("min_count"), 1);
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
			else
			{
				Count = Profile->GetCounter(FString::Printf(TEXT("card_%d"), CardId));
			}
		}
		bResult = Count >= MinCount;
		if (!bResult)
		{
			OutReason = FString::Printf(TEXT("card %d count is %d, expected >= %d"), CardId, Count, MinCount);
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

	const FString Kind = ReadString(Event.Trigger, TEXT("type"));
	if (Kind == TEXT("new_game"))
	{
		const bool bStarted = Profile && (Profile->GetFlag(TEXT("new_game")) || Profile->GetFlag(TEXT("new_game_started")));
		if (!bStarted)
		{
			OutReason = TEXT("new game has not started");
		}
		return bStarted;
	}
	if (Kind == TEXT("date") || Kind == TEXT("flag") || Kind == TEXT("event") || Kind == TEXT("event_complete"))
	{
		return EvaluateCondition(Event.Trigger, Profile, Calendar, OutReason);
	}
	if (Kind == TEXT("talk") || Kind == TEXT("always"))
	{
		OutReason.Reset();
		return true;
	}
	if (Kind.IsEmpty())
	{
		OutReason.Reset();
		return true;
	}

	OutReason = FString::Printf(TEXT("unsupported trigger type '%s'"), *Kind);
	return false;
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
