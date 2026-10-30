// Duel Academy Island - shared economy types: card rarity, collection stats,
// pack definitions, reveal payloads and the shop/inventory save payloads.
//
// This header is data-only. The live systems are UDAInventorySubsystem,
// UDAShopSubsystem and UDADeckLogic.

#pragma once

#include "CoreMinimal.h"
#include "DAEconomyTypes.generated.h"

/** Collection rarity. The pack data uses the GBA's five printed rarities. */
UENUM(BlueprintType)
enum class EDAECardRarity : uint8
{
	Common      UMETA(DisplayName = "Common"),
	Rare        UMETA(DisplayName = "Rare"),
	SuperRare   UMETA(DisplayName = "Super Rare"),
	UltraRare   UMETA(DisplayName = "Ultra Rare"),
	SecretRare  UMETA(DisplayName = "Secret Rare")
};

/** How one card slot in a pack is rolled. */
UENUM(BlueprintType)
enum class EDAEPackSlotType : uint8
{
	/** Draw from one fixed rarity pool. */
	FixedRarity,

	/** Draw from a weighted rare-or-better distribution (default 70/22/6/2). */
	RarePlus,

	/** Draw any card (used by Dorothy's Gift, which can give every card). */
	AnyCard
};

/** Unlock condition vocabulary. A02/A03 fill FDAEUnlockContext. */
UENUM(BlueprintType)
enum class EDAEUnlockConditionType : uint8
{
	Start,
	Tutorial,
	Event,
	Counter,
	Title,
	DormChanges,
	VisitedAllDorms,
	PackCompletion,
	CollectionPercent,
	LocationDuels,
	MonthAtLeast,
	Flag,
	Unknown
};

/** Why a purchase is currently blocked (UI can localise on this). */
UENUM(BlueprintType)
enum class EDAEPurchaseBlock : uint8
{
	None,
	PackNotFound,
	Locked,
	InsufficientDP,
	Restocking,
	SoldOut,
	InvalidPack,
	NoInventory,
	WalletRejected,
	OpenFailed,
	DeckInvalid
};

/** A weighted rarity entry used by rare-plus slots. */
USTRUCT(BlueprintType)
struct FDAERarityWeight
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	EDAECardRarity Rarity = EDAECardRarity::Rare;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 Weight = 1;
};

/** One rarity pool in a pack definition. */
USTRUCT(BlueprintType)
struct FDAERarityPool
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	EDAECardRarity Rarity = EDAECardRarity::Common;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	TArray<int32> Cards;
};

/** One slot in a pack. */
USTRUCT(BlueprintType)
struct FDAEPackSlot
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	EDAEPackSlotType Type = EDAEPackSlotType::FixedRarity;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	EDAECardRarity Rarity = EDAECardRarity::Common;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	TArray<FDAERarityWeight> Weights;
};

/** One structured unlock requirement. */
USTRUCT(BlueprintType)
struct FDAEUnlockCondition
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	EDAEUnlockConditionType Type = EDAEUnlockConditionType::Start;

	/** Event/tutorial/title/counter/location/pack id, depending on Type. */
	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	FString Key;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	int32 Value = 0;

	/** Human-readable canon text for the shop UI. */
	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	FString Description;
};

/**
 * A booster pack definition. Loaded from Content/Data/Shop/packs.json.
 * Pools are card ids; all ids are validated against cards.json on load.
 */
USTRUCT(BlueprintType)
struct FDAEPackDef
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	FString Id;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	FString Category;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	FString Description;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	FString Source;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 Price = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 PackSize = 5;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 RestockDays = 7;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 PurchaseLimit = 1;

	/** Lifetime stock from A01 canon; 0/-1 means unlimited. */
	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 Stock = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 DuplicateDPPerCard = 25;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	bool bAllCards = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	bool bPreferUnowned = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	bool bAllowDuplicatesInPack = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	bool bProvisional = true;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	FString UnlockDescription;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	TArray<FDAEPackSlot> Slots;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	TArray<FDAERarityPool> Pools;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	TArray<FDAERarityWeight> RarePlusWeights;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	TArray<FDAEUnlockCondition> UnlockConditions;

	/** Non-owning lookup; null when the pool is empty/missing. */
	const TArray<int32>* FindPool(EDAECardRarity Rarity) const
	{
		for (const FDAERarityPool& Pool : Pools)
		{
			if (Pool.Rarity == Rarity && Pool.Cards.Num() > 0)
			{
				return &Pool.Cards;
			}
		}
		return nullptr;
	}

	bool HasAnyPool() const
	{
		if (bAllCards)
		{
			return true;
		}
		for (const FDAERarityPool& Pool : Pools)
		{
			if (Pool.Cards.Num() > 0)
			{
				return true;
			}
		}
		return false;
	}
};

