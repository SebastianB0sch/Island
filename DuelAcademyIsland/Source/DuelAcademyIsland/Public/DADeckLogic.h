// Duel Academy Island - deck construction / validation logic.
//
// Owns the player's deck slots, the 40-60 main / 20 extra / 3-copy / banned &
// limited rules, sorting/filtering views, starter decks and the deck save
// payload. It never mutates the duel engine or the UI.

#pragma once

#include "CoreMinimal.h"
#include "DAEconomyTypes.h"
#include "DACardRecords.h"
#include "DAProfileSubsystem.h"
#include "DASaveGame.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DADeckLogic.generated.h"

class UCardDatabaseSubsystem;
class UDAInventorySubsystem;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FDAOnDecksChanged, const FString&, DeckId);

/** One player deck slot. Main = 40-60, Extra = 0-20. */
USTRUCT(BlueprintType)
struct FDAEDeck
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Deck")
	FString Id;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Deck")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Deck")
	TArray<int32> Main;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Deck")
	TArray<int32> Extra;

	/** True when this slot was imported from a starter deck recipe. */
	UPROPERTY(BlueprintReadOnly, Category = "Economy|Deck")
	bool bStarter = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Deck")
	bool bPlayerDeck = true;
};

/** One validation failure with a stable code + GBA-style message. */
USTRUCT(BlueprintType)
struct FDAEDeckError
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Deck")
	FName Code;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Deck")
	FString Message;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Deck")
	int32 CardId = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Deck")
	bool bFatal = true;
};

/** Data-driven deck rules. Loaded from Content/Data/Rules/banned_limited.json. */
struct FDAEDeckRules
{
	int32 MinMain = 40;
	int32 MaxMain = 60;
	int32 MaxExtra = 15;
	int32 MaxCopies = 3;
	int32 MaxSide = 0;
	int32 MaxPlayerDecks = 24;
	int32 DeckNameMinLength = 1;
	int32 DeckNameMaxLength = 24;

	TSet<int32> Banned;
	TMap<int32, int32> Limited;
	TMap<int32, int32> SemiLimited;

	int32 GetCopyLimit(int32 CardId) const
	{
		if (Banned.Contains(CardId))
		{
			return 0;
		}
		if (const int32* Limit = Limited.Find(CardId))
		{
			return FMath::Max(0, *Limit);
		}
		if (const int32* Limit = SemiLimited.Find(CardId))
		{
			return FMath::Max(0, *Limit);
		}
		return MaxCopies;
	}
};

/** Save-friendly deck payload. A02 embeds this in the profile save. */
USTRUCT(BlueprintType)
struct FDAEDeckSaveData
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	int32 Version = 1;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	FString ActiveDeckId;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	TArray<FDAEDeck> Decks;
};

