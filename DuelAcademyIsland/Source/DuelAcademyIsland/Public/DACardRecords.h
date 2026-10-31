// Duel Academy Island - the duel card database (cards, starter decks, fusion recipes).

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DACardRecords.generated.h"

USTRUCT(BlueprintType)
struct FCardRecord
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Card")
	int32 Id = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Card")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "Card")
	FString CardType;

	UPROPERTY(BlueprintReadOnly, Category = "Card")
	FString MonsterType;

	UPROPERTY(BlueprintReadOnly, Category = "Card")
	FString Subtype;

	UPROPERTY(BlueprintReadOnly, Category = "Card")
	FString Attribute;

	UPROPERTY(BlueprintReadOnly, Category = "Card")
	int32 Level = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Card")
	int32 Atk = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Card")
	int32 Def = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Card")
	FString Description;

	bool IsMonster() const { return CardType.Contains(TEXT("Monster")); }
	bool IsSpell() const { return CardType == TEXT("Spell"); }
	bool IsTrap() const { return CardType == TEXT("Trap"); }
};

USTRUCT(BlueprintType)
struct FStarterDeckDef
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Deck")
	FString Id;

	UPROPERTY(BlueprintReadOnly, Category = "Deck")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "Deck")
	FString Subtitle;

	UPROPERTY(BlueprintReadOnly, Category = "Deck")
	FString Description;

	UPROPERTY(BlueprintReadOnly, Category = "Deck")
	FString Accent;

	UPROPERTY(BlueprintReadOnly, Category = "Deck")
	TArray<int32> Cards;

	UPROPERTY(BlueprintReadOnly, Category = "Deck")
	TArray<int32> Extra;
};

USTRUCT(BlueprintType)
struct FFusionRecipeDef
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Fusion")
	int32 Result = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Fusion")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "Fusion")
	TArray<int32> Materials;

	UPROPERTY(BlueprintReadOnly, Category = "Fusion")
	TArray<FString> FusionTypes;

	UPROPERTY(BlueprintReadOnly, Category = "Fusion")
	FString MaterialsType;

	UPROPERTY(BlueprintReadOnly, Category = "Fusion")
	int32 AnyCount = 0;
};

/**
 * Loads the JSON card database that ships in Content/Data: the full card list,
 * the starter deck lists and the fusion recipes. Everything is plain JSON so
 * the data can be edited without reimporting Unreal assets.
 */
UCLASS()
class DUELACADEMYISLAND_API UCardDatabaseSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	const FCardRecord* FindCard(int32 CardId) const;
	const FStarterDeckDef* FindDeck(const FString& DeckId) const;

	/**
	 * Narrow registration hook for A07 opponent decks.  Keeps the card database
	 * as the single deck-id resolver used by FDuelEngine::Start without making
	 * the A06 economy/deck-editor code learn the Opponents directory.
	 * Re-registering the same id replaces the previous entry.
	 */
	bool RegisterDeck(const FStarterDeckDef& Deck);

	const TMap<int32, FCardRecord>& GetCards() const { return CardsById; }
	const TArray<FStarterDeckDef>& GetDecks() const { return Decks; }
	const TArray<FFusionRecipeDef>& GetFusions() const { return Fusions; }
	int32 GetCardCount() const { return CardsById.Num(); }
	bool IsLoaded() const { return bLoaded; }
	const FString& GetLoadError() const { return LoadError; }

private:
	void LoadCards(const FString& Path);
	void LoadDecks(const FString& Path);
	void LoadFusions(const FString& Path);

	TMap<int32, FCardRecord> CardsById;
	TArray<FStarterDeckDef> Decks;
	/** Non-starter decks registered by A07; FindDeck resolves these but GetDecks() does not expose them as starters. */
	TArray<FStarterDeckDef> RegisteredDecks;
	TArray<FFusionRecipeDef> Fusions;
	bool bLoaded = false;
	FString LoadError;
};