/** One card shown on the pack-opening / reveal screen. */
USTRUCT(BlueprintType)
struct FDAEPackCardReveal
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 CardId = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	EDAECardRarity Rarity = EDAECardRarity::Common;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	bool bNew = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	bool bDuplicate = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 OwnedBefore = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 OwnedAfter = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 DuplicateDP = 0;
};

/** Deterministic pack result. Same pack + same non-zero seed = same card ids. */
USTRUCT(BlueprintType)
struct FDAEPackOpenResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	bool bSuccess = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	FString ErrorCode;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	FString ErrorMessage;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	FString PackId;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 Seed = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	TArray<FDAEPackCardReveal> Cards;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 DPFromDuplicates = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 DPBefore = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Pack")
	int32 DPAfter = 0;
};

/** Result of UDAShopSubsystem::PurchasePack. */
USTRUCT(BlueprintType)
struct FDAEPurchaseResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	bool bPurchased = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	EDAEPurchaseBlock Block = EDAEPurchaseBlock::None;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	FString ErrorCode;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	FString ErrorMessage;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	FString PackId;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	int32 Price = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	int32 DPBefore = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	int32 DPAfter = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	FDAEPackOpenResult Open;
};

/** Per-pack UI row returned by GetCatalogue / GetVisiblePacks. */
USTRUCT(BlueprintType)
struct FDAEPackView
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	FString PackId;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	FString Category;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	int32 Price = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	int32 PackSize = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	bool bUnlocked = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	bool bCanPurchase = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	EDAEPurchaseBlock Block = EDAEPurchaseBlock::None;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	FString UnlockReason;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	FString StatusText;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	int32 RestockDays = 7;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	int32 LastPurchaseDay = -1;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Shop")
	int32 NextAvailableDay = -1;
};

/**
 * Everything the shop needs from A02/A03 to evaluate unlocks. Populate it
 * through UDAShopSubsystem::SetUnlockContextProvider or SetUnlockContext.
 * DayNumber is an absolute in-game day (new game = 0 or 1); -1 disables the
 * restock clock.
 */
USTRUCT(BlueprintType)
struct FDAEUnlockContext
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	FString Title;

	/** 1 = October (school year month 1), matching the masterplan calendar. */
	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	int32 MonthIndex = 1;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	int32 DayNumber = -1;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	int32 DormChanges = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	TArray<FString> Titles;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	TArray<FString> CompletedEvents;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	TArray<FString> CompletedTutorials;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	TArray<FString> DormsVisited;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	TArray<FString> Flags;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	TMap<FString, int32> Counters;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	TMap<FString, int32> LocationDuelCounts;

	/** Optional external pack-completion percentages; the shop also computes these from inventory. */
	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	TMap<FString, float> PackCompletion;

	/** Optional external collection percentage; the shop prefers inventory when available. */
	UPROPERTY(BlueprintReadOnly, Category = "Economy|Unlock")
	float CollectionPercent = 0.f;

	bool HasTitle(const FString& InTitle) const
	{
		return Title.Equals(InTitle, ESearchCase::IgnoreCase) ||
			Titles.ContainsByPredicate([&InTitle](const FString& Entry)
			{
				return Entry.Equals(InTitle, ESearchCase::IgnoreCase);
			});
	}

	bool HasEvent(const FString& Key) const
	{
		return CompletedEvents.ContainsByPredicate([&Key](const FString& Entry)
		{
			return Entry.Equals(Key, ESearchCase::IgnoreCase);
		});
	}

	bool HasTutorial(const FString& Key) const
	{
		return CompletedTutorials.ContainsByPredicate([&Key](const FString& Entry)
		{
			return Entry.Equals(Key, ESearchCase::IgnoreCase);
		});
	}

	bool HasFlag(const FString& Key) const
	{
		return Flags.ContainsByPredicate([&Key](const FString& Entry)
		{
			return Entry.Equals(Key, ESearchCase::IgnoreCase);
		});
	}

	bool HasVisitedAllDorms() const
	{
		const bool bSlifer = DormsVisited.ContainsByPredicate([](const FString& Entry) { return Entry.Equals(TEXT("Slifer"), ESearchCase::IgnoreCase); });
		const bool bRa = DormsVisited.ContainsByPredicate([](const FString& Entry) { return Entry.Equals(TEXT("Ra"), ESearchCase::IgnoreCase); });
		const bool bObelisk = DormsVisited.ContainsByPredicate([](const FString& Entry) { return Entry.Equals(TEXT("Obelisk"), ESearchCase::IgnoreCase); });
		return bSlifer && bRa && bObelisk;
	}
};

