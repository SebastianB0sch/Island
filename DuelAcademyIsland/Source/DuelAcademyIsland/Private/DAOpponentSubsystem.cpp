// Duel Academy Island - opponent roster/deck/AI loader.

#include "DAOpponentSubsystem.h"

#include "DACardRecords.h"
#include "DAJson.h"
#include "DuelAcademyIsland.h"
#include "Engine/GameInstance.h"
#include "HAL/FileManager.h"

namespace
{
	void ReadNumberMap(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TMap<FString, float>& Out)
	{
		const TSharedPtr<FJsonObject> MapObject = DAJson::ReadObject(Object, Field);
		if (!MapObject.IsValid())
		{
			return;
		}
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : MapObject->Values)
		{
			if (Pair.Value.IsValid() && Pair.Value->Type == EJson::Number)
			{
				Out.Add(DAJson::KeyToString(Pair.Key), static_cast<float>(Pair.Value->AsNumber()));
			}
		}
	}

	void ReadBoolMap(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TMap<FString, bool>& Out)
	{
		const TSharedPtr<FJsonObject> MapObject = DAJson::ReadObject(Object, Field);
		if (!MapObject.IsValid())
		{
			return;
		}
		for (const TPair<FJsonObject::FStringType, TSharedPtr<FJsonValue>>& Pair : MapObject->Values)
		{
			if (Pair.Value.IsValid() && Pair.Value->Type == EJson::Boolean)
			{
				Out.Add(DAJson::KeyToString(Pair.Key), Pair.Value->AsBool());
			}
		}
	}
}

void UDAOpponentSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	FString Error;
	Reload(Error);
}

bool UDAOpponentSubsystem::Reload(FString& OutError)
{
	OutError.Reset();
	Opponents.Reset();
	OpponentIndex.Reset();
	DeckList.Reset();
	DeckIndex.Reset();
	AIProfileList.Reset();
	AIProfileIndex.Reset();
	RuntimeState = FDAOpponentRuntimeState();
	bLoaded = false;

	const FString DataRoot = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Opponents"));
	if (!LoadRosterFile(FPaths::Combine(DataRoot, TEXT("roster.json")), OutError))
	{
		return false;
	}

	TArray<FString> Warnings;
	LoadDeckDirectory(FPaths::Combine(DataRoot, TEXT("decks")), Warnings);
	LoadAIProfileDirectory(FPaths::Combine(DataRoot, TEXT("ai")), Warnings);
	for (const FString& Warning : Warnings)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[Opponents] %s"), *Warning);
	}

	// A04's FDuelEngine::Start resolves both sides through
	// UCardDatabaseSubsystem::FindDeck, which historically only knew the
	// A06 starter list in Data/decks.json.  Register the A07 opponent decks
	// through the narrow card-database hook rather than teaching A06 economy
	// code about Content/Data/Opponents.
	if (UGameInstance* GameInstance = GetGameInstance())
	{
		if (UCardDatabaseSubsystem* CardDatabase = GameInstance->GetSubsystem<UCardDatabaseSubsystem>())
		{
			int32 Registered = 0;
			for (const FDAOpponentDeckDef& OpponentDeck : DeckList)
			{
				FStarterDeckDef RegisteredDeck;
				RegisteredDeck.Id = OpponentDeck.Id;
				RegisteredDeck.Name = OpponentDeck.Name;
				RegisteredDeck.Cards = OpponentDeck.Cards;
				RegisteredDeck.Extra = OpponentDeck.Extra;
				if (CardDatabase->RegisterDeck(RegisteredDeck))
				{
					++Registered;
				}
			}
			UE_LOG(LogDuelAcademyIsland, Log,
				TEXT("[Opponents] Registered %d/%d opponent decks with the card database."),
				Registered, DeckList.Num());
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("[Opponents] Card database unavailable; opponent deck ids will not resolve in FDuelEngine::Start."));
		}
	}

	bLoaded = Opponents.Num() > 0;
	if (!bLoaded)
	{
		OutError = TEXT("Roster loaded no duelists.");
		return false;
	}
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("[Opponents] %d duelists, %d decks, %d AI profiles."),
		Opponents.Num(), DeckList.Num(), AIProfileList.Num());
	return true;
}

