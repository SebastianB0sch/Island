#include "DAInventorySubsystem.h"

#include "DAEconomyJson.h"
#include "DAEconomyTests.h"
#include "DACardRecords.h"
#include "DADeckLogic.h"
#include "DAShopSubsystem.h"
#include "DAStorySubsystem.h"
#include "DuelAcademyIsland.h"

#include "Algo/Unique.h"
#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonWriter.h"

namespace
{
	const TCHAR* OwnershipRulesPath()
	{
		return TEXT("Data/Rules/banned_limited.json");
	}

	const TCHAR* RarityPath()
	{
		return TEXT("Data/Rules/card_rarity.json");
	}

	/** Written by WriteSaveSection; RequireVersion accepts this and older. */
	constexpr int32 InventorySaveSectionVersion = 1;

	bool MatchesAny(const FString& Value, const TArray<FString>& Filters)
	{
		if (Filters.Num() == 0)
		{
			return true;
		}
		for (const FString& Filter : Filters)
		{
			if (!Filter.IsEmpty() && Value.Equals(Filter, ESearchCase::IgnoreCase))
			{
				return true;
			}
			if (!Filter.IsEmpty() && Value.Contains(Filter, ESearchCase::IgnoreCase))
			{
				return true;
			}
		}
		return false;
	}

	/** Saturating int32 addition used by aggregation and DP counters. */
	int32 SaturatingAdd(int32 Base, int64 Delta)
	{
		return static_cast<int32>(FMath::Clamp<int64>(
			static_cast<int64>(Base) + Delta, 0, TNumericLimits<int32>::Max()));
	}

	/**
	 * Parses a counts-object key.  The save writer always emits canonical
	 * positive decimal card ids, so "1x", "1.0", " 1" and "01" are malformed.
	 */
	bool ParseCardCountKey(const FString& Key, int32& OutCardId)
	{
		if (Key.IsEmpty() || Key.Len() > 10)
		{
			return false;
		}
		int64 Parsed = 0;
		for (const TCHAR Character : Key)
		{
			if (Character < TEXT('0') || Character > TEXT('9'))
			{
				return false;
			}
			Parsed = Parsed * 10 + static_cast<int64>(Character - TEXT('0'));
			if (Parsed > TNumericLimits<int32>::Max())
			{
				return false;
			}
		}
		if (Parsed <= 0 || (Key.Len() > 1 && Key[0] == TEXT('0')))
		{
			return false;
		}
		OutCardId = static_cast<int32>(Parsed);
		return true;
	}

	bool ReadSaveCount(const TSharedPtr<FJsonValue>& Value, int32& OutCount)
	{
		int32 Parsed = 0;
		if (!DAEconomyJson::TryReadInt(Value, Parsed) || Parsed < 0)
		{
			return false;
		}
		OutCount = Parsed;
		return true;
	}

	bool ReadSaveNonNegative(const TSharedPtr<FJsonValue>& Value, int32& OutNumber)
	{
		int32 Parsed = 0;
		if (!DAEconomyJson::TryReadInt(Value, Parsed) || Parsed < 0)
		{
			return false;
		}
		OutNumber = Parsed;
		return true;
	}

	/**
	 * Shared non-mutating validator for the inventory save section.  Both the
	 * provider validation hook and ImportStateJson use it so a malformed save
	 * is rejected instead of silently dropping entries (which used to turn
	 * {"1x": 3} into a card-1 grant or an empty collection).
	 */
	bool ValidateInventorySectionObject(const TSharedPtr<FJsonObject>& Object, FString& OutError)
	{
		if (!Object.IsValid())
		{
			OutError = TEXT("Inventory save section is missing.");
			return false;
		}

		if (!DAEconomyJson::RequireVersion(Object, InventorySaveSectionVersion, OutError))
		{
			return false;
		}

		const TSharedPtr<FJsonObject>* CountsObject = nullptr;
		if (!Object->TryGetObjectField(TEXT("counts"), CountsObject) || !CountsObject || !CountsObject->IsValid())
		{
			OutError = TEXT("Inventory save section is missing the counts object.");
			return false;
		}
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*CountsObject)->Values)
		{
			int32 CardId = 0;
			int32 Count = 0;
			if (!ParseCardCountKey(Pair.Key, CardId))
			{
				OutError = FString::Printf(TEXT("Inventory save section has an invalid card id '%s'."), *Pair.Key);
				return false;
			}
			if (!ReadSaveCount(Pair.Value, Count))
			{
				OutError = FString::Printf(TEXT("Inventory save section has an invalid count for card %d."), CardId);
				return false;
			}
		}

		if (Object->HasField(TEXT("max_owned_copies")))
		{
			int32 MaxOwned = 0;
			if (!ReadSaveNonNegative(Object->TryGetField(TEXT("max_owned_copies")), MaxOwned))
			{
				OutError = TEXT("Inventory save section has an invalid max_owned_copies value.");
				return false;
			}
		}

		if (Object->HasField(TEXT("pending_ante")))
		{
			const TArray<TSharedPtr<FJsonValue>>* AnteArray = nullptr;
			if (!Object->TryGetArrayField(TEXT("pending_ante"), AnteArray) || !AnteArray)
			{
				OutError = TEXT("Inventory save section has a non-array pending_ante value.");
				return false;
			}
			for (const TSharedPtr<FJsonValue>& Value : *AnteArray)
			{
				const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
				if (!Entry.IsValid())
				{
					OutError = TEXT("Inventory save section has a non-object ante entry.");
					return false;
				}
				int32 CardId = 0;
				if (!DAEconomyJson::TryReadCardId(Entry->TryGetField(TEXT("card_id")), CardId))
				{
					OutError = TEXT("Inventory save section has an invalid ante card id.");
					return false;
				}
				const TSharedPtr<FJsonValue> DuelValue = Entry->TryGetField(TEXT("duel_id"));
				FString DuelId;
				if (!DuelValue.IsValid() || DuelValue->Type != EJson::String
					|| !DuelValue->TryGetString(DuelId)
					|| DAEconomy::NormalizeIdKey(DuelId).IsEmpty())
				{
					OutError = TEXT("Inventory save section has an ante record without a duel id.");
					return false;
				}
				const TSharedPtr<FJsonValue> SourceValue = Entry->TryGetField(TEXT("source"));
				FString Source;
				if (SourceValue.IsValid()
					&& (SourceValue->Type != EJson::String || !SourceValue->TryGetString(Source)))
				{
					OutError = TEXT("Inventory save section has an invalid ante source.");
					return false;
				}
			}
		}

		OutError.Reset();
		return true;
	}
}

void UDAInventorySubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	// The profile (inventory provider) and save (payload provider) subsystems
	// must exist before this one registers with them.
	Collection.InitializeDependency<UDAProfileSubsystem>();
	Collection.InitializeDependency<UDASaveSubsystem>();
	Super::Initialize(Collection);

	LoadOwnershipLimit();
	LoadRarityMap();

	if (UGameInstance* GI = GetGameInstance())
	{
		if (UDAProfileSubsystem* Profile = GI->GetSubsystem<UDAProfileSubsystem>())
		{
			Profile->SetInventoryProvider(this);
		}
		if (UDASaveSubsystem* Save = GI->GetSubsystem<UDASaveSubsystem>())
		{
			Save->RegisterPayloadProvider(this);
		}
	}

	if (FParse::Param(FCommandLine::Get(), TEXT("DAEconomySelfTest")))
	{
		ScheduleSelfTest();
	}
}

FString UDAInventorySubsystem::GetSaveSectionName() const
{
	return TEXT("inventory");
}

bool UDAInventorySubsystem::WriteSaveSection(TSharedPtr<FJsonObject>& OutSection) const
{
	if (!OutSection.IsValid())
	{
		OutSection = MakeShared<FJsonObject>();
	}
	WriteStateFields(*OutSection);
	return true;
}

bool UDAInventorySubsystem::ValidateSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError) const
{
	return ValidateInventorySectionObject(InSection, OutError);
}

bool UDAInventorySubsystem::ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError)
{
	if (!ValidateSaveSection(InSection, OutError))
	{
		return false;
	}
	return ApplyStateObject(*InSection, OutError);
}

void UDAInventorySubsystem::ResetSaveSectionState()
{
	// A legacy payload with no inventory section must not leave a previous
	// session's trunk in memory.
	ResetCollection();
}

void UDAInventorySubsystem::Deinitialize()
{
	if (SelfTestTicker.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(SelfTestTicker);
		SelfTestTicker.Reset();
	}
	Super::Deinitialize();
}

void UDAInventorySubsystem::LoadOwnershipLimit()
{
	const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), OwnershipRulesPath());
	TSharedPtr<FJsonValue> Root;
	FString Error;
	if (!DAEconomyJson::LoadFile(Path, Root, Error))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Inventory: %s (using max_owned_copies=3)"), *Error);
		return;
	}
	const TSharedPtr<FJsonObject> Object = Root->AsObject();
	if (!Object.IsValid())
	{
		return;
	}

	int32 Value = MaxOwnedCopies;
	int32 Parsed = 0;
	if (DAEconomyJson::TryReadInt(Object->TryGetField(TEXT("max_owned_copies")), Parsed))
	{
		Value = Parsed;
	}
	else
	{
		const TSharedPtr<FJsonObject>* RulesObject = nullptr;
		if (Object->TryGetObjectField(TEXT("rules"), RulesObject) && RulesObject && RulesObject->IsValid()
			&& DAEconomyJson::TryReadInt((*RulesObject)->TryGetField(TEXT("max_owned_copies")), Parsed))
		{
			Value = Parsed;
		}
	}
	// Older save/profile data may omit the field; keep the 3-copy default.
	MaxOwnedCopies = FMath::Max(0, Value);
}

void UDAInventorySubsystem::LoadRarityMap()
{
	RarityById.Reset();

	const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), RarityPath());
	TSharedPtr<FJsonValue> Root;
	FString Error;
	if (!DAEconomyJson::LoadFile(Path, Root, Error))
	{
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("Inventory: rarity hints unavailable (%s)"), *Error);
		return;
	}

	const TSharedPtr<FJsonObject> Object = Root->AsObject();
	const TArray<TSharedPtr<FJsonValue>>* Rarities = nullptr;
	if (Object.IsValid() && Object->TryGetArrayField(TEXT("rarities"), Rarities) && Rarities)
	{
		for (const TSharedPtr<FJsonValue>& Value : *Rarities)
		{
			const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!Entry.IsValid())
			{
				continue;
			}
			const int32 CardId = DAEconomyJson::ReadInt(Entry, TEXT("card_id"));
			const FString RarityText = DAEconomyJson::ReadString(Entry, TEXT("rarity"));
			EDAECardRarity Rarity;
			if (CardId > 0 && DAEconomyJson::ParseRarity(RarityText, Rarity))
			{
				RarityById.Add(CardId, Rarity);
			}
		}
	}

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Inventory: loaded rarity hints for %d cards."), RarityById.Num());
}

int32 UDAInventorySubsystem::GetCount(int32 CardId) const
{
	const int32* Count = Counts.Find(CardId);
	return Count ? *Count : 0;
}

bool UDAInventorySubsystem::HasCard(int32 CardId, int32 MinCount) const
{
	return GetCount(CardId) >= FMath::Max(0, MinCount);
}

int32 UDAInventorySubsystem::AddCard(int32 CardId, int32 Count)
{
	if (CardId <= 0 || Count <= 0 || !IsKnownCard(CardId))
	{
		return 0;
	}

	// Read the existing count instead of FindOrAdd: inserting before the cap
	// check used to leave a permanent id->0 phantom entry behind whenever an
	// at-cap/invalid add returned early, inflating GetDistinctCardsOwned
	// (Counts.Num()) and every MinCardsOwned title gate that reads it.
	const int32 Owned = GetCount(CardId);
	const int64 Space = MaxOwnedCopies > 0
		? FMath::Max<int64>(0, static_cast<int64>(MaxOwnedCopies) - Owned)
		: Count;
	const int32 Requested = static_cast<int32>(FMath::Min<int64>(Count, Space));
	const int32 NewOwned = static_cast<int32>(FMath::Clamp<int64>(
		static_cast<int64>(Owned) + Requested, 0, TNumericLimits<int32>::Max()));
	const int32 Added = NewOwned - Owned;
	if (Added <= 0)
	{
		return 0;
	}

	// Only insert/overwrite when the count actually moves (also heals a legacy
	// phantom zero entry for the same id).
	Counts.Add(CardId, NewOwned);
	OnCollectionChanged.Broadcast(CardId, NewOwned);
	return Added;
}

