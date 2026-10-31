#include "DAInventorySubsystem.h"

#include "DAEconomyJson.h"
#include "DAEconomyTests.h"
#include "DACardRecords.h"
#include "DADeckLogic.h"
#include "DAShopSubsystem.h"
#include "DAStorySubsystem.h"
#include "DuelAcademyIsland.h"

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
}

void UDAInventorySubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
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
	OutSection->SetNumberField(TEXT("version"), 1);
	OutSection->SetNumberField(TEXT("max_owned_copies"), MaxOwnedCopies);

	const TSharedPtr<FJsonObject> CountsObject = MakeShared<FJsonObject>();
	for (const TPair<int32, int32>& Pair : Counts)
	{
		if (Pair.Value > 0)
		{
			CountsObject->SetNumberField(FString::FromInt(Pair.Key), Pair.Value);
		}
	}
	OutSection->SetObjectField(TEXT("counts"), CountsObject);

	TArray<TSharedPtr<FJsonValue>> AnteArray;
	for (const FDAEAnteRecord& Record : PendingAnte)
	{
		const TSharedPtr<FJsonObject> Entry = MakeShared<FJsonObject>();
		Entry->SetNumberField(TEXT("card_id"), Record.CardId);
		Entry->SetStringField(TEXT("duel_id"), Record.DuelId);
		Entry->SetStringField(TEXT("source"), Record.Source);
		AnteArray.Add(MakeShared<FJsonValueObject>(Entry));
	}
	OutSection->SetArrayField(TEXT("pending_ante"), AnteArray);
	return true;
}

bool UDAInventorySubsystem::ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError)
{
	if (!InSection.IsValid())
	{
		OutError = TEXT("Inventory save section is missing.");
		return false;
	}
	return ImportStateJson(DAEconomyJson::WriteObject(InSection), OutError);
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
	if (!Object->TryGetNumberField(TEXT("max_owned_copies"), Value))
	{
		const TSharedPtr<FJsonObject>* RulesObject = nullptr;
		if (Object->TryGetObjectField(TEXT("rules"), RulesObject) && RulesObject && RulesObject->IsValid())
		{
			(*RulesObject)->TryGetNumberField(TEXT("max_owned_copies"), Value);
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

	int32& Owned = Counts.FindOrAdd(CardId);
	const int32 Space = MaxOwnedCopies > 0 ? FMath::Max(0, MaxOwnedCopies - Owned) : Count;
	const int32 Added = FMath::Min(Count, Space);
	if (Added <= 0)
	{
		return 0;
	}

	Owned += Added;
	OnCollectionChanged.Broadcast(CardId, Owned);
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
	return GetCount(CardId) + Count <= MaxOwnedCopies;
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
	int32 Total = 0;
	for (const TPair<int32, int32>& Pair : Counts)
	{
		Total += Pair.Value;
	}
	return Total;
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
		Stats.TotalCards += Pair.Value;

		const EDAECardRarity Rarity = GetCardRarity(Pair.Key);
		for (FDAERarityCount& Entry : Stats.RarityCounts)
		{
			if (Entry.Rarity == Rarity)
			{
				Entry.Count += Pair.Value;
				break;
			}
		}

		const FCardRecord* Card = Database ? Database->FindCard(Pair.Key) : nullptr;
		if (!Card)
		{
			continue;
		}
		if (!Card->CardType.IsEmpty())
		{
			Stats.TypeCounts.FindOrAdd(Card->CardType) += Pair.Value;
		}
		if (!Card->Attribute.IsEmpty() && Card->Attribute != TEXT("NONE"))
		{
			Stats.AttributeCounts.FindOrAdd(Card->Attribute) += Pair.Value;
		}
		if (!Card->MonsterType.IsEmpty() && Card->IsMonster())
		{
			Stats.MonsterTypeCounts.FindOrAdd(Card->MonsterType) += Pair.Value;
		}
	}

	Stats.CompletionPercent = Stats.CatalogSize > 0
		? (static_cast<float>(Stats.UniqueCards) * 100.f / static_cast<float>(Stats.CatalogSize))
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
		AllCardIds.Sort();
	}

	TSet<int32> PickedThisPack;
	TArray<int32> AddedCards;
	TMap<int32, int32> SimulatedCounts = Counts; // used only for previews

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
				return Fail(TEXT("empty_pool"), TEXT("This booster pack has no cards to reveal."));
			}
			const int32 CardId = PickFromPool(Candidates);
			ChosenRarity = GetCardRarity(CardId);
			ChosenPool = nullptr;

			// Add the card immediately; the common path below handles reveal bookkeeping.
			FDAEPackCardReveal Reveal;
			Reveal.CardId = CardId;
			Reveal.Rarity = ChosenRarity;
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
			// Roll back any cards already added so a bad pack never half-applies.
			for (int32 Index = AddedCards.Num() - 1; Index >= 0; --Index)
			{
				RemoveCard(AddedCards[Index], 1);
			}
			return Fail(TEXT("empty_pool"), FString::Printf(TEXT("Booster pack '%s' has no cards for a slot."), *Pack.Id));
		}

		const int32 CardId = PickFromPool(*ChosenPool);
		if (CardId <= 0)
		{
			for (int32 Index = AddedCards.Num() - 1; Index >= 0; --Index)
			{
				RemoveCard(AddedCards[Index], 1);
			}
			return Fail(TEXT("empty_pool"), FString::Printf(TEXT("Booster pack '%s' has no cards for a slot."), *Pack.Id));
		}

		FDAEPackCardReveal Reveal;
		Reveal.CardId = CardId;
		Reveal.Rarity = ChosenRarity;
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
	return static_cast<int32>((Cycles ^ (static_cast<uint64>(++Counter) * 2654435761u)) & 0x7fffffff);
}

