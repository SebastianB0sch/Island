#include "DADeckLogic.h"

#include "DAEconomyJson.h"
#include "DAInventorySubsystem.h"
#include "DACardRecords.h"
#include "DuelAcademyIsland.h"

#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "HAL/PlatformTime.h"
#include "Misc/Paths.h"
#include "Serialization/JsonWriter.h"

namespace
{
	const TCHAR* RulesPath()
	{
		return TEXT("Data/Rules/banned_limited.json");
	}

	const TCHAR* PlayerDecksPath()
	{
		return TEXT("Data/Decks/player_decks.json");
	}

	bool ParseCardIdArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<int32>& OutCards)
	{
		const TArray<int32> Values = DAEconomyJson::ReadIntArray(Object, Field);
		for (const int32 CardId : Values)
		{
			if (CardId > 0)
			{
				OutCards.Add(CardId);
			}
		}
		return OutCards.Num() > 0;
	}

	bool ParseDeckObject(const TSharedPtr<FJsonObject>& Object, FDAEDeck& OutDeck)
	{
		if (!Object.IsValid())
		{
			return false;
		}
		OutDeck = FDAEDeck();
		OutDeck.Id = DAEconomyJson::ReadString(Object, TEXT("id"));
		OutDeck.Name = DAEconomyJson::ReadString(Object, TEXT("name"));
		OutDeck.bStarter = DAEconomyJson::ReadBool(Object, TEXT("bStarter"), DAEconomyJson::ReadBool(Object, TEXT("is_starter")));
		OutDeck.bPlayerDeck = true;
		ParseCardIdArray(Object, TEXT("main"), OutDeck.Main);
		ParseCardIdArray(Object, TEXT("extra"), OutDeck.Extra);
		return !OutDeck.Id.IsEmpty();
	}

	void AddDeckError(TArray<FDAEDeckError>& Errors, const TCHAR* Code, const FString& Message, int32 CardId = 0)
	{
		FDAEDeckError Error;
		Error.Code = FName(Code);
		Error.Message = Message;
		Error.CardId = CardId;
		Errors.Add(Error);
	}

	FString CopyLimitMessage(int32 Limit)
	{
		switch (Limit)
		{
		case 1: return TEXT("This card is limited to 1 copy.");
		case 2: return TEXT("This card is limited to 2 copies.");
		default:
			return FString::Printf(TEXT("You cannot have more than %d copies of the same card in your Deck."), Limit);
		}
	}
}

void UDADeckLogic::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	FString Error;
	if (!LoadRules(Error))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("DeckLogic: %s (using default rules)"), *Error);
	}
	if (!LoadPlayerDeckFile(Error))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("DeckLogic: %s (falling back to decks.json)"), *Error);
		if (!LoadDefaultDeckFallback(Error))
		{
			LoadError = Error;
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("DeckLogic: %s"), *LoadError);
			return;
		}
	}

	bLoaded = PlayerDecks.Num() > 0;

	if (UGameInstance* GI = GetGameInstance())
	{
		if (UDAProfileSubsystem* Profile = GI->GetSubsystem<UDAProfileSubsystem>())
		{
			Profile->SetDeckProvider(this);
		}
		if (UDASaveSubsystem* Save = GI->GetSubsystem<UDASaveSubsystem>())
		{
			Save->RegisterPayloadProvider(this);
		}
	}

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("DeckLogic: loaded %d player decks (active '%s')."), PlayerDecks.Num(), *ActiveDeckId);
}

TArray<FString> UDADeckLogic::GetDeckIds() const
{
	TArray<FString> Ids;
	Ids.Reserve(PlayerDecks.Num());
	for (const FDAEDeck& Deck : PlayerDecks)
	{
		Ids.Add(Deck.Id);
	}
	return Ids;
}

void UDADeckLogic::SetActiveDeckId(const FString& DeckId)
{
	if (FindPlayerDeck(DeckId))
	{
		ActiveDeckId = DeckId;
	}
	else if (PlayerDecks.Num() > 0)
	{
		ActiveDeckId = PlayerDecks[0].Id;
	}
	OnDecksChanged.Broadcast(ActiveDeckId);
}

bool UDADeckLogic::WriteSaveSection(TSharedPtr<FJsonObject>& OutSection) const
{
	if (!OutSection.IsValid())
	{
		OutSection = MakeShared<FJsonObject>();
	}
	OutSection->SetNumberField(TEXT("version"), 1);
	OutSection->SetStringField(TEXT("active_deck_id"), ActiveDeckId);

	TArray<TSharedPtr<FJsonValue>> Decks;
	for (const FDAEDeck& Deck : PlayerDecks)
	{
		const TSharedPtr<FJsonObject> Entry = MakeShared<FJsonObject>();
		Entry->SetStringField(TEXT("id"), Deck.Id);
		Entry->SetStringField(TEXT("name"), Deck.Name);
		Entry->SetArrayField(TEXT("main"), DAEconomyJson::IntArrayToJson(Deck.Main));
		Entry->SetArrayField(TEXT("extra"), DAEconomyJson::IntArrayToJson(Deck.Extra));
		Entry->SetBoolField(TEXT("bStarter"), Deck.bStarter);
		Entry->SetBoolField(TEXT("bPlayerDeck"), Deck.bPlayerDeck);
		Decks.Add(MakeShared<FJsonValueObject>(Entry));
	}
	OutSection->SetArrayField(TEXT("decks"), Decks);
	return true;
}