int32 UDAInventorySubsystem::RemoveCard(int32 CardId, int32 Count)
{
	if (CardId <= 0 || Count <= 0)
	{
		return 0;
	}

	int32* Owned = Counts.Find(CardId);
	if (!Owned || *Owned <= 0)
	{
		return 0;
	}

	const int32 Removed = FMath::Min(Count, *Owned);
	*Owned -= Removed;
	if (*Owned <= 0)
	{
		Counts.Remove(CardId);
	}
	OnCollectionChanged.Broadcast(CardId, GetCount(CardId));
	return Removed;
}

bool UDAInventorySubsystem::CanAddCard(int32 CardId, int32 Count) const
{
	if (CardId <= 0 || Count <= 0 || !IsKnownCard(CardId))
	{
		return false;
	}
	if (MaxOwnedCopies <= 0)
	{
		return true;
	}
	return static_cast<int64>(GetCount(CardId)) + Count <= MaxOwnedCopies;
}

bool UDAInventorySubsystem::IsKnownCard(int32 CardId) const
{
	if (CardId <= 0)
	{
		return false;
	}
	const UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	return Database && Database->FindCard(CardId) != nullptr;
}

int32 UDAInventorySubsystem::GrantStarterCollection(const TArray<int32>& CardIds)
{
	int32 Added = 0;
	for (const int32 CardId : CardIds)
	{
		Added += AddCard(CardId, 1);
	}
	return Added;
}

void UDAInventorySubsystem::ResetCollection()
{
	Counts.Reset();
	PendingAnte.Reset();
	OnInventoryReset.Broadcast();
	OnAnteChanged.Broadcast(0);
}

TArray<int32> UDAInventorySubsystem::GetCollectionCards() const
{
	TArray<int32> Cards;
	Counts.GetKeys(Cards);
	Cards.Sort();
	return Cards;
}

int32 UDAInventorySubsystem::GetCollectionSize() const
{
	int64 Total = 0;
	for (const TPair<int32, int32>& Pair : Counts)
	{
		if (Pair.Value > 0)
		{
			Total += Pair.Value;
		}
	}
	return static_cast<int32>(FMath::Clamp<int64>(Total, 0, TNumericLimits<int32>::Max()));
}

int32 UDAInventorySubsystem::GetCatalogSize() const
{
	const UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	return Database ? Database->GetCardCount() : 0;
}

FDAECollectionStats UDAInventorySubsystem::GetCollectionStats() const
{
	FDAECollectionStats Stats;
	const UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	Stats.CatalogSize = Database ? Database->GetCardCount() : 0;
	int32 KnownUniqueCards = 0;

	for (const EDAECardRarity Rarity : { EDAECardRarity::Common, EDAECardRarity::Rare, EDAECardRarity::SuperRare, EDAECardRarity::UltraRare, EDAECardRarity::SecretRare })
	{
		FDAERarityCount Entry;
		Entry.Rarity = Rarity;
		Entry.Count = 0;
		Stats.RarityCounts.Add(Entry);
	}

	for (const TPair<int32, int32>& Pair : Counts)
	{
		if (Pair.Value <= 0)
		{
			continue;
		}
		Stats.UniqueCards++;
		Stats.TotalCards = SaturatingAdd(Stats.TotalCards, Pair.Value);

		const EDAECardRarity Rarity = GetCardRarity(Pair.Key);
		for (FDAERarityCount& Entry : Stats.RarityCounts)
		{
			if (Entry.Rarity == Rarity)
			{
				Entry.Count = SaturatingAdd(Entry.Count, Pair.Value);
				break;
			}
		}

		const FCardRecord* Card = Database ? Database->FindCard(Pair.Key) : nullptr;
		if (!Card)
		{
			// Legacy saves can contain ids that were later removed from
			// cards.json. They remain owned counts above, but must not inflate
			// catalogue completion (which is a fraction of the current catalog).
			continue;
		}
		KnownUniqueCards++;
		if (!Card->CardType.IsEmpty())
		{
			int32& TypeCount = Stats.TypeCounts.FindOrAdd(Card->CardType);
			TypeCount = SaturatingAdd(TypeCount, Pair.Value);
		}
		if (!Card->Attribute.IsEmpty() && Card->Attribute != TEXT("NONE"))
		{
			int32& AttributeCount = Stats.AttributeCounts.FindOrAdd(Card->Attribute);
			AttributeCount = SaturatingAdd(AttributeCount, Pair.Value);
		}
		if (!Card->MonsterType.IsEmpty() && Card->IsMonster())
		{
			int32& MonsterTypeCount = Stats.MonsterTypeCounts.FindOrAdd(Card->MonsterType);
			MonsterTypeCount = SaturatingAdd(MonsterTypeCount, Pair.Value);
		}
	}

	Stats.CompletionPercent = Stats.CatalogSize > 0
		? FMath::Clamp(static_cast<float>(KnownUniqueCards) * 100.f / static_cast<float>(Stats.CatalogSize), 0.f, 100.f)
		: 0.f;
	return Stats;
}

EDAECardRarity UDAInventorySubsystem::GetCardRarity(int32 CardId) const
{
	if (const EDAECardRarity* Rarity = RarityById.Find(CardId))
	{
		return *Rarity;
	}
	return EDAECardRarity::Common;
}

FString UDAInventorySubsystem::GetCardRarityName(int32 CardId) const
{
	return DAEconomy::RarityToString(GetCardRarity(CardId));
}

