// Duel Academy Island - opponent roster/deck/AI loader.

#include "DAOpponentSubsystem.h"

#include "DuelAcademyIsland.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	FString OppReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		FString Value;
		if (Object.IsValid())
		{
			Object->TryGetStringField(Field, Value);
		}
		return Value;
	}

	int32 OppReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default = 0)
	{
		int32 Value = Default;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return Value;
	}

	bool OppReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, bool bDefault = false)
	{
		bool bValue = bDefault;
		if (Object.IsValid())
		{
			Object->TryGetBoolField(Field, bValue);
		}
		return bValue;
	}

	void ReadStringArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<FString>& Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (Object.IsValid() && Object->TryGetArrayField(Field, Values))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Values)
			{
				if (Value.IsValid())
				{
					Out.Add(Value->AsString());
				}
			}
		}
	}

	void ReadIntArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<int32>& Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (Object.IsValid() && Object->TryGetArrayField(Field, Values))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Values)
			{
				if (Value.IsValid())
				{
					Out.Add(static_cast<int32>(Value->AsNumber()));
				}
			}
		}
	}

	TSharedPtr<FJsonObject> ReadObject(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		const TSharedPtr<FJsonObject>* Found = nullptr;
		if (Object.IsValid() && Object->TryGetObjectField(Field, Found) && Found && Found->IsValid())
		{
			return *Found;
		}
		return nullptr;
	}

	void ReadNumberMap(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TMap<FString, float>& Out)
	{
		const TSharedPtr<FJsonObject> MapObject = ReadObject(Object, Field);
		if (!MapObject.IsValid())
		{
			return;
		}
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : MapObject->Values)
		{
			if (Pair.Value.IsValid() && Pair.Value->Type == EJson::Number)
			{
				Out.Add(Pair.Key, static_cast<float>(Pair.Value->AsNumber()));
			}
		}
	}

	void ReadBoolMap(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TMap<FString, bool>& Out)
	{
		const TSharedPtr<FJsonObject> MapObject = ReadObject(Object, Field);
		if (!MapObject.IsValid())
		{
			return;
		}
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : MapObject->Values)
		{
			if (Pair.Value.IsValid() && Pair.Value->Type == EJson::Boolean)
			{
				Out.Add(Pair.Key, Pair.Value->AsBool());
			}
		}
	}

	bool LoadJson(const FString& Path, TSharedPtr<FJsonValue>& OutRoot, FString& OutError)
	{
		FString Raw;
		if (!FFileHelper::LoadFileToString(Raw, *Path))
		{
			OutError = FString::Printf(TEXT("File not found: %s"), *Path);
			return false;
		}
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
		if (!FJsonSerializer::Deserialize(Reader, OutRoot) || !OutRoot.IsValid())
		{
			OutError = FString::Printf(TEXT("JSON parse failed: %s"), *Path);
			return false;
		}
		return true;
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
	if (!LoadJson(Path, Root, OutError))
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
		Duelist.Id = OppReadString(Object, TEXT("id"));
		if (Duelist.Id.IsEmpty())
		{
			continue;
		}
		Duelist.Name = OppReadString(Object, TEXT("name"));
		ReadStringArray(Object, TEXT("aliases"), Duelist.Aliases);
		Duelist.Role = OppReadString(Object, TEXT("role"));
		Duelist.Rank = OppReadInt(Object, TEXT("rank"));
		Duelist.Dorm = OppReadString(Object, TEXT("dorm"));
		Duelist.Year = OppReadInt(Object, TEXT("year"), 1);
		Duelist.Title = OppReadString(Object, TEXT("title"));
		Duelist.AIProfile = OppReadString(Object, TEXT("ai_profile"));
		ReadStringArray(Object, TEXT("decks"), Duelist.Decks);
		ReadIntArray(Object, TEXT("signature_card_ids"), Duelist.SignatureCardIds);
		ReadStringArray(Object, TEXT("signature_cards"), Duelist.SignatureCards);
		ReadIntArray(Object, TEXT("canon_gift_card_ids"), Duelist.CanonGiftCardIds);
		Duelist.CanonSource = OppReadString(Object, TEXT("canon_source"));
		Duelist.CanonConfidence = OppReadString(Object, TEXT("canon_confidence"));
		Duelist.DefaultDeck = OppReadString(Object, TEXT("default_deck"));
		ReadIntArray(Object, TEXT("ante"), Duelist.Ante);
		Duelist.Confidence = OppReadString(Object, TEXT("confidence"));
		Duelist.Source = OppReadString(Object, TEXT("source"));
		Duelist.Notes = OppReadString(Object, TEXT("notes"));

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
				Rule.Id = OppReadString(EvolutionObject, TEXT("id"));
				Rule.AfterWins = OppReadInt(EvolutionObject, TEXT("after_wins"), 1);
				Rule.Counter = OppReadString(EvolutionObject, TEXT("counter"));
				Rule.Deck = OppReadString(EvolutionObject, TEXT("deck"));
				Rule.Description = OppReadString(EvolutionObject, TEXT("description"));
				Rule.Confidence = OppReadString(EvolutionObject, TEXT("confidence"));
				Rule.Source = OppReadString(EvolutionObject, TEXT("source"));
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
				Location.Zone = OppReadString(LocationObject, TEXT("zone"));
				Location.Interior = OppReadString(LocationObject, TEXT("interior"));
				Location.Name = OppReadString(LocationObject, TEXT("name"));
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
				ReadStringArray(ScheduleObject, TEXT("weekdays"), Slot.Weekdays);
				ReadStringArray(ScheduleObject, TEXT("periods"), Slot.Periods);
				Slot.Zone = OppReadString(ScheduleObject, TEXT("zone"));
				Slot.Interior = OppReadString(ScheduleObject, TEXT("interior"));
				Duelist.Schedule.Add(MoveTemp(Slot));
			}
		}

		if (const TSharedPtr<FJsonObject> AccessObject = ReadObject(Object, TEXT("access")))
		{
			Duelist.Access.RequiresFlag = OppReadString(AccessObject, TEXT("requires_flag"));
			Duelist.Access.RequiresTitle = OppReadString(AccessObject, TEXT("requires_title"));
			Duelist.Access.RequiresDorm = OppReadString(AccessObject, TEXT("requires_dorm"));
			Duelist.Access.bEventOnly = OppReadBool(AccessObject, TEXT("event_only"));
			Duelist.Access.MinDay = OppReadInt(AccessObject, TEXT("min_day"));
		}

		if (const TSharedPtr<FJsonObject> EmailObject = ReadObject(Object, TEXT("email")))
		{
			Duelist.Email.UnlockFlag = OppReadString(EmailObject, TEXT("unlock_flag"));
			Duelist.Email.Address = OppReadString(EmailObject, TEXT("address"));
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
					Thread.Id = OppReadString(ThreadObject, TEXT("id"));
					Thread.Subject = OppReadString(ThreadObject, TEXT("subject"));
					Thread.UnlockFlag = OppReadString(ThreadObject, TEXT("unlock_flag"));
					Duelist.Email.Threads.Add(MoveTemp(Thread));
				}
			}
		}

		if (const TSharedPtr<FJsonObject> RequestObject = ReadObject(Object, TEXT("duel_request")))
		{
			Duelist.DuelRequest.UnlockFlag = OppReadString(RequestObject, TEXT("unlock_flag"));
			Duelist.DuelRequest.MinWins = OppReadInt(RequestObject, TEXT("min_wins"));
			Duelist.DuelRequest.CooldownDays = OppReadInt(RequestObject, TEXT("cooldown_days"), 1);
			Duelist.DuelRequest.MaxPerDay = OppReadInt(RequestObject, TEXT("max_per_day"), 1);
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
				Gift.Id = OppReadString(GiftObject, TEXT("id"));
				Gift.Type = OppReadString(GiftObject, TEXT("type"));
				Gift.Amount = OppReadInt(GiftObject, TEXT("amount"));
				Gift.CardId = OppReadInt(GiftObject, TEXT("card_id"));
				Gift.Event = OppReadString(GiftObject, TEXT("event"));
				Gift.Confidence = OppReadString(GiftObject, TEXT("confidence"));
				Gift.Source = OppReadString(GiftObject, TEXT("source"));
				Duelist.Gifts.Add(MoveTemp(Gift));
			}
		}

		if (const TSharedPtr<FJsonObject> WalkObject = ReadObject(Object, TEXT("walk_home")))
		{
			Duelist.WalkHome.bEnabled = OppReadBool(WalkObject, TEXT("enabled"));
			Duelist.WalkHome.Zone = OppReadString(WalkObject, TEXT("zone"));
			ReadStringArray(WalkObject, TEXT("weekdays"), Duelist.WalkHome.Weekdays);
			Duelist.WalkHome.Period = OppReadString(WalkObject, TEXT("period"));
			Duelist.WalkHome.Flag = OppReadString(WalkObject, TEXT("flag"));
			Duelist.WalkHome.Confidence = OppReadString(WalkObject, TEXT("confidence"));
			Duelist.WalkHome.Source = OppReadString(WalkObject, TEXT("source"));
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
	if (!LoadJson(Path, Root, OutError))
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
	Deck.Id = OppReadString(Object, TEXT("id"));
	if (Deck.Id.IsEmpty())
	{
		OutError = FString::Printf(TEXT("Deck has no id: %s"), *Path);
		return false;
	}
	Deck.Opponent = OppReadString(Object, TEXT("opponent"));
	Deck.Name = OppReadString(Object, TEXT("name"));
	Deck.Variant = OppReadString(Object, TEXT("variant"));
	Deck.Confidence = OppReadString(Object, TEXT("confidence"));
	Deck.Source = OppReadString(Object, TEXT("source"));
	Deck.Notes = OppReadString(Object, TEXT("notes"));
	ReadIntArray(Object, TEXT("cards"), Deck.Cards);
	ReadIntArray(Object, TEXT("extra"), Deck.Extra);
	ReadIntArray(Object, TEXT("side"), Deck.Side);

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
		if (!LoadJson(Path, Root, Error))
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
		Profile.Id = OppReadString(Object, TEXT("id"));
		if (Profile.Id.IsEmpty() || AIProfileIndex.Contains(Profile.Id))
		{
			OutWarnings.Add(FString::Printf(TEXT("AI profile missing/duplicate id: %s"), *Path));
			continue;
		}
		Profile.Label = OppReadString(Object, TEXT("label"));
		Profile.Strategy = OppReadString(Object, TEXT("strategy"));
		Profile.Difficulty = OppReadInt(Object, TEXT("difficulty"), 2);
		double Aggression = 0.7;
		Object->TryGetNumberField(TEXT("aggression"), Aggression);
		Profile.Aggression = static_cast<float>(Aggression);
		ReadNumberMap(Object, TEXT("weights"), Profile.Weights);
		ReadNumberMap(Object, TEXT("thresholds"), Profile.Thresholds);
		ReadBoolMap(Object, TEXT("thresholds"), Profile.BoolThresholds);
		ReadStringArray(Object, TEXT("preferred_card_names"), Profile.PreferredCardNames);
		ReadStringArray(Object, TEXT("avoid_card_names"), Profile.AvoidCardNames);
		Profile.Confidence = OppReadString(Object, TEXT("confidence"));
		Profile.Source = OppReadString(Object, TEXT("source"));
		Profile.Notes = OppReadString(Object, TEXT("notes"));

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

bool UDAOpponentSubsystem::GetDeckCards(const FString& DeckId, TArray<int32>& OutMain, TArray<int32>& OutExtra) const
{
	const FDAOpponentDeckDef* Deck = FindDeck(DeckId);
	if (!Deck)
	{
		OutMain.Reset();
		OutExtra.Reset();
		return false;
	}
	OutMain = Deck->Cards;
	OutExtra = Deck->Extra;
	return true;
}

TArray<FString> UDAOpponentSubsystem::GetDuelistIds() const
{
	TArray<FString> Ids;
	Ids.Reserve(Opponents.Num());
	for (const FDAOpponentDef& Opponent : Opponents)
	{
		Ids.Add(Opponent.Id);
	}
	return Ids;
}

TArray<FString> UDAOpponentSubsystem::GetDeckIds() const
{
	TArray<FString> Ids;
	Ids.Reserve(DeckList.Num());
	for (const FDAOpponentDeckDef& Deck : DeckList)
	{
		Ids.Add(Deck.Id);
	}
	return Ids;
}

TArray<const FDAOpponentDef*> UDAOpponentSubsystem::GetDuelistsByRank() const
{
	TArray<const FDAOpponentDef*> Result;
	Result.Reserve(Opponents.Num());
	for (const FDAOpponentDef& Opponent : Opponents)
	{
		Result.Add(&Opponent);
	}
	Result.Sort([](const FDAOpponentDef& A, const FDAOpponentDef& B)
	{
		const bool bARanked = A.Role.Equals(TEXT("ranked"), ESearchCase::IgnoreCase) && A.Rank > 0;
		const bool bBRanked = B.Role.Equals(TEXT("ranked"), ESearchCase::IgnoreCase) && B.Rank > 0;
		if (bARanked != bBRanked)
		{
			return bARanked;
		}
		if (A.Rank != B.Rank)
		{
			return A.Rank < B.Rank;
		}
		return A.Id < B.Id;
	});
	return Result;
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
