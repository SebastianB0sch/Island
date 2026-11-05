#include "DACardRecords.h"

#include "DuelAcademyIsland.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	FString CardReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		if (!Object.IsValid())
		{
			return FString();
		}
		const TSharedPtr<FJsonValue> Value = Object->TryGetField(Field);
		FString Text;
		if (!Value.IsValid() || Value->Type != EJson::String || !Value->TryGetString(Text))
		{
			return FString();
		}
		return Text;
	}

	int32 CardReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default = 0)
	{
		if (!Object.IsValid())
		{
			return Default;
		}
		// Require a real JSON number with an integral value in int32 range.
		// TryGetNumberField(int32) also accepts booleans (true -> 1) and rounds
		// fractional values, which would let malformed card rows through.
		const TSharedPtr<FJsonValue> Value = Object->TryGetField(Field);
		if (!Value.IsValid() || Value->Type != EJson::Number)
		{
			return Default;
		}
		double Number = 0.0;
		if (!Value->TryGetNumber(Number) || !FMath::IsFinite(Number)
			|| FMath::FloorToDouble(Number) != Number
			|| Number < static_cast<double>(TNumericLimits<int32>::Min())
			|| Number > static_cast<double>(TNumericLimits<int32>::Max()))
		{
			return Default;
		}
		return static_cast<int32>(Number);
	}

	int32 CardReadIntArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<int32>& Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (!Object.IsValid() || !Object->TryGetArrayField(Field, Values))
		{
			return 0;
		}
		int32 Skipped = 0;
		for (const TSharedPtr<FJsonValue>& Value : *Values)
		{
			double Number = 0.0;
			if (!Value.IsValid() || Value->Type != EJson::Number
				|| !Value->TryGetNumber(Number) || !FMath::IsFinite(Number)
				|| Number < 1.0 || Number > static_cast<double>(TNumericLimits<int32>::Max())
				|| FMath::FloorToDouble(Number) != Number)
			{
				++Skipped;
				continue;
			}
			Out.Add(static_cast<int32>(Number));
		}
		return Skipped;
	}

	int32 CardReadStringArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<FString>& Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (!Object.IsValid() || !Object->TryGetArrayField(Field, Values))
		{
			return 0;
		}
		int32 Skipped = 0;
		for (const TSharedPtr<FJsonValue>& Value : *Values)
		{
			FString Text;
			if (!Value.IsValid() || Value->Type != EJson::String || !Value->TryGetString(Text))
			{
				++Skipped;
				continue;
			}
			Text.TrimStartAndEndInline();
			if (Text.IsEmpty())
			{
				++Skipped;
				continue;
			}
			Out.Add(MoveTemp(Text));
		}
		return Skipped;
	}
}

void UCardDatabaseSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	const FString ContentDir = FPaths::ProjectContentDir();
	LoadCards(FPaths::Combine(ContentDir, TEXT("Data/cards.json")));
	LoadDecks(FPaths::Combine(ContentDir, TEXT("Data/decks.json")));
	LoadFusions(FPaths::Combine(ContentDir, TEXT("Data/fusions.json")));
}