TArray<int32> UDAInventorySubsystem::FilterCollection(const FDAECardFilter& Filter) const
{
	const UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	if (!Database)
	{
		return TArray<int32>();
	}

	TArray<int32> Result;
	if (Filter.bOwnedOnly)
	{
		Result.Reserve(Counts.Num());
		for (const TPair<int32, int32>& Pair : Counts)
		{
			if (Pair.Value > 0)
			{
				Result.Add(Pair.Key);
			}
		}
	}
	else
	{
		Database->GetCards().GetKeys(Result);
	}

	Result.RemoveAll([this, Database, &Filter](int32 CardId)
	{
		const FCardRecord* Card = Database->FindCard(CardId);
		if (!Card)
		{
			return true;
		}
		if (!Filter.NameContains.IsEmpty() && !Card->Name.Contains(Filter.NameContains, ESearchCase::IgnoreCase))
		{
			return true;
		}
		if (Filter.bMonstersOnly && !Card->IsMonster()) return true;
		if (Filter.bSpellsOnly && !Card->IsSpell()) return true;
		if (Filter.bTrapsOnly && !Card->IsTrap()) return true;

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
			if (!bTypeMatch) return true;
		}
		if (!MatchesAny(Card->Attribute, Filter.Attributes)) return true;
		if (!MatchesAny(Card->MonsterType, Filter.MonsterTypes)) return true;
		if (Filter.Rarities.Num() > 0 && !Filter.Rarities.Contains(GetCardRarity(CardId))) return true;

		const bool bHasAtkFilter = Filter.MinAtk >= 0 || Filter.MaxAtk >= 0;
		const bool bHasLevelFilter = Filter.MinLevel >= 0 || Filter.MaxLevel >= 0;
		if (bHasAtkFilter || bHasLevelFilter)
		{
			if (!Card->IsMonster()) return true;
			if (bHasAtkFilter)
			{
				if (Filter.MinAtk >= 0 && Card->Atk < Filter.MinAtk) return true;
				if (Filter.MaxAtk >= 0 && Card->Atk > Filter.MaxAtk) return true;
			}
			if (bHasLevelFilter)
			{
				if (Filter.MinLevel >= 0 && Card->Level < Filter.MinLevel) return true;
				if (Filter.MaxLevel >= 0 && Card->Level > Filter.MaxLevel) return true;
			}
		}
		return false;
	});

	Result.Sort();
	return Result;
}

TArray<int32> UDAInventorySubsystem::SortCards(const TArray<int32>& CardIds, EDAECardSortKey SortKey, bool bDescending) const
{
	TArray<int32> Result = CardIds;
	const UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	if (!Database)
	{
		return Result;
	}

	auto Compare = [this, Database, SortKey](int32 A, int32 B) -> int32
	{
		const FCardRecord* CardA = Database->FindCard(A);
		const FCardRecord* CardB = Database->FindCard(B);
		if (!CardA && !CardB) return 0;
		if (!CardA) return 1;
		if (!CardB) return -1;

		switch (SortKey)
		{
		case EDAECardSortKey::Name:        return CardA->Name.Compare(CardB->Name, ESearchCase::IgnoreCase);
		case EDAECardSortKey::Attack:      return CardA->Atk == CardB->Atk ? 0 : (CardA->Atk < CardB->Atk ? -1 : 1);
		case EDAECardSortKey::Defense:     return CardA->Def == CardB->Def ? 0 : (CardA->Def < CardB->Def ? -1 : 1);
		case EDAECardSortKey::Level:       return CardA->Level == CardB->Level ? 0 : (CardA->Level < CardB->Level ? -1 : 1);
		case EDAECardSortKey::CardType:    return CardA->CardType.Compare(CardB->CardType, ESearchCase::IgnoreCase);
		case EDAECardSortKey::Attribute:   return CardA->Attribute.Compare(CardB->Attribute, ESearchCase::IgnoreCase);
		case EDAECardSortKey::MonsterType: return CardA->MonsterType.Compare(CardB->MonsterType, ESearchCase::IgnoreCase);
		case EDAECardSortKey::Rarity:
		{
			const int32 RarityA = static_cast<int32>(GetCardRarity(A));
			const int32 RarityB = static_cast<int32>(GetCardRarity(B));
			return RarityA == RarityB ? 0 : (RarityA < RarityB ? -1 : 1);
		}
		case EDAECardSortKey::CardId:
		default:
			return A == B ? 0 : (A < B ? -1 : 1);
		}
	};

	Result.StableSort([&Compare, bDescending](int32 A, int32 B)
	{
		const int32 Cmp = Compare(A, B);
		if (Cmp != 0)
		{
			return bDescending ? Cmp > 0 : Cmp < 0;
		}
		return A < B;
	});
	return Result;
}

void UDAInventorySubsystem::SetMaxOwnedCopies(int32 NewMax)
{
	MaxOwnedCopies = FMath::Max(0, NewMax);
}

FDAEPackOpenResult UDAInventorySubsystem::OpenPack(const FString& PackId, int32 Seed)
{
	FDAEPackOpenResult Result;
	Result.PackId = PackId;
	Result.Seed = Seed;

	UGameInstance* GI = GetGameInstance();
	UDAShopSubsystem* Shop = GI ? GI->GetSubsystem<UDAShopSubsystem>() : nullptr;
	if (!Shop)
	{
		Result.ErrorCode = TEXT("shop_unavailable");
		Result.ErrorMessage = TEXT("The card shop is not available.");
		return Result;
	}

	const FDAEPackDef* Pack = Shop->FindPack(PackId);
	if (!Pack)
	{
		Result.ErrorCode = TEXT("pack_not_found");
		Result.ErrorMessage = FString::Printf(TEXT("Unknown booster pack '%s'."), *PackId);
		return Result;
	}
	Result.PackId = Pack->Id;
	return OpenPackDefinition(*Pack, Seed, true);
}

FDAEPackOpenResult UDAInventorySubsystem::PreviewPack(const FString& PackId, int32 Seed)
{
	FDAEPackOpenResult Result;
	Result.PackId = PackId;
	Result.Seed = Seed;

	UGameInstance* GI = GetGameInstance();
	UDAShopSubsystem* Shop = GI ? GI->GetSubsystem<UDAShopSubsystem>() : nullptr;
	if (!Shop)
	{
		Result.ErrorCode = TEXT("shop_unavailable");
		Result.ErrorMessage = TEXT("The card shop is not available.");
		return Result;
	}
	const FDAEPackDef* Pack = Shop->FindPack(PackId);
	if (!Pack)
	{
		Result.ErrorCode = TEXT("pack_not_found");
		Result.ErrorMessage = FString::Printf(TEXT("Unknown booster pack '%s'."), *PackId);
		return Result;
	}
	Result.PackId = Pack->Id;
	return OpenPackDefinition(*Pack, Seed, false);
}