bool UDADeckLogic::ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError)
{
	if (!InSection.IsValid())
	{
		OutError = TEXT("Deck save section is missing.");
		return false;
	}
	return ImportStateJson(DAEconomyJson::WriteObject(InSection), OutError);
}

bool UDADeckLogic::LoadRules(FString& OutError)
{
	Rules = FDAEDeckRules();

	const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), RulesPath());
	TSharedPtr<FJsonValue> Root;
	if (!DAEconomyJson::LoadFile(Path, Root, OutError))
	{
		return false;
	}
	const TSharedPtr<FJsonObject> Object = Root->AsObject();
	if (!Object.IsValid())
	{
		OutError = TEXT("Deck rules JSON root must be an object.");
		return false;
	}

	const TSharedPtr<FJsonObject>* RulesObject = nullptr;
	const TSharedPtr<FJsonObject>& Source = (Object->TryGetObjectField(TEXT("rules"), RulesObject) && RulesObject && RulesObject->IsValid())
		? *RulesObject
		: Object;

	Rules.MinMain = FMath::Max(0, DAEconomyJson::ReadInt(Source, TEXT("min_main"), Rules.MinMain));
	Rules.MaxMain = FMath::Max(Rules.MinMain, DAEconomyJson::ReadInt(Source, TEXT("max_main"), Rules.MaxMain));
	Rules.MaxExtra = FMath::Max(0, DAEconomyJson::ReadInt(Source, TEXT("max_extra"), Rules.MaxExtra));
	Rules.MaxCopies = FMath::Max(1, DAEconomyJson::ReadInt(Source, TEXT("max_copies"), Rules.MaxCopies));
	Rules.MaxSide = FMath::Max(0, DAEconomyJson::ReadInt(Source, TEXT("max_side"), Rules.MaxSide));
	Rules.MaxPlayerDecks = FMath::Max(1, DAEconomyJson::ReadInt(Source, TEXT("max_player_decks"), Rules.MaxPlayerDecks));
	Rules.DeckNameMinLength = FMath::Max(0, DAEconomyJson::ReadInt(Source, TEXT("deck_name_min_length"), Rules.DeckNameMinLength));
	Rules.DeckNameMaxLength = FMath::Max(Rules.DeckNameMinLength, DAEconomyJson::ReadInt(Source, TEXT("deck_name_max_length"), Rules.DeckNameMaxLength));
	MaxPlayerDecks = Rules.MaxPlayerDecks;

	auto ReadCardList = [](const TArray<TSharedPtr<FJsonValue>>* Array, TSet<int32>& OutSet)
	{
		if (!Array)
		{
			return;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Array)
		{
			if (!Value.IsValid())
			{
				continue;
			}
			if (Value->Type == EJson::Number)
			{
				const int32 CardId = static_cast<int32>(Value->AsNumber());
				if (CardId > 0)
				{
					OutSet.Add(CardId);
				}
			}
			else if (Value->Type == EJson::Object)
			{
				const TSharedPtr<FJsonObject> Entry = Value->AsObject();
				const int32 CardId = DAEconomyJson::ReadInt(Entry, TEXT("card_id"));
				if (CardId > 0)
				{
					OutSet.Add(CardId);
				}
			}
		}
	};

	auto ReadLimitedList = [](const TArray<TSharedPtr<FJsonValue>>* Array, TMap<int32, int32>& OutMap, int32 DefaultLimit)
	{
		if (!Array)
		{
			return;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Array)
		{
			if (!Value.IsValid())
			{
				continue;
			}
			if (Value->Type == EJson::Number)
			{
				const int32 CardId = static_cast<int32>(Value->AsNumber());
				if (CardId > 0)
				{
					OutMap.Add(CardId, DefaultLimit);
				}
			}
			else if (Value->Type == EJson::Object)
			{
				const TSharedPtr<FJsonObject> Entry = Value->AsObject();
				const int32 CardId = DAEconomyJson::ReadInt(Entry, TEXT("card_id"));
				const int32 Limit = DAEconomyJson::ReadInt(Entry, TEXT("limit"), DefaultLimit);
				if (CardId > 0)
				{
					OutMap.Add(CardId, FMath::Max(0, Limit));
				}
			}
		}
	};

	const TArray<TSharedPtr<FJsonValue>>* Banned = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* Limited = nullptr;
	const TArray<TSharedPtr<FJsonValue>>* SemiLimited = nullptr;
	Object->TryGetArrayField(TEXT("banned"), Banned);
	Object->TryGetArrayField(TEXT("limited"), Limited);
	Object->TryGetArrayField(TEXT("semi_limited"), SemiLimited);
	ReadCardList(Banned, Rules.Banned);
	ReadLimitedList(Limited, Rules.Limited, 1);
	ReadLimitedList(SemiLimited, Rules.SemiLimited, 2);

	return true;
}