void UCardDatabaseSubsystem::LoadCards(const FString& Path)
{
	// A failed or repeated load must not leave records from an earlier file.
	CardsById.Reset();
	LoadError.Reset();
	bLoaded = false;

	FString Raw;
	if (!FFileHelper::LoadFileToString(Raw, *Path))
	{
		LoadError = FString::Printf(TEXT("Card database not found at %s"), *Path);
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("%s"), *LoadError);
		return;
	}

	TSharedPtr<FJsonValue> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		LoadError = TEXT("Card database JSON could not be parsed.");
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("%s"), *LoadError);
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
	if (!Root->TryGetArray(Entries))
	{
		LoadError = TEXT("Card database root must be an array.");
		return;
	}

	int32 SkippedEntries = 0;
	int32 DuplicateEntries = 0;
	for (const TSharedPtr<FJsonValue>& Entry : *Entries)
	{
		const TSharedPtr<FJsonObject> Object = Entry.IsValid() ? Entry->AsObject() : nullptr;
		if (!Object.IsValid())
		{
			++SkippedEntries;
			continue;
		}
		FCardRecord Card;
		Card.Id = CardReadInt(Object, TEXT("id"));
		Card.Name = CardReadString(Object, TEXT("name"));
		Card.CardType = CardReadString(Object, TEXT("card_type"));
		Card.MonsterType = CardReadString(Object, TEXT("monster_type"));
		Card.Subtype = CardReadString(Object, TEXT("subtype"));
		Card.Attribute = CardReadString(Object, TEXT("attribute"));
		Card.Level = CardReadInt(Object, TEXT("level"));
		Card.Atk = CardReadInt(Object, TEXT("atk"));
		Card.Def = CardReadInt(Object, TEXT("def"));
		Card.Description = CardReadString(Object, TEXT("description"));
		if (Card.Id <= 0 || Card.Name.IsEmpty() || Card.CardType.IsEmpty())
		{
			++SkippedEntries;
			continue;
		}
		if (CardsById.Contains(Card.Id))
		{
			++DuplicateEntries;
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Duplicate card id %d; the later record replaces the earlier one."), Card.Id);
		}
		CardsById.Add(Card.Id, MoveTemp(Card));
	}

	bLoaded = CardsById.Num() > 0;
	if (!bLoaded)
	{
		LoadError = TEXT("Card database contains no valid card records.");
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("%s"), *LoadError);
		return;
	}
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Loaded %d cards for the duel database (%d skipped, %d duplicate ids)."),
		CardsById.Num(), SkippedEntries, DuplicateEntries);
}

void UCardDatabaseSubsystem::LoadDecks(const FString& Path)
{
	Decks.Reset();

	FString Raw;
	if (!FFileHelper::LoadFileToString(Raw, *Path))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Starter deck JSON not found at %s"), *Path);
		return;
	}

	TSharedPtr<FJsonValue> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Starter deck JSON could not be parsed."));
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
	if (!Root->TryGetArray(Entries))
	{
		return;
	}

	int32 SkippedEntries = 0;
	int32 DuplicateEntries = 0;
	for (const TSharedPtr<FJsonValue>& Entry : *Entries)
	{
		const TSharedPtr<FJsonObject> Object = Entry.IsValid() ? Entry->AsObject() : nullptr;
		if (!Object.IsValid())
		{
			++SkippedEntries;
			continue;
		}

		FStarterDeckDef Deck;
		Deck.Id = CardReadString(Object, TEXT("id")).TrimStartAndEnd();
		Deck.Name = CardReadString(Object, TEXT("name"));
		Deck.Subtitle = CardReadString(Object, TEXT("subtitle"));
		Deck.Description = CardReadString(Object, TEXT("description"));
		Deck.Accent = CardReadString(Object, TEXT("accent"));
		const int32 SkippedCards = CardReadIntArray(Object, TEXT("cards"), Deck.Cards)
			+ CardReadIntArray(Object, TEXT("extra"), Deck.Extra);
		if (SkippedCards > 0)
		{
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("Deck '%s' ignored %d malformed card id(s)."), *Deck.Id, SkippedCards);
		}

		if (Deck.Id.IsEmpty() || Deck.Cards.Num() == 0)
		{
			++SkippedEntries;
			continue;
		}
		if (Decks.ContainsByPredicate([&Deck](const FStarterDeckDef& Existing)
			{
				return Existing.Id.Equals(Deck.Id, ESearchCase::IgnoreCase);
			}))
		{
			++DuplicateEntries;
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("Duplicate deck id '%s'; the first decklist wins."), *Deck.Id);
			continue;
		}
		Decks.Add(MoveTemp(Deck));
	}

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Loaded %d decklists (%d skipped, %d duplicate ids)."),
		Decks.Num(), SkippedEntries, DuplicateEntries);
}