FDAEPackOpenResult UDAInventorySubsystem::ConsumePendingPackGrant(const FString& PackId, int32 Seed)
{
	FDAEPackOpenResult Result;
	Result.PackId = PackId;
	Result.Seed = Seed;

	UGameInstance* GI = GetGameInstance();
	UDAStorySubsystem* Story = GI ? GI->GetSubsystem<UDAStorySubsystem>() : nullptr;
	if (!Story)
	{
		Result.ErrorCode = TEXT("story_unavailable");
		Result.ErrorMessage = TEXT("The story pack-grant queue is not available.");
		return Result;
	}
	if (!Story->GetPendingPackGrants().Contains(PackId))
	{
		Result.ErrorCode = TEXT("no_pending_grant");
		Result.ErrorMessage = TEXT("No pending pack grant matches that pack.");
		return Result;
	}

	UDAShopSubsystem* Shop = GI ? GI->GetSubsystem<UDAShopSubsystem>() : nullptr;
	if (!Shop)
	{
		Result.ErrorCode = TEXT("shop_unavailable");
		Result.ErrorMessage = TEXT("The card shop is not available.");
		return Result;
	}
	const FDAEPackDef* Pack = Shop->FindPack(PackId);
	if (!Pack)
	{
		Result.ErrorCode = TEXT("pack_not_found");
		Result.ErrorMessage = FString::Printf(TEXT("Unknown booster pack '%s'."), *PackId);
		return Result;
	}

	const FDAEPackOpenResult OpenResult = OpenPackDefinition(*Pack, Seed, true);
	if (!OpenResult.bSuccess)
	{
		return OpenResult;
	}

	// Consume the grant only after the cards have been added. If the grant was
	// already taken by another caller, roll back exactly the copies this call
	// added so a race cannot duplicate cards.
	if (!Story->ConsumePendingPackGrant(PackId))
	{
		for (int32 Index = OpenResult.Cards.Num() - 1; Index >= 0; --Index)
		{
			if (!OpenResult.Cards[Index].bDuplicate)
			{
				RemoveCard(OpenResult.Cards[Index].CardId, 1);
			}
		}
		FDAEPackOpenResult Failed = OpenResult;
		Failed.bSuccess = false;
		Failed.ErrorCode = TEXT("grant_consume_failed");
		Failed.ErrorMessage = TEXT("The pending pack grant could not be consumed; the pack was rolled back.");
		Failed.Cards.Reset();
		Failed.DPFromDuplicates = 0;
		return Failed;
	}

	return OpenResult;
}