bool UDADeckLogic::LoadPlayerDeckFile(FString& OutError)
{
	const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), PlayerDecksPath());
	TSharedPtr<FJsonValue> Root;
	if (!DAEconomyJson::LoadFile(Path, Root, OutError))
	{
		return false;
	}
	const TSharedPtr<FJsonObject> Object = Root->AsObject();
	if (!Object.IsValid())
	{
		OutError = TEXT("Player deck JSON root must be an object.");
		return false;
	}

	PlayerDecks.Reset();
	DefaultStarterCards.Reset();

	const TArray<TSharedPtr<FJsonValue>>* DeckArray = nullptr;
	if (!Object->TryGetArrayField(TEXT("decks"), DeckArray) || !DeckArray)
	{
		OutError = TEXT("Player deck JSON has no decks array.");
		return false;
	}

	TSet<FString> SeenIds;
	for (const TSharedPtr<FJsonValue>& Value : *DeckArray)
	{
		const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
		FDAEDeck Deck;
		if (!ParseDeckObject(Entry, Deck) || SeenIds.Contains(Deck.Id))
		{
			continue;
		}
		SeenIds.Add(Deck.Id);
		PlayerDecks.Add(MoveTemp(Deck));
	}

	if (PlayerDecks.Num() == 0)
	{
		OutError = TEXT("Player deck JSON produced no valid decks.");
		return false;
	}

	MaxPlayerDecks = FMath::Max(MaxPlayerDecks, DAEconomyJson::ReadInt(Object, TEXT("max_player_decks"), MaxPlayerDecks));
	DefaultStarterCards = DAEconomyJson::ReadIntArray(Object, TEXT("starter_cards"));
	if (DefaultStarterCards.Num() == 0)
	{
		// Keep duplicate copies: a 40-card starter deck can legitimately contain
		// two copies of the same card, and the grant must own both.
		for (const FDAEDeck& Deck : PlayerDecks)
		{
			DefaultStarterCards.Append(Deck.Main);
			DefaultStarterCards.Append(Deck.Extra);
		}
		DefaultStarterCards.Sort();
	}

	ActiveDeckId = DAEconomyJson::ReadString(Object, TEXT("default_deck_id"));
	if (!FindPlayerDeck(ActiveDeckId))
	{
		ActiveDeckId = PlayerDecks[0].Id;
	}
	return true;
}

bool UDADeckLogic::LoadDefaultDeckFallback(FString& OutError)
{
	UGameInstance* GI = GetGameInstance();
	UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	if (!Database || Database->GetDecks().Num() == 0)
	{
		OutError = TEXT("No player decks and no starter decks in decks.json.");
		return false;
	}

	const FStarterDeckDef* Starter = Database->FindDeck(TEXT("fire"));
	if (!Starter)
	{
		Starter = &Database->GetDecks()[0];
	}

	PlayerDecks.Reset();
	FDAEDeck Deck;
	Deck.Id = TEXT("player_1");
	Deck.Name = TEXT("My Deck");
	Deck.Main = Starter->Cards;
	Deck.Extra = Starter->Extra;
	Deck.bPlayerDeck = true;
	PlayerDecks.Add(MoveTemp(Deck));

	DefaultStarterCards = PlayerDecks[0].Main;
	DefaultStarterCards.Append(PlayerDecks[0].Extra);
	DefaultStarterCards.Sort();
	ActiveDeckId = PlayerDecks[0].Id;
	return true;
}

void UDADeckLogic::SeedDefaultPlayerDecks()
{
	FString Error;
	if (!LoadPlayerDeckFile(Error))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("DeckLogic: %s (falling back to decks.json)"), *Error);
		if (!LoadDefaultDeckFallback(Error))
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("DeckLogic: %s"), *Error);
		}
	}
	OnDecksChanged.Broadcast(ActiveDeckId);
}

void UDADeckLogic::ResetToDefaults()
{
	FString Error;
	LoadRules(Error);
	if (!LoadPlayerDeckFile(Error) && !LoadDefaultDeckFallback(Error))
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("DeckLogic reset failed: %s"), *Error);
	}
	OnDecksChanged.Broadcast(ActiveDeckId);
}

const FDAEDeck* UDADeckLogic::FindPlayerDeck(const FString& DeckId) const
{
	return PlayerDecks.FindByPredicate([&DeckId](const FDAEDeck& Deck)
	{
		return Deck.Id.Equals(DeckId, ESearchCase::IgnoreCase);
	});
}

FDAEDeck* UDADeckLogic::FindMutable(const FString& DeckId)
{
	return PlayerDecks.FindByPredicate([&DeckId](const FDAEDeck& Deck)
	{
		return Deck.Id.Equals(DeckId, ESearchCase::IgnoreCase);
	});
}

bool UDADeckLogic::GetPlayerDeck(const FString& DeckId, FDAEDeck& OutDeck) const
{
	if (const FDAEDeck* Deck = FindPlayerDeck(DeckId))
	{
		OutDeck = *Deck;
		return true;
	}
	return false;
}

const FDAEDeck* UDADeckLogic::GetActiveDeck() const
{
	if (const FDAEDeck* Deck = FindPlayerDeck(ActiveDeckId))
	{
		return Deck;
	}
	return PlayerDecks.Num() > 0 ? &PlayerDecks[0] : nullptr;
}

FString UDADeckLogic::MakeDeckId() const
{
	for (int32 Index = 1; Index < 10000; ++Index)
	{
		const FString Candidate = FString::Printf(TEXT("player_%d"), Index);
		if (!FindPlayerDeck(Candidate))
		{
			return Candidate;
		}
	}
	return FString::Printf(TEXT("player_%u"), FPlatformTime::Cycles());
}