void UCardDatabaseSubsystem::LoadFusions(const FString& Path)
{
	Fusions.Reset();

	FString Raw;
	if (!FFileHelper::LoadFileToString(Raw, *Path))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Fusion recipe JSON not found at %s"), *Path);
		return;
	}

	TSharedPtr<FJsonValue> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Fusion recipe JSON could not be parsed."));
		return;
	}

	const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
	if (!Root->TryGetArray(Entries))
	{
		return;
	}

	int32 SkippedEntries = 0;
	for (const TSharedPtr<FJsonValue>& Entry : *Entries)
	{
		const TSharedPtr<FJsonObject> Object = Entry.IsValid() ? Entry->AsObject() : nullptr;
		if (!Object.IsValid())
		{
			++SkippedEntries;
			continue;
		}

		FFusionRecipeDef Recipe;
		Recipe.Result = CardReadInt(Object, TEXT("result"));
		Recipe.Name = CardReadString(Object, TEXT("name"));
		Recipe.MaterialsType = CardReadString(Object, TEXT("materialsType"));
		Recipe.AnyCount = FMath::Max(0, CardReadInt(Object, TEXT("anyCount")));
		const int32 SkippedMaterials = CardReadIntArray(Object, TEXT("materials"), Recipe.Materials)
			+ CardReadStringArray(Object, TEXT("fusionTypes"), Recipe.FusionTypes);
		if (SkippedMaterials > 0)
		{
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("Fusion recipe for card %d ignored %d malformed field(s)."),
				Recipe.Result, SkippedMaterials);
		}

		if (Recipe.Result > 0 && (Recipe.Materials.Num() > 0 || Recipe.AnyCount > 0))
		{
			Fusions.Add(MoveTemp(Recipe));
		}
		else
		{
			++SkippedEntries;
		}
	}

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Loaded %d fusion recipes (%d skipped)."),
		Fusions.Num(), SkippedEntries);
}

const FCardRecord* UCardDatabaseSubsystem::FindCard(int32 CardId) const
{
	return CardsById.Find(CardId);
}

const FStarterDeckDef* UCardDatabaseSubsystem::FindDeck(const FString& DeckId) const
{
	if (const FStarterDeckDef* Starter = Decks.FindByPredicate([&DeckId](const FStarterDeckDef& Deck)
	{
		return Deck.Id.Equals(DeckId, ESearchCase::IgnoreCase);
	}))
	{
		return Starter;
	}
	return RegisteredDecks.FindByPredicate([&DeckId](const FStarterDeckDef& Deck)
	{
		return Deck.Id.Equals(DeckId, ESearchCase::IgnoreCase);
	});
}

bool UCardDatabaseSubsystem::RegisterDeck(const FStarterDeckDef& Deck)
{
	const FString DeckId = Deck.Id.TrimStartAndEnd();
	if (DeckId.IsEmpty() || Deck.Cards.Num() == 0)
	{
		return false;
	}
	for (const int32 CardId : Deck.Cards)
	{
		if (CardId <= 0)
		{
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("RegisterDeck('%s') contains invalid card id %d and was ignored."), *DeckId, CardId);
			return false;
		}
	}
	for (const int32 CardId : Deck.Extra)
	{
		if (CardId <= 0)
		{
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("RegisterDeck('%s') contains invalid Extra card id %d and was ignored."), *DeckId, CardId);
			return false;
		}
	}
	if (Decks.ContainsByPredicate([&DeckId](const FStarterDeckDef& Starter)
		{
			return Starter.Id.Equals(DeckId, ESearchCase::IgnoreCase);
		}))
	{
		// FindDeck resolves starters first, so registering a colliding id would
		// be a silent no-op.  Refuse it instead of pretending it succeeded.
		UE_LOG(LogDuelAcademyIsland, Warning,
			TEXT("RegisterDeck('%s') collides with a starter deck and was ignored."), *DeckId);
		return false;
	}
	for (FStarterDeckDef& Existing : RegisteredDecks)
	{
		if (Existing.Id.Equals(DeckId, ESearchCase::IgnoreCase))
		{
			Existing = Deck;
			Existing.Id = DeckId;
			return true;
		}
	}
	FStarterDeckDef Registered = Deck;
	Registered.Id = DeckId;
	RegisteredDecks.Add(MoveTemp(Registered));
	return true;
}