UCLASS()
class DUELACADEMYISLAND_API UDADeckLogic : public UGameInstanceSubsystem, public IDASavePayloadProvider, public IDAProfileDeckInterface
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	// ------------------------------------------------ A02 save/profile interfaces
	virtual FString GetSaveSectionName() const override { return TEXT("decks"); }
	virtual bool WriteSaveSection(TSharedPtr<FJsonObject>& OutSection) const override;
	virtual bool ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError) override;
	virtual TArray<FString> GetDeckIds() const override;
	virtual void SetActiveDeckId(const FString& DeckId) override;

	// ------------------------------------------------------------ rules / slots

	const FDAEDeckRules& GetRules() const { return Rules; }

	UFUNCTION(BlueprintPure, Category = "Economy|Deck")
	int32 GetMaxPlayerDecks() const { return MaxPlayerDecks; }

	UFUNCTION(BlueprintPure, Category = "Economy|Deck")
	TArray<FDAEDeck> GetPlayerDecks() const { return PlayerDecks; }

	/** C++ accessor; use GetPlayerDecks for Blueprint. */
	const TArray<FDAEDeck>& GetPlayerDecksRef() const { return PlayerDecks; }

	UFUNCTION(BlueprintPure, Category = "Economy|Deck")
	bool GetPlayerDeck(const FString& DeckId, FDAEDeck& OutDeck) const;

	const FDAEDeck* FindPlayerDeck(const FString& DeckId) const;

	UFUNCTION(BlueprintPure, Category = "Economy|Deck")
	FString GetActiveDeckId() const override { return ActiveDeckId; }

	const FDAEDeck* GetActiveDeck() const;

	// ------------------------------------------------------------ validation

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	bool ValidateDeck(const FDAEDeck& Deck, TArray<FDAEDeckError>& OutErrors) const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	TArray<FDAEDeckError> GetDeckErrors(const FDAEDeck& Deck) const;

	UFUNCTION(BlueprintPure, Category = "Economy|Deck")
	bool IsDeckLegal(const FDAEDeck& Deck) const;

	UFUNCTION(BlueprintPure, Category = "Economy|Deck")
	FString GetDeckValidationMessage(const FDAEDeck& Deck) const;

	/** Opponent/starter validation: same size/copy/banned rules, no ownership check. */
	bool ValidateDeckWithoutOwnership(const FDAEDeck& Deck, TArray<FDAEDeckError>& OutErrors) const;

	/** Shared rule core for A04 and the self-test. */
	static bool ValidateDeckAgainstRules(
		const FDAEDeck& Deck,
		const FDAEDeckRules& InRules,
		const UCardDatabaseSubsystem* Database,
		const UDAInventorySubsystem* Inventory,
		bool bCheckOwnership,
		TArray<FDAEDeckError>& OutErrors);

	// ------------------------------------------------------------ editing

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	bool AddCardToDeck(const FString& DeckId, int32 CardId, bool bExtra, FString& OutError);

	bool AddCardToDeck(const FString& DeckId, int32 CardId, bool bExtra);

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	bool RemoveCardFromDeck(const FString& DeckId, int32 CardId, bool bExtra, FString& OutError);

	bool RemoveCardFromDeck(const FString& DeckId, int32 CardId, bool bExtra);

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	bool SwapCardInDeck(const FString& DeckId, int32 OldCardId, int32 NewCardId, bool bExtra, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	bool RenameDeck(const FString& DeckId, const FString& NewName, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	FString CreateDeck(const FString& Name, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	bool CopyDeck(const FString& SourceDeckId, const FString& NewName, FString& OutNewDeckId, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	bool EraseDeck(const FString& DeckId, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	bool SetActiveDeck(const FString& DeckId, FString& OutError);

	// ------------------------------------------------------------ starters / recipes

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	TArray<FStarterDeckDef> GetStarterDecks() const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	TArray<int32> GetStarterDeckCards(const FString& StarterId) const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	bool ImportStarterDeck(const FString& StarterId, const FString& NewName, FString& OutNewDeckId, FString& OutError);

	UFUNCTION(BlueprintPure, Category = "Economy|Deck")
	TArray<int32> GetDefaultStarterCards() const { return DefaultStarterCards; }

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	TArray<FFusionRecipeDef> GetAvailableFusionRecipes() const;

	// ------------------------------------------------------------ collection views

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	TArray<int32> SortCardIds(const TArray<int32>& CardIds, EDAECardSortKey SortKey, bool bDescending = false) const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	TArray<int32> FilterCardIds(const TArray<int32>& CardIds, const FDAECardFilter& Filter) const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	TArray<int32> GetCollectionView(const FDAECardFilter& Filter, EDAECardSortKey SortKey, bool bDescending = false) const;

	// ------------------------------------------------------------ save / lifecycle

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	FString ExportStateJson() const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	bool ImportStateJson(const FString& Json, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	FDAEDeckSaveData GetSaveData() const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	bool ApplySaveData(const FDAEDeckSaveData& Data, FString& OutError);

	/** Load Content/Data/Decks/player_decks.json (new-game defaults). */
	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	void SeedDefaultPlayerDecks();

	UFUNCTION(BlueprintCallable, Category = "Economy|Deck")
	void ResetToDefaults();

	UPROPERTY(BlueprintAssignable, Category = "Economy|Deck")
	FDAOnDecksChanged OnDecksChanged;

private:
	bool LoadRules(FString& OutError);
	bool LoadPlayerDeckFile(FString& OutError);
	bool LoadDefaultDeckFallback(FString& OutError);
	FDAEDeck* FindMutable(const FString& DeckId);
	FString MakeDeckId() const;
	bool ValidateDeckName(const FString& Name, FString& OutError) const;
	bool CardBelongsInExtra(int32 CardId) const;
	bool CanUseCard(const FDAEDeck& Deck, int32 CardId, bool bExtra, FString& OutError) const;
	void BroadcastChanged(const FString& DeckId);

	TArray<FDAEDeck> PlayerDecks;
	FString ActiveDeckId;
	FDAEDeckRules Rules;
	TArray<int32> DefaultStarterCards;
	int32 MaxPlayerDecks = 24;
	bool bLoaded = false;
	FString LoadError;
};