FDAEPackOpenResult UDAInventorySubsystem::OpenPackDefinition(const FDAEPackDef& Pack, int32 Seed, bool bAddToCollection)
{
	FDAEPackOpenResult Result;
	Result.PackId = Pack.Id;
	Result.Seed = Seed;

	UGameInstance* GI = GetGameInstance();
	UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	if (!Database || Database->GetCardCount() == 0)
	{
		Result.ErrorCode = TEXT("database_unavailable");
		Result.ErrorMessage = TEXT("The card database is not loaded.");
		return Result;
	}

	auto Fail = [&Result](const TCHAR* Code, const FString& Message)
	{
		Result.bSuccess = false;
		Result.ErrorCode = Code;
		Result.ErrorMessage = Message;
		// A failed open is fully rolled back; do not expose partial reveals or
		// duplicate compensation that was never credited.
		Result.Cards.Reset();
		Result.DPFromDuplicates = 0;
		return Result;
	};

	if (Pack.Slots.Num() == 0 || Pack.PackSize <= 0)
	{
		return Fail(TEXT("invalid_pack"), TEXT("This booster pack has no card slots."));
	}
	if (Pack.Slots.Num() != Pack.PackSize)
	{
		return Fail(TEXT("invalid_pack"), TEXT("This booster pack's slot count does not match its pack size."));
	}
	if (!Pack.bAllCards && !Pack.HasAnyPool())
	{
		return Fail(TEXT("empty_pool"), TEXT("This booster pack has no cards in its pool."));
	}
	for (const FDAERarityPool& Pool : Pack.Pools)
	{
		for (const int32 CardId : Pool.Cards)
		{
			if (!Database->FindCard(CardId))
			{
				return Fail(TEXT("invalid_pool_card"), FString::Printf(TEXT("Booster pack '%s' references missing card %d."), *Pack.Id, CardId));
			}
		}
	}

	const int32 ActualSeed = ResolveSeed(Seed);
	Result.Seed = ActualSeed;
	FRandomStream Rng(ActualSeed);

	TArray<int32> AllCardIds;
	if (Pack.bAllCards)
	{
		Database->GetCards().GetKeys(AllCardIds);
	}
	else
	{
		// An AnyCard slot in a non-all-cards pack draws from the union of the
		// materialised rarity pools. validate_packs.py allows this shape, and
		// treating it as an empty all-cards pool made the pack impossible to open.
		for (const FDAERarityPool& Pool : Pack.Pools)
		{
			AllCardIds.Append(Pool.Cards);
		}
	}
	AllCardIds.Sort();
	AllCardIds.SetNum(Algo::Unique(AllCardIds));

	TSet<int32> PickedThisPack;
	TArray<int32> AddedCards;
	TMap<int32, int32> SimulatedCounts;
	if (!bAddToCollection)
	{
		// Preview state is simulated from a copy of the trunk; a real open
		// reads the live counts instead, so skip the copy on that path.
		SimulatedCounts = Counts;
	}

	auto PickFromPool = [&Rng, &PickedThisPack, &Pack](const TArray<int32>& Pool) -> int32
	{
		if (Pool.Num() == 0)
		{
			return 0;
		}
		if (!Pack.bAllowDuplicatesInPack)
		{
			TArray<int32> Unpicked;
			Unpicked.Reserve(Pool.Num());
			for (const int32 CardId : Pool)
			{
				if (!PickedThisPack.Contains(CardId))
				{
					Unpicked.Add(CardId);
				}
			}
			if (Unpicked.Num() > 0)
			{
				return Unpicked[Rng.RandRange(0, Unpicked.Num() - 1)];
			}
		}
		return Pool[Rng.RandRange(0, Pool.Num() - 1)];
	};

	auto FindFallbackPool = [&Pack](EDAECardRarity& OutRarity) -> const TArray<int32>*
	{
		for (const EDAECardRarity Candidate : { EDAECardRarity::Common, EDAECardRarity::Rare, EDAECardRarity::SuperRare, EDAECardRarity::UltraRare, EDAECardRarity::SecretRare })
		{
			if (const TArray<int32>* Pool = Pack.FindPool(Candidate))
			{
				OutRarity = Candidate;
				return Pool;
			}
		}
		return nullptr;
	};

	// Undo every copy this call added so a bad pack never half-applies.
	auto RollBack = [this, &AddedCards]()
	{
		for (int32 Index = AddedCards.Num() - 1; Index >= 0; --Index)
		{
			RemoveCard(AddedCards[Index], 1);
		}
		AddedCards.Reset();
	};

	// Reveal bookkeeping shared by every slot type: add (or simulate adding)
	// one copy, flag duplicates past the ownership cap and accrue their DP.
	auto RevealCard = [this, &Pack, &Result, Database, bAddToCollection, &SimulatedCounts, &AddedCards, &PickedThisPack]
		(int32 CardId, EDAECardRarity Rarity)
	{
		FDAEPackCardReveal Reveal;
		Reveal.CardId = CardId;
		Reveal.Rarity = Rarity;
		if (const FCardRecord* Card = Database->FindCard(CardId))
		{
			Reveal.Name = Card->Name;
		}
		const int32 OwnedBefore = bAddToCollection ? GetCount(CardId) : SimulatedCounts.FindRef(CardId);
		Reveal.OwnedBefore = OwnedBefore;
		Reveal.bNew = OwnedBefore == 0;

		if (bAddToCollection)
		{
			const int32 Added = AddCard(CardId, 1);
			if (Added > 0)
			{
				AddedCards.Add(CardId);
			}
			Reveal.bDuplicate = Added == 0;
			Reveal.OwnedAfter = GetCount(CardId);
		}
		else
		{
			Reveal.bDuplicate = MaxOwnedCopies > 0 && OwnedBefore >= MaxOwnedCopies;
			Reveal.OwnedAfter = Reveal.bDuplicate ? OwnedBefore : OwnedBefore + 1;
			SimulatedCounts.FindOrAdd(CardId) = Reveal.OwnedAfter;
		}
		if (Reveal.bDuplicate)
		{
			Reveal.DuplicateDP = Pack.DuplicateDPPerCard;
			Result.DPFromDuplicates += Reveal.DuplicateDP;
		}
		PickedThisPack.Add(CardId);
		Result.Cards.Add(Reveal);
	};

	for (const FDAEPackSlot& Slot : Pack.Slots)
	{
		const TArray<int32>* ChosenPool = nullptr;
		EDAECardRarity ChosenRarity = Slot.Rarity;

		if (Slot.Type == EDAEPackSlotType::AnyCard)
		{
			TArray<int32> Candidates = AllCardIds;
			if (Pack.bPreferUnowned)
			{
				Candidates.RemoveAll([this, bAddToCollection, &SimulatedCounts](int32 CardId)
				{
					const int32 Owned = bAddToCollection ? GetCount(CardId) : SimulatedCounts.FindRef(CardId);
					return MaxOwnedCopies > 0 && Owned >= MaxOwnedCopies;
				});
				if (Candidates.Num() == 0)
				{
					Candidates = AllCardIds;
				}
			}
			if (Candidates.Num() == 0)
			{
				// AllCardIds is only filled for all_cards packs; an AnyCard slot in
				// any other pack lands here, possibly after earlier slots added cards.
				RollBack();
				return Fail(TEXT("empty_pool"), TEXT("This booster pack has no cards to reveal."));
			}
			const int32 CardId = PickFromPool(Candidates);
			RevealCard(CardId, GetCardRarity(CardId));
			continue;
		}

		if (Slot.Type == EDAEPackSlotType::FixedRarity)
		{
			ChosenPool = Pack.FindPool(Slot.Rarity);
			if (!ChosenPool)
			{
				ChosenPool = FindFallbackPool(ChosenRarity);
			}
		}
		else // RarePlus
		{
			TArray<FDAERarityWeight> Weights = Slot.Weights.Num() > 0 ? Slot.Weights : Pack.RarePlusWeights;
			TArray<FDAERarityWeight> Usable;
			int32 TotalWeight = 0;
			for (const FDAERarityWeight& Weight : Weights)
			{
				if (Weight.Weight > 0 && Pack.FindPool(Weight.Rarity))
				{
					Usable.Add(Weight);
					TotalWeight += Weight.Weight;
				}
			}
			if (Usable.Num() > 0)
			{
				int32 Roll = Rng.RandRange(1, TotalWeight);
				for (const FDAERarityWeight& Weight : Usable)
				{
					if (Roll <= Weight.Weight)
					{
						ChosenRarity = Weight.Rarity;
						break;
					}
					Roll -= Weight.Weight;
				}
				ChosenPool = Pack.FindPool(ChosenRarity);
			}
			if (!ChosenPool)
			{
				ChosenPool = FindFallbackPool(ChosenRarity);
			}
		}

		if (!ChosenPool || ChosenPool->Num() == 0)
		{
			RollBack();
			return Fail(TEXT("empty_pool"), FString::Printf(TEXT("Booster pack '%s' has no cards for a slot."), *Pack.Id));
		}

		const int32 CardId = PickFromPool(*ChosenPool);
		if (CardId <= 0)
		{
			RollBack();
			return Fail(TEXT("empty_pool"), FString::Printf(TEXT("Booster pack '%s' has no cards for a slot."), *Pack.Id));
		}

		RevealCard(CardId, ChosenRarity);
	}

	Result.bSuccess = true;
	return Result;
}