bool UDADeckLogic::ValidateDeckName(const FString& Name, FString& OutError) const
{
	const FString Trimmed = Name.TrimStartAndEnd();
	if (Trimmed.Len() < Rules.DeckNameMinLength)
	{
		OutError = TEXT("Please enter a name for your Deck.");
		return false;
	}
	if (Trimmed.Len() > Rules.DeckNameMaxLength)
	{
		OutError = FString::Printf(TEXT("That Deck name is too long (maximum %d characters)."), Rules.DeckNameMaxLength);
		return false;
	}
	if (Trimmed.Contains(TEXT("\n")) || Trimmed.Contains(TEXT("\r")) || Trimmed.Contains(TEXT("\t")))
	{
		OutError = TEXT("That Deck name contains invalid characters.");
		return false;
	}
	return true;
}

bool UDADeckLogic::CardBelongsInExtra(int32 CardId) const
{
	UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	const FCardRecord* Card = Database ? Database->FindCard(CardId) : nullptr;
	return Card && Card->CardType.Contains(TEXT("Fusion"));
}

bool UDADeckLogic::ValidateDeckAgainstRules(
	const FDAEDeck& Deck,
	const FDAEDeckRules& InRules,
	const UCardDatabaseSubsystem* Database,
	const UDAInventorySubsystem* Inventory,
	bool bCheckOwnership,
	TArray<FDAEDeckError>& OutErrors)
{
	OutErrors.Reset();

	if (Deck.Main.Num() < InRules.MinMain)
	{
		AddDeckError(OutErrors, TEXT("main_too_small"),
			FString::Printf(TEXT("Your Main Deck must contain at least %d cards."), InRules.MinMain));
	}
	if (Deck.Main.Num() > InRules.MaxMain)
	{
		AddDeckError(OutErrors, TEXT("main_too_large"),
			FString::Printf(TEXT("Your Main Deck cannot contain more than %d cards."), InRules.MaxMain));
	}
	if (Deck.Extra.Num() > InRules.MaxExtra)
	{
		AddDeckError(OutErrors, TEXT("extra_too_large"),
			FString::Printf(TEXT("Your Fusion Deck cannot contain more than %d cards."), InRules.MaxExtra));
	}

	if (!Database)
	{
		AddDeckError(OutErrors, TEXT("database_unavailable"), TEXT("The card database is not loaded."));
		return false;
	}

	TMap<int32, int32> Copies;
	auto CountCard = [&Copies](int32 CardId) { Copies.FindOrAdd(CardId)++; };

	for (const int32 CardId : Deck.Main)
	{
		if (CardId <= 0)
		{
			AddDeckError(OutErrors, TEXT("unknown_card"), TEXT("This card is not in the card database."), CardId);
			continue;
		}
		const FCardRecord* Card = Database->FindCard(CardId);
		if (!Card)
		{
			AddDeckError(OutErrors, TEXT("unknown_card"), TEXT("This card is not in the card database."), CardId);
			continue;
		}
		if (Card->CardType.Contains(TEXT("Fusion")))
		{
			AddDeckError(OutErrors, TEXT("fusion_in_main"), TEXT("Fusion Monsters cannot be placed in the Main Deck."), CardId);
		}
		CountCard(CardId);
	}
	for (const int32 CardId : Deck.Extra)
	{
		if (CardId <= 0)
		{
			AddDeckError(OutErrors, TEXT("unknown_card"), TEXT("This card is not in the card database."), CardId);
			continue;
		}
		const FCardRecord* Card = Database->FindCard(CardId);
		if (!Card)
		{
			AddDeckError(OutErrors, TEXT("unknown_card"), TEXT("This card is not in the card database."), CardId);
			continue;
		}
		if (!Card->CardType.Contains(TEXT("Fusion")))
		{
			AddDeckError(OutErrors, TEXT("invalid_extra_card"), TEXT("Only Fusion Monsters can be placed in the Fusion Deck."), CardId);
		}
		CountCard(CardId);
	}

	for (const TPair<int32, int32>& Pair : Copies)
	{
		const int32 CardId = Pair.Key;
		const int32 Count = Pair.Value;
		if (InRules.Banned.Contains(CardId))
		{
			AddDeckError(OutErrors, TEXT("banned_card"), TEXT("This card is forbidden and cannot be used in your Deck."), CardId);
			continue;
		}
		const int32 Limit = InRules.GetCopyLimit(CardId);
		if (Limit <= 0)
		{
			AddDeckError(OutErrors, TEXT("banned_card"), TEXT("This card is forbidden and cannot be used in your Deck."), CardId);
			continue;
		}
		if (Count > Limit)
		{
			const bool bLimited = InRules.Limited.Contains(CardId) || InRules.SemiLimited.Contains(CardId);
			AddDeckError(OutErrors, bLimited ? TEXT("limited_card") : TEXT("copy_limit"), CopyLimitMessage(Limit), CardId);
		}
		if (bCheckOwnership && Inventory)
		{
			const int32 Owned = Inventory->GetCount(CardId);
			if (Owned < Count)
			{
				AddDeckError(OutErrors, TEXT("not_owned"),
					Owned == 0 ? TEXT("You do not own this card.") : TEXT("You do not own enough copies of this card."), CardId);
			}
		}
	}
	return OutErrors.Num() == 0;
}

