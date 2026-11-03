#include "DACardRecords.h"

#include "DuelAcademyIsland.h"
#include "DAJson.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

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

	for (const TSharedPtr<FJsonValue>& Entry : *Entries)
	{
		const TSharedPtr<FJsonObject> Object = Entry.IsValid() ? Entry->AsObject() : nullptr;
		if (!Object.IsValid())
		{
			continue;
		}
		FCardRecord Card;
		Card.Id = DAJson::ReadInt(Object, TEXT("id"));
		Card.Name = DAJson::ReadString(Object, TEXT("name"));
		Card.CardType = DAJson::ReadString(Object, TEXT("card_type"));
		Card.MonsterType = DAJson::ReadString(Object, TEXT("monster_type"));
		Card.Subtype = DAJson::ReadString(Object, TEXT("subtype"));
		Card.Attribute = DAJson::ReadString(Object, TEXT("attribute"));
		Card.Level = DAJson::ReadInt(Object, TEXT("level"));
		Card.Atk = DAJson::ReadInt(Object, TEXT("atk"));
		Card.Def = DAJson::ReadInt(Object, TEXT("def"));
		Card.Description = DAJson::ReadString(Object, TEXT("description"));
		if (Card.Id > 0)
		{
			CardsById.Add(Card.Id, MoveTemp(Card));
		}
	}

	bLoaded = CardsById.Num() > 0;
	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Loaded %d cards for the duel database."), CardsById.Num());
}

void UCardDatabaseSubsystem::LoadDecks(const FString& Path)
{
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

	for (const TSharedPtr<FJsonValue>& Entry : *Entries)
	{
		const TSharedPtr<FJsonObject> Object = Entry.IsValid() ? Entry->AsObject() : nullptr;
		if (!Object.IsValid())
		{
			continue;
		}

		FStarterDeckDef Deck;
		Deck.Id = DAJson::ReadString(Object, TEXT("id"));
		Deck.Name = DAJson::ReadString(Object, TEXT("name"));
		Deck.Subtitle = DAJson::ReadString(Object, TEXT("subtitle"));
		Deck.Description = DAJson::ReadString(Object, TEXT("description"));
		Deck.Accent = DAJson::ReadString(Object, TEXT("accent"));

		DAJson::AppendIntArray(Object, TEXT("cards"), Deck.Cards);
		DAJson::AppendIntArray(Object, TEXT("extra"), Deck.Extra);

		if (!Deck.Id.IsEmpty() && Deck.Cards.Num() > 0)
		{
			Decks.Add(MoveTemp(Deck));
		}
	}

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Loaded %d decklists."), Decks.Num());
}

void UCardDatabaseSubsystem::LoadFusions(const FString& Path)
{
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

	for (const TSharedPtr<FJsonValue>& Entry : *Entries)
	{
		const TSharedPtr<FJsonObject> Object = Entry.IsValid() ? Entry->AsObject() : nullptr;
		if (!Object.IsValid())
		{
			continue;
		}

		FFusionRecipeDef Recipe;
		Recipe.Result = DAJson::ReadInt(Object, TEXT("result"));
		Recipe.Name = DAJson::ReadString(Object, TEXT("name"));
		Recipe.MaterialsType = DAJson::ReadString(Object, TEXT("materialsType"));
		Recipe.AnyCount = DAJson::ReadInt(Object, TEXT("anyCount"));

		DAJson::AppendIntArray(Object, TEXT("materials"), Recipe.Materials);
		DAJson::AppendStringArray(Object, TEXT("fusionTypes"), Recipe.FusionTypes);

		if (Recipe.Result > 0 && (Recipe.Materials.Num() > 0 || Recipe.AnyCount > 0))
		{
			Fusions.Add(MoveTemp(Recipe));
		}
	}

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Loaded %d fusion recipes."), Fusions.Num());
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
	if (Deck.Id.IsEmpty() || Deck.Cards.Num() == 0)
	{
		return false;
	}
	for (FStarterDeckDef& Existing : RegisteredDecks)
	{
		if (Existing.Id.Equals(Deck.Id, ESearchCase::IgnoreCase))
		{
			Existing = Deck;
			return true;
		}
	}
	RegisteredDecks.Add(Deck);
	return true;
}