int32 UDAInventorySubsystem::ResolveSeed(int32 Seed)
{
	if (Seed != 0)
	{
		return Seed;
	}
	static uint32 Counter = 0;
	const uint64 Cycles = FPlatformTime::Cycles64();
	const int32 Candidate = static_cast<int32>((Cycles ^ (static_cast<uint64>(++Counter) * 2654435761u)) & 0x7fffffff);
	// 0 means "pick a seed" at the public API boundary, so never report a
	// generated seed of 0 (the pack was still opened deterministically by the
	// FRandomStream, but callers rely on a non-zero Seed to replay a reveal).
	return Candidate != 0 ? Candidate : 1;
}

bool UDAInventorySubsystem::RemoveCardForAnte(int32 CardId, const FString& DuelId, const FString& Source)
{
	// Ante duel ids are stored in canonical folded form (like deck ids) so the
	// one-stake guard and every later lookup compare equal regardless of the
	// caller's casing; comparisons stay case-insensitive for legacy rows.
	const FString DuelKey = DAEconomy::NormalizeIdKey(DuelId);
	if (DuelKey.IsEmpty())
	{
		return false;
	}
	if (PendingAnte.ContainsByPredicate([&DuelKey](const FDAEAnteRecord& Record)
		{
			return Record.DuelId.Equals(DuelKey, ESearchCase::IgnoreCase);
		}))
	{
		// One ante stake per duel. Without this guard a retried call could
		// remove a second copy while ReturnAnteCard only returns one of them.
		return false;
	}
	if (RemoveCard(CardId, 1) != 1)
	{
		return false;
	}
	FDAEAnteRecord Record;
	Record.CardId = CardId;
	Record.DuelId = DuelKey;
	Record.Source = Source;
	PendingAnte.Add(Record);
	OnAnteChanged.Broadcast(PendingAnte.Num());
	return true;
}

bool UDAInventorySubsystem::ReturnAnteCard(const FString& DuelId)
{
	const FString DuelKey = DAEconomy::NormalizeIdKey(DuelId);
	const int32 Index = PendingAnte.IndexOfByPredicate([&DuelKey](const FDAEAnteRecord& Record)
	{
		return Record.DuelId.Equals(DuelKey, ESearchCase::IgnoreCase);
	});
	if (Index == INDEX_NONE)
	{
		return false;
	}
	if (AddCard(PendingAnte[Index].CardId, 1) != 1)
	{
		return false;
	}
	PendingAnte.RemoveAt(Index);
	OnAnteChanged.Broadcast(PendingAnte.Num());
	return true;
}

bool UDAInventorySubsystem::CommitAnteLoss(const FString& DuelId)
{
	const FString DuelKey = DAEconomy::NormalizeIdKey(DuelId);
	const int32 Removed = PendingAnte.RemoveAll([&DuelKey](const FDAEAnteRecord& Record)
	{
		return Record.DuelId.Equals(DuelKey, ESearchCase::IgnoreCase);
	});
	if (Removed > 0)
	{
		OnAnteChanged.Broadcast(PendingAnte.Num());
		return true;
	}
	return false;
}

int32 UDAInventorySubsystem::ReturnAllAnte()
{
	int32 Returned = 0;
	for (int32 Index = PendingAnte.Num() - 1; Index >= 0; --Index)
	{
		if (AddCard(PendingAnte[Index].CardId, 1) == 1)
		{
			PendingAnte.RemoveAt(Index);
			Returned++;
		}
	}
	if (Returned > 0)
	{
		OnAnteChanged.Broadcast(PendingAnte.Num());
	}
	return Returned;
}

void UDAInventorySubsystem::WriteStateFields(FJsonObject& Out) const
{
	Out.SetNumberField(TEXT("version"), 1);
	Out.SetNumberField(TEXT("max_owned_copies"), MaxOwnedCopies);

	const TSharedPtr<FJsonObject> CountsObject = MakeShared<FJsonObject>();
	for (const TPair<int32, int32>& Pair : Counts)
	{
		if (Pair.Value > 0)
		{
			CountsObject->SetNumberField(FString::FromInt(Pair.Key), Pair.Value);
		}
	}
	Out.SetObjectField(TEXT("counts"), CountsObject);

	TArray<TSharedPtr<FJsonValue>> AnteArray;
	for (const FDAEAnteRecord& Record : PendingAnte)
	{
		const TSharedPtr<FJsonObject> Entry = MakeShared<FJsonObject>();
		Entry->SetNumberField(TEXT("card_id"), Record.CardId);
		Entry->SetStringField(TEXT("duel_id"), Record.DuelId);
		Entry->SetStringField(TEXT("source"), Record.Source);
		AnteArray.Add(MakeShared<FJsonValueObject>(Entry));
	}
	Out.SetArrayField(TEXT("pending_ante"), AnteArray);
}

FString UDAInventorySubsystem::ExportStateJson() const
{
	const TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	WriteStateFields(*Root);
	return DAEconomyJson::WriteObject(Root);
}

bool UDAInventorySubsystem::ImportStateJson(const FString& Json, FString& OutError)
{
	TSharedPtr<FJsonValue> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid() || !Root->AsObject().IsValid())
	{
		OutError = TEXT("Inventory JSON could not be parsed.");
		return false;
	}
	return ApplyStateObject(*Root->AsObject(), OutError);
}