bool UDADeckLogic::ValidateDeck(const FDAEDeck& Deck, TArray<FDAEDeckError>& OutErrors) const
{
	UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	const UDAInventorySubsystem* Inventory = GI ? GI->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	ValidateDeckAgainstRules(Deck, Rules, Database, Inventory, true, OutErrors);
	return OutErrors.Num() == 0;
}

bool UDADeckLogic::ValidateDeckWithoutOwnership(const FDAEDeck& Deck, TArray<FDAEDeckError>& OutErrors) const
{
	UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	ValidateDeckAgainstRules(Deck, Rules, Database, nullptr, false, OutErrors);
	return OutErrors.Num() == 0;
}

TArray<FDAEDeckError> UDADeckLogic::GetDeckErrors(const FDAEDeck& Deck) const
{
	TArray<FDAEDeckError> Errors;
	ValidateDeck(Deck, Errors);
	return Errors;
}

bool UDADeckLogic::IsDeckLegal(const FDAEDeck& Deck) const
{
	TArray<FDAEDeckError> Errors;
	return ValidateDeck(Deck, Errors);
}

FString UDADeckLogic::GetDeckValidationMessage(const FDAEDeck& Deck) const
{
	TArray<FDAEDeckError> Errors;
	ValidateDeck(Deck, Errors);
	return Errors.Num() > 0 ? Errors[0].Message : FString();
}

bool UDADeckLogic::CanUseCard(const FDAEDeck& Deck, int32 CardId, bool bExtra, FString& OutError) const
{
	UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	const UDAInventorySubsystem* Inventory = GI ? GI->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	const FCardRecord* Card = Database ? Database->FindCard(CardId) : nullptr;
	if (!Card)
	{
		OutError = TEXT("This card is not in the card database.");
		return false;
	}

	const bool bIsFusion = Card->CardType.Contains(TEXT("Fusion"));
	if (bExtra && !bIsFusion)
	{
		OutError = TEXT("Only Fusion Monsters can be placed in the Fusion Deck.");
		return false;
	}
	if (!bExtra && bIsFusion)
	{
		OutError = TEXT("Fusion Monsters cannot be placed in the Main Deck.");
		return false;
	}

	int32 CurrentCopies = 0;
	for (const int32 Existing : Deck.Main) CurrentCopies += Existing == CardId ? 1 : 0;
	for (const int32 Existing : Deck.Extra) CurrentCopies += Existing == CardId ? 1 : 0;

	if (Rules.Banned.Contains(CardId))
	{
		OutError = TEXT("This card is forbidden and cannot be used in your Deck.");
		return false;
	}
	const int32 Limit = Rules.GetCopyLimit(CardId);
	if (CurrentCopies >= Limit)
	{
		OutError = (Rules.Limited.Contains(CardId) || Rules.SemiLimited.Contains(CardId))
			? CopyLimitMessage(Limit)
			: CopyLimitMessage(Rules.MaxCopies);
		return false;
	}

	if (bExtra && Deck.Extra.Num() >= Rules.MaxExtra)
	{
		OutError = FString::Printf(TEXT("Your Fusion Deck cannot contain more than %d cards."), Rules.MaxExtra);
		return false;
	}
	if (!bExtra && Deck.Main.Num() >= Rules.MaxMain)
	{
		OutError = FString::Printf(TEXT("Your Main Deck cannot contain more than %d cards."), Rules.MaxMain);
		return false;
	}

	if (Inventory && Inventory->GetCount(CardId) <= CurrentCopies)
	{
		OutError = TEXT("You do not own this card.");
		return false;
	}
	return true;
}

bool UDADeckLogic::AddCardToDeck(const FString& DeckId, int32 CardId, bool bExtra, FString& OutError)
{
	FDAEDeck* Deck = FindMutable(DeckId);
	if (!Deck)
	{
		OutError = TEXT("That Deck does not exist.");
		return false;
	}
	if (!CanUseCard(*Deck, CardId, bExtra, OutError))
	{
		return false;
	}
	(bExtra ? Deck->Extra : Deck->Main).Add(CardId);
	BroadcastChanged(DeckId);
	return true;
}

bool UDADeckLogic::AddCardToDeck(const FString& DeckId, int32 CardId, bool bExtra)
{
	FString Error;
	return AddCardToDeck(DeckId, CardId, bExtra, Error);
}

bool UDADeckLogic::RemoveCardFromDeck(const FString& DeckId, int32 CardId, bool bExtra, FString& OutError)
{
	FDAEDeck* Deck = FindMutable(DeckId);
	if (!Deck)
	{
		OutError = TEXT("That Deck does not exist.");
		return false;
	}
	TArray<int32>& Zone = bExtra ? Deck->Extra : Deck->Main;
	const int32 Index = Zone.FindLast(CardId);
	if (Index == INDEX_NONE)
	{
		OutError = TEXT("That card is not in your Deck.");
		return false;
	}
	Zone.RemoveAt(Index);
	BroadcastChanged(DeckId);
	return true;
}

bool UDADeckLogic::RemoveCardFromDeck(const FString& DeckId, int32 CardId, bool bExtra)
{
	FString Error;
	return RemoveCardFromDeck(DeckId, CardId, bExtra, Error);
}