bool UDAOpponentSubsystem::LoadRosterFile(const FString& Path, FString& OutError)
{
	TSharedPtr<FJsonValue> Root;
	if (!DAJson::LoadFile(Path, Root, OutError))
	{
		return false;
	}

	const TSharedPtr<FJsonObject> RootObject = Root->AsObject();
	if (!RootObject.IsValid())
	{
		OutError = TEXT("roster.json root must be an object.");
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* DuelistValues = nullptr;
	if (!RootObject->TryGetArrayField(TEXT("duelists"), DuelistValues))
	{
		OutError = TEXT("roster.json has no duelists array.");
		return false;
	}

	for (const TSharedPtr<FJsonValue>& Value : *DuelistValues)
	{
		const TSharedPtr<FJsonObject> Object = Value.IsValid() ? Value->AsObject() : nullptr;
		if (!Object.IsValid())
		{
			continue;
		}

		FDAOpponentDef Duelist;
		Duelist.Id = DAJson::ReadString(Object, TEXT("id"));
		if (Duelist.Id.IsEmpty())
		{
			continue;
		}
		Duelist.Name = DAJson::ReadString(Object, TEXT("name"));
		DAJson::AppendStringArray(Object, TEXT("aliases"), Duelist.Aliases);
		Duelist.Role = DAJson::ReadString(Object, TEXT("role"));
		Duelist.Rank = DAJson::ReadInt(Object, TEXT("rank"));
		Duelist.Dorm = DAJson::ReadString(Object, TEXT("dorm"));
		Duelist.Year = DAJson::ReadInt(Object, TEXT("year"), 1);
		Duelist.Title = DAJson::ReadString(Object, TEXT("title"));
		Duelist.AIProfile = DAJson::ReadString(Object, TEXT("ai_profile"));
		DAJson::AppendStringArray(Object, TEXT("decks"), Duelist.Decks);
		DAJson::AppendIntArray(Object, TEXT("signature_card_ids"), Duelist.SignatureCardIds);
		DAJson::AppendStringArray(Object, TEXT("signature_cards"), Duelist.SignatureCards);
		DAJson::AppendIntArray(Object, TEXT("canon_gift_card_ids"), Duelist.CanonGiftCardIds);
		Duelist.CanonSource = DAJson::ReadString(Object, TEXT("canon_source"));
		Duelist.CanonConfidence = DAJson::ReadString(Object, TEXT("canon_confidence"));
		Duelist.DefaultDeck = DAJson::ReadString(Object, TEXT("default_deck"));
		DAJson::AppendIntArray(Object, TEXT("ante"), Duelist.Ante);
		Duelist.Confidence = DAJson::ReadString(Object, TEXT("confidence"));
		Duelist.Source = DAJson::ReadString(Object, TEXT("source"));
		Duelist.Notes = DAJson::ReadString(Object, TEXT("notes"));

		const TArray<TSharedPtr<FJsonValue>>* EvolutionValues = nullptr;
		if (Object->TryGetArrayField(TEXT("evolution_rules"), EvolutionValues))
		{
			for (const TSharedPtr<FJsonValue>& EvolutionValue : *EvolutionValues)
			{
				const TSharedPtr<FJsonObject> EvolutionObject = EvolutionValue.IsValid() ? EvolutionValue->AsObject() : nullptr;
				if (!EvolutionObject.IsValid())
				{
					continue;
				}
				FDAOpponentEvolutionRule Rule;
				Rule.Id = DAJson::ReadString(EvolutionObject, TEXT("id"));
				Rule.AfterWins = DAJson::ReadInt(EvolutionObject, TEXT("after_wins"), 1);
				Rule.Counter = DAJson::ReadString(EvolutionObject, TEXT("counter"));
				Rule.Deck = DAJson::ReadString(EvolutionObject, TEXT("deck"));
				Rule.Description = DAJson::ReadString(EvolutionObject, TEXT("description"));
				Rule.Confidence = DAJson::ReadString(EvolutionObject, TEXT("confidence"));
				Rule.Source = DAJson::ReadString(EvolutionObject, TEXT("source"));
				Duelist.EvolutionRules.Add(MoveTemp(Rule));
			}
		}

		const TArray<TSharedPtr<FJsonValue>>* LocationValues = nullptr;
		if (Object->TryGetArrayField(TEXT("locations"), LocationValues))
		{
			for (const TSharedPtr<FJsonValue>& LocationValue : *LocationValues)
			{
				const TSharedPtr<FJsonObject> LocationObject = LocationValue.IsValid() ? LocationValue->AsObject() : nullptr;
				if (!LocationObject.IsValid())
				{
					continue;
				}
				FDAOpponentLocation Location;
				Location.Zone = DAJson::ReadString(LocationObject, TEXT("zone"));
				Location.Interior = DAJson::ReadString(LocationObject, TEXT("interior"));
				Location.Name = DAJson::ReadString(LocationObject, TEXT("name"));
				Duelist.Locations.Add(MoveTemp(Location));
			}
		}

		const TArray<TSharedPtr<FJsonValue>>* ScheduleValues = nullptr;
		if (Object->TryGetArrayField(TEXT("schedule"), ScheduleValues))
		{
			for (const TSharedPtr<FJsonValue>& ScheduleValue : *ScheduleValues)
			{
				const TSharedPtr<FJsonObject> ScheduleObject = ScheduleValue.IsValid() ? ScheduleValue->AsObject() : nullptr;
				if (!ScheduleObject.IsValid())
				{
					continue;
				}
				FDAOpponentScheduleSlot Slot;
				DAJson::AppendStringArray(ScheduleObject, TEXT("weekdays"), Slot.Weekdays);
				DAJson::AppendStringArray(ScheduleObject, TEXT("periods"), Slot.Periods);
				Slot.Zone = DAJson::ReadString(ScheduleObject, TEXT("zone"));
				Slot.Interior = DAJson::ReadString(ScheduleObject, TEXT("interior"));
				Duelist.Schedule.Add(MoveTemp(Slot));
			}
		}

		if (const TSharedPtr<FJsonObject> AccessObject = DAJson::ReadObject(Object, TEXT("access")))
		{
			Duelist.Access.RequiresFlag = DAJson::ReadString(AccessObject, TEXT("requires_flag"));
			Duelist.Access.RequiresTitle = DAJson::ReadString(AccessObject, TEXT("requires_title"));
			Duelist.Access.RequiresDorm = DAJson::ReadString(AccessObject, TEXT("requires_dorm"));
			Duelist.Access.bEventOnly = DAJson::ReadBool(AccessObject, TEXT("event_only"));
			Duelist.Access.MinDay = DAJson::ReadInt(AccessObject, TEXT("min_day"));
		}

		if (const TSharedPtr<FJsonObject> EmailObject = DAJson::ReadObject(Object, TEXT("email")))
		{
			Duelist.Email.UnlockFlag = DAJson::ReadString(EmailObject, TEXT("unlock_flag"));
			Duelist.Email.Address = DAJson::ReadString(EmailObject, TEXT("address"));
			const TArray<TSharedPtr<FJsonValue>>* ThreadValues = nullptr;
			if (EmailObject->TryGetArrayField(TEXT("threads"), ThreadValues))
			{
				for (const TSharedPtr<FJsonValue>& ThreadValue : *ThreadValues)
				{
					const TSharedPtr<FJsonObject> ThreadObject = ThreadValue.IsValid() ? ThreadValue->AsObject() : nullptr;
					if (!ThreadObject.IsValid())
					{
						continue;
					}
					FDAOpponentEmailThread Thread;
					Thread.Id = DAJson::ReadString(ThreadObject, TEXT("id"));
					Thread.Subject = DAJson::ReadString(ThreadObject, TEXT("subject"));
					Thread.UnlockFlag = DAJson::ReadString(ThreadObject, TEXT("unlock_flag"));
					Duelist.Email.Threads.Add(MoveTemp(Thread));
				}
			}
		}

		if (const TSharedPtr<FJsonObject> RequestObject = DAJson::ReadObject(Object, TEXT("duel_request")))
		{
			Duelist.DuelRequest.UnlockFlag = DAJson::ReadString(RequestObject, TEXT("unlock_flag"));
			Duelist.DuelRequest.MinWins = DAJson::ReadInt(RequestObject, TEXT("min_wins"));
			Duelist.DuelRequest.CooldownDays = DAJson::ReadInt(RequestObject, TEXT("cooldown_days"), 1);
			Duelist.DuelRequest.MaxPerDay = DAJson::ReadInt(RequestObject, TEXT("max_per_day"), 1);
		}

		const TArray<TSharedPtr<FJsonValue>>* GiftValues = nullptr;
		if (Object->TryGetArrayField(TEXT("gifts"), GiftValues))
		{
			for (const TSharedPtr<FJsonValue>& GiftValue : *GiftValues)
			{
				const TSharedPtr<FJsonObject> GiftObject = GiftValue.IsValid() ? GiftValue->AsObject() : nullptr;
				if (!GiftObject.IsValid())
				{
					continue;
				}
				FDAOpponentGift Gift;
				Gift.Id = DAJson::ReadString(GiftObject, TEXT("id"));
				Gift.Type = DAJson::ReadString(GiftObject, TEXT("type"));
				Gift.Amount = DAJson::ReadInt(GiftObject, TEXT("amount"));
				Gift.CardId = DAJson::ReadInt(GiftObject, TEXT("card_id"));
				Gift.Event = DAJson::ReadString(GiftObject, TEXT("event"));
				Gift.Confidence = DAJson::ReadString(GiftObject, TEXT("confidence"));
				Gift.Source = DAJson::ReadString(GiftObject, TEXT("source"));
				Duelist.Gifts.Add(MoveTemp(Gift));
			}
		}

		if (const TSharedPtr<FJsonObject> WalkObject = DAJson::ReadObject(Object, TEXT("walk_home")))
		{
			Duelist.WalkHome.bEnabled = DAJson::ReadBool(WalkObject, TEXT("enabled"));
			Duelist.WalkHome.Zone = DAJson::ReadString(WalkObject, TEXT("zone"));
			DAJson::AppendStringArray(WalkObject, TEXT("weekdays"), Duelist.WalkHome.Weekdays);
			Duelist.WalkHome.Period = DAJson::ReadString(WalkObject, TEXT("period"));
			Duelist.WalkHome.Flag = DAJson::ReadString(WalkObject, TEXT("flag"));
			Duelist.WalkHome.Confidence = DAJson::ReadString(WalkObject, TEXT("confidence"));
			Duelist.WalkHome.Source = DAJson::ReadString(WalkObject, TEXT("source"));
		}

		if (!OpponentIndex.Contains(Duelist.Id))
		{
			OpponentIndex.Add(Duelist.Id, Opponents.Num());
			Opponents.Add(MoveTemp(Duelist));
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[Opponents] Duplicate duelist id '%s' ignored."), *Duelist.Id);
		}
	}

	return Opponents.Num() > 0;
}

bool UDAOpponentSubsystem::LoadDeckFile(const FString& Path, FString& OutError)
{
	TSharedPtr<FJsonValue> Root;
	if (!DAJson::LoadFile(Path, Root, OutError))
	{
		return false;
	}
	const TSharedPtr<FJsonObject> Object = Root->AsObject();
	if (!Object.IsValid())
	{
		OutError = FString::Printf(TEXT("Deck root is not an object: %s"), *Path);
		return false;
	}

	FDAOpponentDeckDef Deck;
	Deck.Id = DAJson::ReadString(Object, TEXT("id"));
	if (Deck.Id.IsEmpty())
	{
		OutError = FString::Printf(TEXT("Deck has no id: %s"), *Path);
		return false;
	}
	Deck.Opponent = DAJson::ReadString(Object, TEXT("opponent"));
	Deck.Name = DAJson::ReadString(Object, TEXT("name"));
	Deck.Variant = DAJson::ReadString(Object, TEXT("variant"));
	Deck.Confidence = DAJson::ReadString(Object, TEXT("confidence"));
	Deck.Source = DAJson::ReadString(Object, TEXT("source"));
	Deck.Notes = DAJson::ReadString(Object, TEXT("notes"));
	DAJson::AppendIntArray(Object, TEXT("cards"), Deck.Cards);
	DAJson::AppendIntArray(Object, TEXT("extra"), Deck.Extra);
	DAJson::AppendIntArray(Object, TEXT("side"), Deck.Side);

	if (DeckIndex.Contains(Deck.Id))
	{
		OutError = FString::Printf(TEXT("Duplicate deck id '%s' in %s"), *Deck.Id, *Path);
		return false;
	}
	DeckIndex.Add(Deck.Id, DeckList.Num());
	DeckList.Add(MoveTemp(Deck));
	return true;
}

void UDAOpponentSubsystem::LoadDeckDirectory(const FString& Directory, TArray<FString>& OutWarnings)
{
	TArray<FString> Files;
	IFileManager::Get().FindFiles(Files, *FPaths::Combine(Directory, TEXT("*.json")), true, false);
	Files.Sort();
	for (const FString& File : Files)
	{
		FString Error;
		if (!LoadDeckFile(FPaths::Combine(Directory, File), Error))
		{
			OutWarnings.Add(Error);
		}
	}
}

void UDAOpponentSubsystem::LoadAIProfileDirectory(const FString& Directory, TArray<FString>& OutWarnings)
{
	TArray<FString> Files;
	IFileManager::Get().FindFiles(Files, *FPaths::Combine(Directory, TEXT("*.json")), true, false);
	Files.Sort();
	for (const FString& File : Files)
	{
		const FString Path = FPaths::Combine(Directory, File);
		TSharedPtr<FJsonValue> Root;
		FString Error;
		if (!DAJson::LoadFile(Path, Root, Error))
		{
			OutWarnings.Add(Error);
			continue;
		}
		const TSharedPtr<FJsonObject> Object = Root->AsObject();
		if (!Object.IsValid())
		{
			OutWarnings.Add(FString::Printf(TEXT("AI profile root is not an object: %s"), *Path));
			continue;
		}

		FDAIProfileDef Profile;
		Profile.Id = DAJson::ReadString(Object, TEXT("id"));
		if (Profile.Id.IsEmpty() || AIProfileIndex.Contains(Profile.Id))
		{
			OutWarnings.Add(FString::Printf(TEXT("AI profile missing/duplicate id: %s"), *Path));
			continue;
		}
		Profile.Label = DAJson::ReadString(Object, TEXT("label"));
		Profile.Strategy = DAJson::ReadString(Object, TEXT("strategy"));
		Profile.Difficulty = DAJson::ReadInt(Object, TEXT("difficulty"), 2);
		double Aggression = 0.7;
		Object->TryGetNumberField(TEXT("aggression"), Aggression);
		Profile.Aggression = static_cast<float>(Aggression);
		ReadNumberMap(Object, TEXT("weights"), Profile.Weights);
		ReadNumberMap(Object, TEXT("thresholds"), Profile.Thresholds);
		ReadBoolMap(Object, TEXT("thresholds"), Profile.BoolThresholds);
		DAJson::AppendStringArray(Object, TEXT("preferred_card_names"), Profile.PreferredCardNames);
		DAJson::AppendStringArray(Object, TEXT("avoid_card_names"), Profile.AvoidCardNames);
		Profile.Confidence = DAJson::ReadString(Object, TEXT("confidence"));
		Profile.Source = DAJson::ReadString(Object, TEXT("source"));
		Profile.Notes = DAJson::ReadString(Object, TEXT("notes"));

		AIProfileIndex.Add(Profile.Id, AIProfileList.Num());
		AIProfileList.Add(MoveTemp(Profile));
	}
}

const FDAOpponentDef* UDAOpponentSubsystem::FindOpponent(const FString& OpponentId) const
{
	if (const int32* Index = OpponentIndex.Find(OpponentId))
	{
		return Opponents.IsValidIndex(*Index) ? &Opponents[*Index] : nullptr;
	}
	return nullptr;
}

const FDAOpponentDeckDef* UDAOpponentSubsystem::FindDeck(const FString& DeckId) const
{
	if (const int32* Index = DeckIndex.Find(DeckId))
	{
		return DeckList.IsValidIndex(*Index) ? &DeckList[*Index] : nullptr;
	}
	return nullptr;
}

const FDAIProfileDef* UDAOpponentSubsystem::FindAIProfile(const FString& ProfileId) const
{
	if (const int32* Index = AIProfileIndex.Find(ProfileId))
	{
		return AIProfileList.IsValidIndex(*Index) ? &AIProfileList[*Index] : nullptr;
	}
	return nullptr;
}

bool UDAOpponentSubsystem::IsDuelistUnlocked(const FString& OpponentId, const FString& PlayerTitle,
	const FString& PlayerDorm, const TSet<FString>& Flags, int32 DayIndex, FString& OutReason) const
{
	OutReason.Reset();
	const FDAOpponentDef* Opponent = FindOpponent(OpponentId);
	if (!Opponent)
	{
		OutReason = FString::Printf(TEXT("Unknown duelist '%s'."), *OpponentId);
		return false;
	}
	if (!Opponent->Access.RequiresFlag.IsEmpty() && !Flags.Contains(Opponent->Access.RequiresFlag))
	{
		OutReason = FString::Printf(TEXT("Requires flag '%s'."), *Opponent->Access.RequiresFlag);
		return false;
	}
	if (!Opponent->Access.RequiresTitle.IsEmpty() && !PlayerTitle.Equals(Opponent->Access.RequiresTitle, ESearchCase::IgnoreCase))
	{
		OutReason = FString::Printf(TEXT("Requires title '%s'."), *Opponent->Access.RequiresTitle);
		return false;
	}
	if (!Opponent->Access.RequiresDorm.IsEmpty() && !PlayerDorm.Equals(Opponent->Access.RequiresDorm, ESearchCase::IgnoreCase))
	{
		OutReason = FString::Printf(TEXT("Requires dorm '%s'."), *Opponent->Access.RequiresDorm);
		return false;
	}
	if (Opponent->Access.MinDay > 0 && DayIndex < Opponent->Access.MinDay)
	{
		OutReason = FString::Printf(TEXT("Available from day %d."), Opponent->Access.MinDay);
		return false;
	}
	return true;
}

bool UDAOpponentSubsystem::CanDuelAtLocation(const FString& OpponentId, const FString& Zone,
	const FString& Interior, const FString& Weekday, const FString& Period, FString& OutReason) const
{
	OutReason.Reset();
	const FDAOpponentDef* Opponent = FindOpponent(OpponentId);
	if (!Opponent)
	{
		OutReason = FString::Printf(TEXT("Unknown duelist '%s'."), *OpponentId);
		return false;
	}
	if (Opponent->Schedule.Num() == 0)
	{
		return true;
	}
	for (const FDAOpponentScheduleSlot& Slot : Opponent->Schedule)
	{
		if (!Slot.Zone.Equals(Zone, ESearchCase::IgnoreCase))
		{
			continue;
		}
		if (!Slot.Interior.IsEmpty() && !Slot.Interior.Equals(Interior, ESearchCase::IgnoreCase))
		{
			continue;
		}
		if (Slot.Weekdays.Num() > 0 && !Slot.Weekdays.Contains(Weekday))
		{
			continue;
		}
		if (Slot.Periods.Num() > 0 && !Slot.Periods.Contains(Period))
		{
			continue;
		}
		return true;
	}
	OutReason = FString::Printf(TEXT("%s is not scheduled at %s/%s on %s %s."),
		*Opponent->Name, *Zone, *Interior, *Weekday, *Period);
	return false;
}

FString UDAOpponentSubsystem::ResolveDeckFor(const FString& OpponentId, const TMap<FString, int32>& Counters) const
{
	const FDAOpponentDef* Opponent = FindOpponent(OpponentId);
	if (!Opponent)
	{
		return FString();
	}
	FString Result = Opponent->DefaultDeck;
	int32 BestWins = -1;
	for (const FDAOpponentEvolutionRule& Rule : Opponent->EvolutionRules)
	{
		if (Rule.Deck.IsEmpty() || !FindDeck(Rule.Deck))
		{
			continue;
		}
		FString CounterKey = Rule.Counter;
		if (CounterKey.IsEmpty())
		{
			CounterKey = FString::Printf(TEXT("wins_%s"), *OpponentId);
		}
		const int32* Value = Counters.Find(CounterKey);
		const int32 Wins = Value ? *Value : 0;
		if (Wins >= Rule.AfterWins && Rule.AfterWins >= BestWins)
		{
			BestWins = Rule.AfterWins;
			Result = Rule.Deck;
		}
	}
	if (Result.IsEmpty() || !FindDeck(Result))
	{
		return Opponent->DefaultDeck;
	}
	return Result;
}

FDAOpponentDuelOutcome UDAOpponentSubsystem::RecordDuelResult(const FString& OpponentId, bool bPlayerWon, bool bDraw)
{
	FDAOpponentDuelOutcome Outcome;
	Outcome.OpponentId = OpponentId;
	Outcome.bPlayerWon = bPlayerWon;
	Outcome.bDraw = bDraw;

	if (!FindOpponent(OpponentId))
	{
		return Outcome;
	}

	if (bDraw)
	{
		RuntimeState.Draws.FindOrAdd(OpponentId)++;
	}
	else if (bPlayerWon)
	{
		RuntimeState.Wins.FindOrAdd(OpponentId)++;
	}
	else
	{
		RuntimeState.Losses.FindOrAdd(OpponentId)++;
	}

	Outcome.Wins = GetWins(OpponentId);
	Outcome.Losses = GetLosses(OpponentId);

	const FDAOpponentDef* Opponent = FindOpponent(OpponentId);
	int32 BestWins = -1;
	for (const FDAOpponentEvolutionRule& Rule : Opponent->EvolutionRules)
	{
		if (Outcome.Wins >= Rule.AfterWins && Rule.AfterWins >= BestWins && FindDeck(Rule.Deck))
		{
			BestWins = Rule.AfterWins;
			Outcome.EvolutionDeckId = Rule.Deck;
			Outcome.bEvolutionUnlocked = true;
		}
	}
	return Outcome;
}

int32 UDAOpponentSubsystem::GetWins(const FString& OpponentId) const
{
	const int32* Wins = RuntimeState.Wins.Find(OpponentId);
	return Wins ? *Wins : 0;
}

int32 UDAOpponentSubsystem::GetLosses(const FString& OpponentId) const
{
	const int32* Losses = RuntimeState.Losses.Find(OpponentId);
	return Losses ? *Losses : 0;
}

bool UDAOpponentSubsystem::IsEmailUnlocked(const FString& OpponentId, const FString& ThreadId) const
{
	const FDAOpponentEmailRuntime* State = RuntimeState.Emails.Find(OpponentId);
	return State && State->UnlockedThreads.Contains(ThreadId);
}

bool UDAOpponentSubsystem::UnlockEmail(const FString& OpponentId, const FString& ThreadId)
{
	const FDAOpponentDef* Opponent = FindOpponent(OpponentId);
	if (!Opponent)
	{
		return false;
	}
	const bool bKnownThread = Opponent->Email.Threads.ContainsByPredicate([&ThreadId](const FDAOpponentEmailThread& Thread)
	{
		return Thread.Id == ThreadId;
	});
	if (!bKnownThread)
	{
		return false;
	}
	FDAOpponentEmailRuntime& State = RuntimeState.Emails.FindOrAdd(OpponentId);
	State.bUnlocked = true;
	State.UnlockedThreads.AddUnique(ThreadId);
	return true;
}

bool UDAOpponentSubsystem::MarkEmailRead(const FString& OpponentId, const FString& ThreadId)
{
	FDAOpponentEmailRuntime* State = RuntimeState.Emails.Find(OpponentId);
	if (!State || !State->UnlockedThreads.Contains(ThreadId))
	{
		return false;
	}
	State->ReadThreads.AddUnique(ThreadId);
	return true;
}

bool UDAOpponentSubsystem::CanRequestDuel(const FString& OpponentId, int32 DayIndex, int32 PlayerWins, FString& OutReason) const
{
	OutReason.Reset();
	const FDAOpponentDef* Opponent = FindOpponent(OpponentId);
	if (!Opponent)
	{
		OutReason = FString::Printf(TEXT("Unknown duelist '%s'."), *OpponentId);
		return false;
	}
	if (Opponent->Role.Equals(TEXT("exam"), ESearchCase::IgnoreCase))
	{
		OutReason = TEXT("Exam opponents cannot be challenged from the PDA.");
		return false;
	}
	if (PlayerWins < Opponent->DuelRequest.MinWins)
	{
		OutReason = FString::Printf(TEXT("Requires %d total wins."), Opponent->DuelRequest.MinWins);
		return false;
	}
	if (RuntimeState.RequestDay == DayIndex)
	{
		const int32* Count = RuntimeState.RequestsToday.Find(OpponentId);
		if (Count && *Count >= Opponent->DuelRequest.MaxPerDay)
		{
			OutReason = TEXT("No more duel requests from this opponent today.");
			return false;
		}
	}
	return true;
}

bool UDAOpponentSubsystem::ConsumeDuelRequest(const FString& OpponentId, int32 DayIndex, int32 PlayerWins, FString& OutReason)
{
	if (RuntimeState.RequestDay != DayIndex)
	{
		ResetDailyRequests(DayIndex);
	}
	if (!CanRequestDuel(OpponentId, DayIndex, PlayerWins, OutReason))
	{
		return false;
	}
	RuntimeState.RequestsToday.FindOrAdd(OpponentId)++;
	return true;
}

void UDAOpponentSubsystem::ResetDailyRequests(int32 DayIndex)
{
	if (RuntimeState.RequestDay != DayIndex)
	{
		RuntimeState.RequestDay = DayIndex;
		RuntimeState.RequestsToday.Reset();
	}
}