bool UDAInventorySubsystem::RemoveCardForAnte(int32 CardId, const FString& DuelId, const FString& Source)
{
	if (DuelId.IsEmpty() || RemoveCard(CardId, 1) != 1)
	{
		return false;
	}
	FDAEAnteRecord Record;
	Record.CardId = CardId;
	Record.DuelId = DuelId;
	Record.Source = Source;
	PendingAnte.Add(Record);
	OnAnteChanged.Broadcast(PendingAnte.Num());
	return true;
}

bool UDAInventorySubsystem::ReturnAnteCard(const FString& DuelId)
{
	const int32 Index = PendingAnte.IndexOfByPredicate([&DuelId](const FDAEAnteRecord& Record)
	{
		return Record.DuelId.Equals(DuelId, ESearchCase::IgnoreCase);
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
	const int32 Removed = PendingAnte.RemoveAll([&DuelId](const FDAEAnteRecord& Record)
	{
		return Record.DuelId.Equals(DuelId, ESearchCase::IgnoreCase);
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

FString UDAInventorySubsystem::ExportStateJson() const
{
	const TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetNumberField(TEXT("version"), 1);
	Root->SetNumberField(TEXT("max_owned_copies"), MaxOwnedCopies);

	const TSharedPtr<FJsonObject> CountsObject = MakeShared<FJsonObject>();
	for (const TPair<int32, int32>& Pair : Counts)
	{
		if (Pair.Value > 0)
		{
			CountsObject->SetNumberField(FString::FromInt(Pair.Key), Pair.Value);
		}
	}
	Root->SetObjectField(TEXT("counts"), CountsObject);

	TArray<TSharedPtr<FJsonValue>> AnteArray;
	for (const FDAEAnteRecord& Record : PendingAnte)
	{
		const TSharedPtr<FJsonObject> Entry = MakeShared<FJsonObject>();
		Entry->SetNumberField(TEXT("card_id"), Record.CardId);
		Entry->SetStringField(TEXT("duel_id"), Record.DuelId);
		Entry->SetStringField(TEXT("source"), Record.Source);
		AnteArray.Add(MakeShared<FJsonValueObject>(Entry));
	}
	Root->SetArrayField(TEXT("pending_ante"), AnteArray);

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

	const TSharedPtr<FJsonObject> Object = Root->AsObject();
	const TSharedPtr<FJsonObject>* CountsObject = nullptr;
	if (!Object->TryGetObjectField(TEXT("counts"), CountsObject) || !CountsObject || !CountsObject->IsValid())
	{
		OutError = TEXT("Inventory JSON is missing the counts object.");
		return false;
	}

	TMap<int32, int32> NewCounts;
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*CountsObject)->Values)
	{
		const int32 CardId = FCString::Atoi(*Pair.Key);
		const int32 Count = Pair.Value.IsValid() ? static_cast<int32>(Pair.Value->AsNumber()) : 0;
		if (CardId > 0 && Count > 0)
		{
			NewCounts.Add(CardId, Count);
		}
	}

	TArray<FDAEAnteRecord> NewAnte;
	const TArray<TSharedPtr<FJsonValue>>* AnteArray = nullptr;
	if (Object->TryGetArrayField(TEXT("pending_ante"), AnteArray) && AnteArray)
	{
		for (const TSharedPtr<FJsonValue>& Value : *AnteArray)
		{
			const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!Entry.IsValid())
			{
				continue;
			}
			FDAEAnteRecord Record;
			Record.CardId = DAEconomyJson::ReadInt(Entry, TEXT("card_id"));
			Record.DuelId = DAEconomyJson::ReadString(Entry, TEXT("duel_id"));
			Record.Source = DAEconomyJson::ReadString(Entry, TEXT("source"));
			if (Record.CardId > 0)
			{
				NewAnte.Add(Record);
			}
		}
	}

	int32 NewMax = MaxOwnedCopies;
	Object->TryGetNumberField(TEXT("max_owned_copies"), NewMax);

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

	TMap<int32, int32> NewCounts;
	for (const TPair<int32, int32>& Pair : Data.Counts)
	{
		if (Pair.Key > 0 && Pair.Value > 0)
		{
			NewCounts.Add(Pair.Key, Pair.Value);
		}
	}
	if (Data.Counts.Num() > 0 && NewCounts.Num() == 0)
	{
		OutError = TEXT("Inventory save contains no valid card counts.");
		return false;
	}

	Counts = MoveTemp(NewCounts);
	PendingAnte = Data.PendingAnte;
	if (Data.MaxOwnedCopies > 0)
	{
		MaxOwnedCopies = Data.MaxOwnedCopies;
	}
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
			FPlatformMisc::RequestExit(false);
			return false;
		}
		return true;
	}

	const FString Report = DAEconomyTests::Run(this, Shop, DeckLogic, Database);
	UE_LOG(LogDuelAcademyIsland, Display, TEXT("%s"), *Report);
	UE_LOG(LogDuelAcademyIsland, Display, TEXT("DAEconomySelfTest: finished; requesting exit."));
	FPlatformMisc::RequestExit(false);
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