bool UDADeckLogic::SwapCardInDeck(const FString& DeckId, int32 OldCardId, int32 NewCardId, bool bExtra, FString& OutError)
{
	FDAEDeck* Deck = FindMutable(DeckId);
	if (!Deck)
	{
		OutError = TEXT("That Deck does not exist.");
		return false;
	}
	TArray<int32>& Zone = bExtra ? Deck->Extra : Deck->Main;
	const int32 Index = Zone.FindLast(OldCardId);
	if (Index == INDEX_NONE)
	{
		OutError = TEXT("That card is not in your Deck.");
		return false;
	}
	if (OldCardId == NewCardId)
	{
		return true;
	}

	FDAEDeck Temp = *Deck;
	TArray<int32>& TempZone = bExtra ? Temp.Extra : Temp.Main;
	TempZone.RemoveAt(Index);
	if (!CanUseCard(Temp, NewCardId, bExtra, OutError))
	{
		return false;
	}
	TempZone.Insert(NewCardId, Index);
	*Deck = MoveTemp(Temp);
	BroadcastChanged(DeckId);
	return true;
}

bool UDADeckLogic::RenameDeck(const FString& DeckId, const FString& NewName, FString& OutError)
{
	FDAEDeck* Deck = FindMutable(DeckId);
	if (!Deck)
	{
		OutError = TEXT("That Deck does not exist.");
		return false;
	}
	if (!ValidateDeckName(NewName, OutError))
	{
		return false;
	}
	Deck->Name = NewName.TrimStartAndEnd();
	BroadcastChanged(DeckId);
	return true;
}

FString UDADeckLogic::CreateDeck(const FString& Name, FString& OutError)
{
	if (PlayerDecks.Num() >= MaxPlayerDecks)
	{
		OutError = TEXT("You cannot create any more Decks.");
		return FString();
	}
	if (!ValidateDeckName(Name, OutError))
	{
		return FString();
	}
	FDAEDeck Deck;
	Deck.Id = MakeDeckId();
	Deck.Name = Name.TrimStartAndEnd();
	Deck.bPlayerDeck = true;
	const FString NewId = Deck.Id;
	PlayerDecks.Add(MoveTemp(Deck));
	BroadcastChanged(NewId);
	return NewId;
}

bool UDADeckLogic::CopyDeck(const FString& SourceDeckId, const FString& NewName, FString& OutNewDeckId, FString& OutError)
{
	OutNewDeckId.Reset();
	if (PlayerDecks.Num() >= MaxPlayerDecks)
	{
		OutError = TEXT("You cannot create any more Decks.");
		return false;
	}
	const FDAEDeck* Source = FindPlayerDeck(SourceDeckId);
	if (!Source)
	{
		OutError = TEXT("That Deck does not exist.");
		return false;
	}
	if (!ValidateDeckName(NewName, OutError))
	{
		return false;
	}

	FDAEDeck Copy = *Source;
	Copy.Id = MakeDeckId();
	Copy.Name = NewName.TrimStartAndEnd();
	Copy.bStarter = false;
	Copy.bPlayerDeck = true;
	OutNewDeckId = Copy.Id;
	PlayerDecks.Add(MoveTemp(Copy));
	BroadcastChanged(OutNewDeckId);
	return true;
}

bool UDADeckLogic::EraseDeck(const FString& DeckId, FString& OutError)
{
	if (PlayerDecks.Num() <= 1)
	{
		OutError = TEXT("You cannot erase your last Deck.");
		return false;
	}
	const int32 Index = PlayerDecks.IndexOfByPredicate([&DeckId](const FDAEDeck& Deck)
	{
		return Deck.Id.Equals(DeckId, ESearchCase::IgnoreCase);
	});
	if (Index == INDEX_NONE)
	{
		OutError = TEXT("That Deck does not exist.");
		return false;
	}
	const bool bWasActive = ActiveDeckId.Equals(DeckId, ESearchCase::IgnoreCase);
	PlayerDecks.RemoveAt(Index);
	if (bWasActive)
	{
		ActiveDeckId = PlayerDecks[0].Id;
	}
	BroadcastChanged(DeckId);
	return true;
}

bool UDADeckLogic::SetActiveDeck(const FString& DeckId, FString& OutError)
{
	const FDAEDeck* Deck = FindPlayerDeck(DeckId);
	if (!Deck)
	{
		OutError = TEXT("That Deck does not exist.");
		return false;
	}
	TArray<FDAEDeckError> Errors;
	if (!ValidateDeck(*Deck, Errors))
	{
		OutError = Errors.Num() > 0 ? Errors[0].Message : TEXT("That Deck is not legal.");
		return false;
	}
	ActiveDeckId = Deck->Id;
	BroadcastChanged(DeckId);
	return true;
}

TArray<FStarterDeckDef> UDADeckLogic::GetStarterDecks() const
{
	UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	return Database ? Database->GetDecks() : TArray<FStarterDeckDef>();
}

TArray<int32> UDADeckLogic::GetStarterDeckCards(const FString& StarterId) const
{
	UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	const FStarterDeckDef* Deck = Database ? Database->FindDeck(StarterId) : nullptr;
	if (!Deck)
	{
		return TArray<int32>();
	}
	TArray<int32> Cards = Deck->Cards;
	Cards.Append(Deck->Extra);
	return Cards;
}