/** One rarity row in the card trunk's collection summary. */
USTRUCT(BlueprintType)
struct FDAERarityCount
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	EDAECardRarity Rarity = EDAECardRarity::Common;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	int32 Count = 0;
};

/** Aggregated card-trunk stats. Counts include duplicate copies. */
USTRUCT(BlueprintType)
struct FDAECollectionStats
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	int32 UniqueCards = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	int32 TotalCards = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	int32 CatalogSize = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	float CompletionPercent = 0.f;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	TArray<FDAERarityCount> RarityCounts;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	TMap<FString, int32> TypeCounts;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	TMap<FString, int32> AttributeCounts;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	TMap<FString, int32> MonsterTypeCounts;
};

/** Card-trunk filter. Empty arrays / -1 bounds mean "no restriction". */
USTRUCT(BlueprintType)
struct FDAECardFilter
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	FString NameContains;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	TArray<FString> CardTypes;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	TArray<FString> Attributes;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	TArray<FString> MonsterTypes;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	TArray<EDAECardRarity> Rarities;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	int32 MinAtk = -1;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	int32 MaxAtk = -1;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	int32 MinLevel = -1;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	int32 MaxLevel = -1;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	bool bMonstersOnly = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	bool bSpellsOnly = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	bool bTrapsOnly = false;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Collection")
	bool bOwnedOnly = true;
};

/** Card-trunk sort keys. */
UENUM(BlueprintType)
enum class EDAECardSortKey : uint8
{
	CardId,
	Name,
	Attack,
	Defense,
	Level,
	CardType,
	Attribute,
	MonsterType,
	Rarity
};

/** An ante card that has left the collection and must be returned or lost. */
USTRUCT(BlueprintType)
struct FDAEAnteRecord
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Ante")
	int32 CardId = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Ante")
	FString DuelId;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Ante")
	FString Source;
};

/** Save-friendly inventory payload. A02 embeds this in the profile save. */
USTRUCT(BlueprintType)
struct FDAEInventorySaveData
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	int32 Version = 1;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	int32 MaxOwnedCopies = 3;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	TMap<int32, int32> Counts;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	TArray<FDAEAnteRecord> PendingAnte;
};

namespace DAEconomy
{
	inline FString RarityToString(EDAECardRarity Rarity)
	{
		switch (Rarity)
		{
		case EDAECardRarity::Rare:       return TEXT("Rare");
		case EDAECardRarity::SuperRare:  return TEXT("Super Rare");
		case EDAECardRarity::UltraRare:  return TEXT("Ultra Rare");
		case EDAECardRarity::SecretRare: return TEXT("Secret Rare");
		case EDAECardRarity::Common:
		default:                         return TEXT("Common");
		}
	}

	inline bool ParseRarity(const FString& Text, EDAECardRarity& OutRarity)
	{
		const FString Key = Text.Replace(TEXT(" "), TEXT("")).Replace(TEXT("_"), TEXT("")).ToLower();
		if (Key == TEXT("common"))      { OutRarity = EDAECardRarity::Common; return true; }
		if (Key == TEXT("rare"))        { OutRarity = EDAECardRarity::Rare; return true; }
		if (Key == TEXT("superrare"))   { OutRarity = EDAECardRarity::SuperRare; return true; }
		if (Key == TEXT("ultrarare"))   { OutRarity = EDAECardRarity::UltraRare; return true; }
		if (Key == TEXT("secretrare"))  { OutRarity = EDAECardRarity::SecretRare; return true; }
		return false;
	}

	inline bool IsRareOrBetter(EDAECardRarity Rarity)
	{
		return Rarity != EDAECardRarity::Common;
	}
}