bool UDAInventorySubsystem::ApplyStateObject(const FJsonObject& Object, FString& OutError)
{
	const TSharedPtr<FJsonObject>* CountsObject = nullptr;
	if (!Object.TryGetObjectField(TEXT("counts"), CountsObject) || !CountsObject || !CountsObject->IsValid())
	{
		OutError = TEXT("Inventory JSON is missing the counts object.");
		return false;
	}

	TMap<int32, int32> NewCounts;
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*CountsObject)->Values)
	{
		int32 CardId = 0;
		int32 Count = 0;
		// Validation above guarantees these succeed; keep the defensive checks
		// so a future validator change cannot install a partial collection.
		if (!ParseCardCountKey(Pair.Key, CardId) || !ReadSaveCount(Pair.Value, Count))
		{
			OutError = TEXT("Inventory JSON contains an invalid count entry.");
			return false;
		}
		// The save schema allows an explicit zero (meaning "not owned"), while
		// the writer omits zero entries; treat both as absent.
		if (Count > 0)
		{
			NewCounts.Add(CardId, Count);
		}
	}

	TArray<FDAEAnteRecord> NewAnte;
	const TArray<TSharedPtr<FJsonValue>>* AnteArray = nullptr;
	if (Object.TryGetArrayField(TEXT("pending_ante"), AnteArray) && AnteArray)
	{
		for (const TSharedPtr<FJsonValue>& Value : *AnteArray)
		{
			const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!Entry.IsValid())
			{
				OutError = TEXT("Inventory JSON contains an invalid ante entry.");
				return false;
			}
			FDAEAnteRecord Record;
			if (!DAEconomyJson::TryReadCardId(Entry->TryGetField(TEXT("card_id")), Record.CardId))
			{
				OutError = TEXT("Inventory JSON contains an invalid ante card id.");
				return false;
			}
			Record.DuelId = DAEconomy::NormalizeIdKey(DAEconomyJson::ReadString(Entry, TEXT("duel_id")));
			Record.Source = DAEconomyJson::ReadString(Entry, TEXT("source"));
			if (Record.DuelId.IsEmpty())
			{
				OutError = TEXT("Inventory JSON contains an ante record without a duel id.");
				return false;
			}
			NewAnte.Add(MoveTemp(Record));
		}
	}

	int32 NewMax = MaxOwnedCopies;
	Object.TryGetNumberField(TEXT("max_owned_copies"), NewMax);

	Counts = MoveTemp(NewCounts);
	PendingAnte = MoveTemp(NewAnte);
	MaxOwnedCopies = FMath::Max(0, NewMax);
	OnInventoryReset.Broadcast();
	OnAnteChanged.Broadcast(PendingAnte.Num());
	return true;
}

FDAEInventorySaveData UDAInventorySubsystem::GetSaveData() const
{
	FDAEInventorySaveData Data;
	Data.Version = 1;
	Data.MaxOwnedCopies = MaxOwnedCopies;
	Data.Counts = Counts;
	Data.PendingAnte = PendingAnte;
	return Data;
}

bool UDAInventorySubsystem::ApplySaveData(const FDAEInventorySaveData& Data, FString& OutError)
{
	if (Data.Version < 0)
	{
		OutError = TEXT("Unknown inventory save version.");
		return false;
	}

	// Same explicit-zero contract as ImportStateJson: a zero count means
	// "not owned" and is treated as absent, so an all-zero struct payload
	// refreshes the trunk to empty instead of drifting into a rejection that
	// the JSON path would not produce.
	TMap<int32, int32> NewCounts;
	for (const TPair<int32, int32>& Pair : Data.Counts)
	{
		if (Pair.Key > 0 && Pair.Value > 0)
		{
			NewCounts.Add(Pair.Key, Pair.Value);
		}
	}

	Counts = MoveTemp(NewCounts);

	TArray<FDAEAnteRecord> NewAnte;
	NewAnte.Reserve(Data.PendingAnte.Num());
	for (const FDAEAnteRecord& Record : Data.PendingAnte)
	{
		// Normalize the duel id at entry so the one-stake guard and return
		// lookups match the runtime path (RemoveCardForAnte) everywhere.
		FDAEAnteRecord Normalized = Record;
		Normalized.DuelId = DAEconomy::NormalizeIdKey(Normalized.DuelId);
		if (Normalized.CardId > 0 && !Normalized.DuelId.IsEmpty())
		{
			NewAnte.Add(MoveTemp(Normalized));
		}
	}
	PendingAnte = MoveTemp(NewAnte);

	// 0 is a documented "unlimited" setting, so it must round-trip instead of
	// silently keeping the previous cap.
	MaxOwnedCopies = FMath::Max(0, Data.MaxOwnedCopies);
	OnInventoryReset.Broadcast();
	OnAnteChanged.Broadcast(PendingAnte.Num());
	return true;
}

void UDAInventorySubsystem::ScheduleSelfTest()
{
	UE_LOG(LogDuelAcademyIsland, Display, TEXT("DAEconomySelfTest: scheduled; waiting for the card database."));
	SelfTestTicker = FTSTicker::GetCoreTicker().AddTicker(
		FTickerDelegate::CreateUObject(this, &UDAInventorySubsystem::TickSelfTest), 1.0f);
}

bool UDAInventorySubsystem::TickSelfTest(float DeltaSeconds)
{
	SelfTestAttempts++;
	UGameInstance* GI = GetGameInstance();
	UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	UDAShopSubsystem* Shop = GI ? GI->GetSubsystem<UDAShopSubsystem>() : nullptr;
	UDADeckLogic* DeckLogic = GI ? GI->GetSubsystem<UDADeckLogic>() : nullptr;

	if (!Database || !Database->IsLoaded() || !Shop || !DeckLogic)
	{
		if (SelfTestAttempts > 30)
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("DAEconomySelfTest: timed out waiting for subsystems."));
			FPlatformMisc::RequestExitWithStatus(false, 1, TEXT("DAEconomySelfTest"));
			return false;
		}
		return true;
	}

	int32 Failures = 0;
	const FString Report = DAEconomyTests::Run(this, Shop, DeckLogic, Database, &Failures);
	UE_LOG(LogDuelAcademyIsland, Display, TEXT("%s"), *Report);
	UE_LOG(LogDuelAcademyIsland, Display, TEXT("DAEconomySelfTest: finished; requesting exit."));
	// The self-test harness treats the process exit code as authoritative, so
	// a failed check must not exit 0.
	FPlatformMisc::RequestExitWithStatus(false, Failures > 0 ? 1 : 0, TEXT("DAEconomySelfTest"));
	return false;
}

FString UDAInventorySubsystem::RunSelfTest()
{
	UGameInstance* GI = GetGameInstance();
	UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	UDAShopSubsystem* Shop = GI ? GI->GetSubsystem<UDAShopSubsystem>() : nullptr;
	UDADeckLogic* DeckLogic = GI ? GI->GetSubsystem<UDADeckLogic>() : nullptr;
	if (!Database || !Shop || !DeckLogic)
	{
		return TEXT("DA ECONOMY SELF-TEST: FAILED (subsystems unavailable)");
	}
	return DAEconomyTests::Run(this, Shop, DeckLogic, Database);
}