bool UDADeckLogic::ImportStarterDeck(const FString& StarterId, const FString& NewName, FString& OutNewDeckId, FString& OutError)
{
	OutNewDeckId.Reset();
	if (PlayerDecks.Num() >= MaxPlayerDecks)
	{
		OutError = TEXT("You cannot create any more Decks.");
		return false;
	}
	UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	const FStarterDeckDef* Starter = Database ? Database->FindDeck(StarterId) : nullptr;
	if (!Starter)
	{
		OutError = TEXT("That starter Deck does not exist.");
		return false;
	}
	if (!ValidateDeckName(NewName, OutError))
	{
		return false;
	}

	FDAEDeck Deck;
	Deck.Id = MakeDeckId();
	Deck.Name = NewName.TrimStartAndEnd();
	Deck.Main = Starter->Cards;
	Deck.Extra = Starter->Extra;
	Deck.bStarter = true;
	Deck.bPlayerDeck = true;
	OutNewDeckId = Deck.Id;
	PlayerDecks.Add(MoveTemp(Deck));
	BroadcastChanged(OutNewDeckId);
	return true;
}

TArray<FFusionRecipeDef> UDADeckLogic::GetAvailableFusionRecipes() const
{
	UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	const UDAInventorySubsystem* Inventory = GI ? GI->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	if (!Database || !Inventory)
	{
		return TArray<FFusionRecipeDef>();
	}

	TArray<FFusionRecipeDef> Available;
	for (const FFusionRecipeDef& Recipe : Database->GetFusions())
	{
		if (Recipe.Materials.Num() == 0)
		{
			continue;
		}
		TMap<int32, int32> Needed;
		for (const int32 Material : Recipe.Materials)
		{
			Needed.FindOrAdd(Material)++;
		}
		bool bHasAll = true;
		for (const TPair<int32, int32>& Pair : Needed)
		{
			if (Inventory->GetCount(Pair.Key) < Pair.Value)
			{
				bHasAll = false;
				break;
			}
		}
		if (bHasAll)
		{
			Available.Add(Recipe);
		}
	}
	return Available;
}

TArray<int32> UDADeckLogic::SortCardIds(const TArray<int32>& CardIds, EDAECardSortKey SortKey, bool bDescending) const
{
	UGameInstance* GI = GetGameInstance();
	const UDAInventorySubsystem* Inventory = GI ? GI->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	if (Inventory)
	{
		return Inventory->SortCards(CardIds, SortKey, bDescending);
	}
	TArray<int32> Fallback = CardIds;
	Fallback.Sort();
	return Fallback;
}

TArray<int32> UDADeckLogic::FilterCardIds(const TArray<int32>& CardIds, const FDAECardFilter& Filter) const
{
	UGameInstance* GI = GetGameInstance();
	UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	UDAInventorySubsystem* Inventory = GI ? GI->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	if (!Database)
	{
		return TArray<int32>();
	}

	TArray<int32> Result;
	for (const int32 CardId : CardIds)
	{
		const FCardRecord* Card = Database->FindCard(CardId);
		if (!Card)
		{
			continue;
		}
		if (Filter.bOwnedOnly && Inventory && !Inventory->HasCard(CardId, 1))
		{
			continue;
		}
		if (!Filter.NameContains.IsEmpty() && !Card->Name.Contains(Filter.NameContains, ESearchCase::IgnoreCase))
		{
			continue;
		}
		if (Filter.bMonstersOnly && !Card->IsMonster()) continue;
		if (Filter.bSpellsOnly && !Card->IsSpell()) continue;
		if (Filter.bTrapsOnly && !Card->IsTrap()) continue;
		if (Filter.CardTypes.Num() > 0)
		{
			bool bTypeMatch = false;
			for (const FString& Type : Filter.CardTypes)
			{
				if (Card->CardType.Equals(Type, ESearchCase::IgnoreCase) ||
					Card->CardType.Contains(Type, ESearchCase::IgnoreCase) ||
					Card->Subtype.Equals(Type, ESearchCase::IgnoreCase))
				{
					bTypeMatch = true;
					break;
				}
			}
			if (!bTypeMatch) continue;
		}
		if (Filter.Attributes.Num() > 0)
		{
			bool bMatch = false;
			for (const FString& Attribute : Filter.Attributes)
			{
				if (Card->Attribute.Equals(Attribute, ESearchCase::IgnoreCase)) { bMatch = true; break; }
			}
			if (!bMatch) continue;
		}
		if (Filter.MonsterTypes.Num() > 0)
		{
			bool bMatch = false;
			for (const FString& MonsterType : Filter.MonsterTypes)
			{
				if (Card->MonsterType.Equals(MonsterType, ESearchCase::IgnoreCase) ||
					Card->MonsterType.Contains(MonsterType, ESearchCase::IgnoreCase)) { bMatch = true; break; }
			}
			if (!bMatch) continue;
		}
		if (Filter.Rarities.Num() > 0 && Inventory && !Filter.Rarities.Contains(Inventory->GetCardRarity(CardId)))
		{
			continue;
		}
		const bool bHasAtkFilter = Filter.MinAtk >= 0 || Filter.MaxAtk >= 0;
		const bool bHasLevelFilter = Filter.MinLevel >= 0 || Filter.MaxLevel >= 0;
		if ((bHasAtkFilter || bHasLevelFilter) && !Card->IsMonster())
		{
			continue;
		}
		if (Filter.MinAtk >= 0 && Card->Atk < Filter.MinAtk) continue;
		if (Filter.MaxAtk >= 0 && Card->Atk > Filter.MaxAtk) continue;
		if (Filter.MinLevel >= 0 && Card->Level < Filter.MinLevel) continue;
		if (Filter.MaxLevel >= 0 && Card->Level > Filter.MaxLevel) continue;
		Result.Add(CardId);
	}
	return Result;
}

