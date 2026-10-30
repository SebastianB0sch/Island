#include "DACardRecords.h"

#include "DuelAcademyIsland.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	FString ReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field)
	{
		FString Value;
		if (Object.IsValid())
		{
			Object->TryGetStringField(Field, Value);
		}
		return Value;
	}

	int32 ReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default = 0)
	{
		int32 Value = Default;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return Value;
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
		Card.Id = ReadInt(Object, TEXT("id"));
		Card.Name = ReadString(Object, TEXT("name"));
		Card.CardType = ReadString(Object, TEXT("card_type"));
		Card.MonsterType = ReadString(Object, TEXT("monster_type"));
		Card.Subtype = ReadString(Object, TEXT("subtype"));
		Card.Attribute = ReadString(Object, TEXT("attribute"));
		Card.Level = ReadInt(Object, TEXT("level"));
		Card.Atk = ReadInt(Object, TEXT("atk"));
		Card.Def = ReadInt(Object, TEXT("def"));
		Card.Description = ReadString(Object, TEXT("description"));
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
		Deck.Id = ReadString(Object, TEXT("id"));
		Deck.Name = ReadString(Object, TEXT("name"));
		Deck.Subtitle = ReadString(Object, TEXT("subtitle"));
		Deck.Description = ReadString(Object, TEXT("description"));
		Deck.Accent = ReadString(Object, TEXT("accent"));

		const TArray<TSharedPtr<FJsonValue>>* Cards = nullptr;
		if (Object->TryGetArrayField(TEXT("cards"), Cards))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Cards)
			{
				Deck.Cards.Add(static_cast<int32>(Value->AsNumber()));
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* Extra = nullptr;
		if (Object->TryGetArrayField(TEXT("extra"), Extra))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Extra)
			{
				Deck.Extra.Add(static_cast<int32>(Value->AsNumber()));
			}
		}

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
		Recipe.Result = ReadInt(Object, TEXT("result"));
		Recipe.Name = ReadString(Object, TEXT("name"));
		Recipe.MaterialsType = ReadString(Object, TEXT("materialsType"));
		Recipe.AnyCount = ReadInt(Object, TEXT("anyCount"));

		const TArray<TSharedPtr<FJsonValue>>* Materials = nullptr;
		if (Object->TryGetArrayField(TEXT("materials"), Materials))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Materials)
			{
				Recipe.Materials.Add(static_cast<int32>(Value->AsNumber()));
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* FusionTypes = nullptr;
		if (Object->TryGetArrayField(TEXT("fusionTypes"), FusionTypes))
		{
			for (const TSharedPtr<FJsonValue>& Value : *FusionTypes)
			{
				Recipe.FusionTypes.Add(Value->AsString());
			}
		}

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
	return Decks.FindByPredicate([&DeckId](const FStarterDeckDef& Deck)
	{
		return Deck.Id.Equals(DeckId, ESearchCase::IgnoreCase);
	});
}