TArray<int32> UDADeckLogic::GetCollectionView(const FDAECardFilter& Filter, EDAECardSortKey SortKey, bool bDescending) const
{
	UGameInstance* GI = GetGameInstance();
	UDAInventorySubsystem* Inventory = GI ? GI->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	if (!Inventory)
	{
		return TArray<int32>();
	}
	return SortCardIds(FilterCardIds(Inventory->GetCollectionCards(), Filter), SortKey, bDescending);
}

FDAEDeckSaveData UDADeckLogic::GetSaveData() const
{
	FDAEDeckSaveData Data;
	Data.Version = 1;
	Data.ActiveDeckId = ActiveDeckId;
	Data.Decks = PlayerDecks;
	return Data;
}

bool UDADeckLogic::ApplySaveData(const FDAEDeckSaveData& Data, FString& OutError)
{
	if (Data.Version < 0)
	{
		OutError = TEXT("Unknown deck save version.");
		return false;
	}
	if (Data.Decks.Num() == 0)
	{
		OutError = TEXT("Deck save contains no Decks.");
		return false;
	}
	if (Data.Decks.Num() > MaxPlayerDecks)
	{
		OutError = TEXT("Deck save contains too many Decks.");
		return false;
	}

	TSet<FString> SeenIds;
	TArray<FDAEDeck> NewDecks;
	for (const FDAEDeck& Source : Data.Decks)
	{
		if (Source.Id.IsEmpty() || SeenIds.Contains(Source.Id))
		{
			OutError = TEXT("Deck save contains an invalid or duplicate Deck id.");
			return false;
		}
		SeenIds.Add(Source.Id);
		FDAEDeck Deck = Source;
		Deck.bPlayerDeck = true;
		NewDecks.Add(MoveTemp(Deck));
	}

	PlayerDecks = MoveTemp(NewDecks);
	ActiveDeckId = SeenIds.Contains(Data.ActiveDeckId) ? Data.ActiveDeckId : PlayerDecks[0].Id;
	OnDecksChanged.Broadcast(ActiveDeckId);
	return true;
}

FString UDADeckLogic::ExportStateJson() const
{
	const TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetNumberField(TEXT("version"), 1);
	Root->SetStringField(TEXT("active_deck_id"), ActiveDeckId);

	TArray<TSharedPtr<FJsonValue>> Decks;
	for (const FDAEDeck& Deck : PlayerDecks)
	{
		const TSharedPtr<FJsonObject> Entry = MakeShared<FJsonObject>();
		Entry->SetStringField(TEXT("id"), Deck.Id);
		Entry->SetStringField(TEXT("name"), Deck.Name);
		Entry->SetArrayField(TEXT("main"), DAEconomyJson::IntArrayToJson(Deck.Main));
		Entry->SetArrayField(TEXT("extra"), DAEconomyJson::IntArrayToJson(Deck.Extra));
		Entry->SetBoolField(TEXT("bStarter"), Deck.bStarter);
		Entry->SetBoolField(TEXT("bPlayerDeck"), Deck.bPlayerDeck);
		Decks.Add(MakeShared<FJsonValueObject>(Entry));
	}
	Root->SetArrayField(TEXT("decks"), Decks);
	return DAEconomyJson::WriteObject(Root);
}

bool UDADeckLogic::ImportStateJson(const FString& Json, FString& OutError)
{
	TSharedPtr<FJsonValue> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid() || !Root->AsObject().IsValid())
	{
		OutError = TEXT("Deck JSON could not be parsed.");
		return false;
	}
	const TSharedPtr<FJsonObject> Object = Root->AsObject();

	const TArray<TSharedPtr<FJsonValue>>* DeckArray = nullptr;
	if (!Object->TryGetArrayField(TEXT("decks"), DeckArray) || !DeckArray || DeckArray->Num() == 0)
	{
		OutError = TEXT("Deck JSON has no decks.");
		return false;
	}
	if (DeckArray->Num() > MaxPlayerDecks)
	{
		OutError = TEXT("Deck JSON contains too many Decks.");
		return false;
	}

	TArray<FDAEDeck> NewDecks;
	TSet<FString> SeenIds;
	for (const TSharedPtr<FJsonValue>& Value : *DeckArray)
	{
		const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
		FDAEDeck Deck;
		if (!ParseDeckObject(Entry, Deck) || SeenIds.Contains(Deck.Id))
		{
			OutError = TEXT("Deck JSON contains an invalid or duplicate Deck.");
			return false;
		}
		SeenIds.Add(Deck.Id);
		NewDecks.Add(MoveTemp(Deck));
	}

	PlayerDecks = MoveTemp(NewDecks);
	const FString Active = DAEconomyJson::ReadString(Object, TEXT("active_deck_id"));
	ActiveDeckId = SeenIds.Contains(Active) ? Active : PlayerDecks[0].Id;
	OnDecksChanged.Broadcast(ActiveDeckId);
	return true;
}

void UDADeckLogic::BroadcastChanged(const FString& DeckId)
{
	OnDecksChanged.Broadcast(DeckId);
}
