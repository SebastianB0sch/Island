#include "DAShopSubsystem.h"

#include "DAEconomyJson.h"
#include "DAInventorySubsystem.h"
#include "DACardRecords.h"
#include "DuelAcademyIsland.h"

#include "Algo/Unique.h"
#include "Dom/JsonObject.h"
#include "Engine/GameInstance.h"
#include "Misc/Paths.h"
#include "Serialization/JsonWriter.h"

namespace
{
	const TCHAR* PacksPath()
	{
		return TEXT("Data/Shop/packs.json");
	}

	EDAEUnlockConditionType ParseUnlockType(const FString& Text)
	{
		const FString Key = Text.ToLower();
		if (Key == TEXT("start")) return EDAEUnlockConditionType::Start;
		if (Key == TEXT("tutorial")) return EDAEUnlockConditionType::Tutorial;
		if (Key == TEXT("event")) return EDAEUnlockConditionType::Event;
		if (Key == TEXT("counter")) return EDAEUnlockConditionType::Counter;
		if (Key == TEXT("title")) return EDAEUnlockConditionType::Title;
		if (Key == TEXT("dorm_changes")) return EDAEUnlockConditionType::DormChanges;
		if (Key == TEXT("visited_all_dorms")) return EDAEUnlockConditionType::VisitedAllDorms;
		if (Key == TEXT("pack_completion")) return EDAEUnlockConditionType::PackCompletion;
		if (Key == TEXT("collection_percent")) return EDAEUnlockConditionType::CollectionPercent;
		if (Key == TEXT("location_duels")) return EDAEUnlockConditionType::LocationDuels;
		if (Key == TEXT("month_at_least")) return EDAEUnlockConditionType::MonthAtLeast;
		if (Key == TEXT("flag")) return EDAEUnlockConditionType::Flag;
		return EDAEUnlockConditionType::Unknown;
	}

	EDAEPackSlotType ParseSlotType(const FString& Text)
	{
		const FString Key = Text.ToLower();
		if (Key == TEXT("fixed") || Key == TEXT("fixed_rarity")) return EDAEPackSlotType::FixedRarity;
		if (Key == TEXT("any") || Key == TEXT("any_card")) return EDAEPackSlotType::AnyCard;
		return EDAEPackSlotType::RarePlus;
	}

	FString ConditionText(const FDAEUnlockCondition& Condition)
	{
		if (!Condition.Description.IsEmpty())
		{
			return Condition.Description;
		}
		switch (Condition.Type)
		{
		case EDAEUnlockConditionType::Tutorial:          return FString::Printf(TEXT("Read the '%s' tutorial."), *Condition.Key);
		case EDAEUnlockConditionType::Event:             return FString::Printf(TEXT("Clear the '%s' event."), *Condition.Key);
		case EDAEUnlockConditionType::Counter:           return FString::Printf(TEXT("Reach %d %s."), Condition.Value, *Condition.Key);
		case EDAEUnlockConditionType::Title:             return FString::Printf(TEXT("Reach the '%s' title."), *Condition.Key);
		case EDAEUnlockConditionType::DormChanges:       return FString::Printf(TEXT("Change dorms %d time(s)."), Condition.Value);
		case EDAEUnlockConditionType::VisitedAllDorms:   return TEXT("Have been in every dorm at least once.");
		case EDAEUnlockConditionType::PackCompletion:    return FString::Printf(TEXT("Get %d%% of the '%s' pack."), Condition.Value, *Condition.Key);
		case EDAEUnlockConditionType::CollectionPercent: return FString::Printf(TEXT("Get %d%% collection rate."), Condition.Value);
		case EDAEUnlockConditionType::LocationDuels:     return FString::Printf(TEXT("Duel at '%s' %d time(s)."), *Condition.Key, Condition.Value);
		case EDAEUnlockConditionType::MonthAtLeast:      return FString::Printf(TEXT("Available from school month %d."), Condition.Value);
		case EDAEUnlockConditionType::Flag:              return FString::Printf(TEXT("Flag: %s"), *Condition.Key);
		case EDAEUnlockConditionType::Start:
		case EDAEUnlockConditionType::Unknown:
		default:                                         return TEXT("Unavailable.");
		}
	}
}

void UDAShopSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	FString Error;
	bLoaded = LoadPacks(Error);
	if (!bLoaded)
	{
		LoadError = Error;
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("Shop: %s"), *LoadError);
		return;
	}

	if (UGameInstance* GI = GetGameInstance())
	{
		if (UDASaveSubsystem* Save = GI->GetSubsystem<UDASaveSubsystem>())
		{
			Save->RegisterPayloadProvider(this);
		}
	}

	UE_LOG(LogDuelAcademyIsland, Log, TEXT("Shop: loaded %d booster packs."), Packs.Num());
}

bool UDAShopSubsystem::WriteSaveSection(TSharedPtr<FJsonObject>& OutSection) const
{
	if (!OutSection.IsValid())
	{
		OutSection = MakeShared<FJsonObject>();
	}
	OutSection->SetNumberField(TEXT("version"), 1);
	OutSection->SetNumberField(TEXT("cached_dp"), CachedDP);
	OutSection->SetBoolField(TEXT("internal_wallet"), bInternalWallet);

	const TSharedPtr<FJsonObject> LastObject = MakeShared<FJsonObject>();
	for (const TPair<FString, int32>& Pair : LastPurchaseDay)
	{
		LastObject->SetNumberField(Pair.Key, Pair.Value);
	}
	OutSection->SetObjectField(TEXT("last_purchase_day"), LastObject);

	const TSharedPtr<FJsonObject> CountObject = MakeShared<FJsonObject>();
	for (const TPair<FString, int32>& Pair : PurchaseCounts)
	{
		CountObject->SetNumberField(Pair.Key, Pair.Value);
	}
	OutSection->SetObjectField(TEXT("purchase_counts"), CountObject);
	return true;
}

bool UDAShopSubsystem::ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError)
{
	if (!InSection.IsValid())
	{
		OutError = TEXT("Shop save section is missing.");
		return false;
	}
	return ImportStateJson(DAEconomyJson::WriteObject(InSection), OutError);
}

bool UDAShopSubsystem::LoadPacks(FString& OutError)
{
	Packs.Reset();
	PackIndexById.Reset();

	const FString Path = FPaths::Combine(FPaths::ProjectContentDir(), PacksPath());
	TSharedPtr<FJsonValue> Root;
	if (!DAEconomyJson::LoadFile(Path, Root, OutError))
	{
		return false;
	}

	const TSharedPtr<FJsonObject> RootObject = Root->AsObject();
	if (!RootObject.IsValid())
	{
		OutError = TEXT("Shop packs.json root must be an object.");
		return false;
	}

	int32 DefaultDuplicateDP = 25;
	bool bDefaultAllowDuplicates = false;
	TArray<FDAERarityWeight> DefaultRarePlusWeights;
	const TSharedPtr<FJsonObject>* DefaultsObject = nullptr;
	if (RootObject->TryGetObjectField(TEXT("defaults"), DefaultsObject) && DefaultsObject && DefaultsObject->IsValid())
	{
		DefaultDuplicateDP = DAEconomyJson::ReadInt(*DefaultsObject, TEXT("duplicate_dp_per_card"), DefaultDuplicateDP);
		bDefaultAllowDuplicates = DAEconomyJson::ReadBool(*DefaultsObject, TEXT("allow_duplicates_in_pack"), bDefaultAllowDuplicates);

		const TArray<TSharedPtr<FJsonValue>>* WeightArray = nullptr;
		if ((*DefaultsObject)->TryGetArrayField(TEXT("rare_plus_weights"), WeightArray) && WeightArray)
		{
			for (const TSharedPtr<FJsonValue>& Value : *WeightArray)
			{
				const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
				if (!Entry.IsValid())
				{
					continue;
				}
				EDAECardRarity Rarity;
				if (!DAEconomyJson::ParseRarity(DAEconomyJson::ReadString(Entry, TEXT("rarity")), Rarity))
				{
					continue;
				}
				FDAERarityWeight Weight;
				Weight.Rarity = Rarity;
				Weight.Weight = DAEconomyJson::ReadInt(Entry, TEXT("weight"), 1);
				if (Weight.Weight > 0)
				{
					DefaultRarePlusWeights.Add(Weight);
				}
			}
		}
	}
	if (DefaultRarePlusWeights.Num() == 0)
	{
		FDAERarityWeight Rare;
		Rare.Rarity = EDAECardRarity::Rare;
		Rare.Weight = 70;
		DefaultRarePlusWeights.Add(Rare);
		FDAERarityWeight Super;
		Super.Rarity = EDAECardRarity::SuperRare;
		Super.Weight = 22;
		DefaultRarePlusWeights.Add(Super);
		FDAERarityWeight Ultra;
		Ultra.Rarity = EDAECardRarity::UltraRare;
		Ultra.Weight = 6;
		DefaultRarePlusWeights.Add(Ultra);
		FDAERarityWeight Secret;
		Secret.Rarity = EDAECardRarity::SecretRare;
		Secret.Weight = 2;
		DefaultRarePlusWeights.Add(Secret);
	}

	const TArray<TSharedPtr<FJsonValue>>* PackArray = nullptr;
	if (!RootObject->TryGetArrayField(TEXT("packs"), PackArray) || !PackArray)
	{
		OutError = TEXT("Shop packs.json has no packs array.");
		return false;
	}

	const FString DefaultStatus = DAEconomyJson::ReadString(RootObject, TEXT("canon_status"), TEXT("provisional"));

	for (const TSharedPtr<FJsonValue>& Value : *PackArray)
	{
		const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
		if (!Entry.IsValid())
		{
			continue;
		}

		FDAEPackDef Pack;
		Pack.Id = DAEconomyJson::ReadString(Entry, TEXT("id"));
		Pack.Name = DAEconomyJson::ReadString(Entry, TEXT("name"));
		Pack.Category = DAEconomyJson::ReadString(Entry, TEXT("category"));
		Pack.Description = DAEconomyJson::ReadString(Entry, TEXT("description"));
		Pack.Source = DAEconomyJson::ReadString(Entry, TEXT("source"));
		Pack.Price = DAEconomyJson::ReadInt(Entry, TEXT("price"));
		Pack.PackSize = DAEconomyJson::ReadInt(Entry, TEXT("pack_size"), 5);
		Pack.RestockDays = DAEconomyJson::ReadInt(Entry, TEXT("restock_days"), 7);
		Pack.PurchaseLimit = FMath::Max(1, DAEconomyJson::ReadInt(Entry, TEXT("purchase_limit"), 1));
		Pack.Stock = FMath::Max(0, DAEconomyJson::ReadInt(Entry, TEXT("stock"), 0));
		Pack.DuplicateDPPerCard = DAEconomyJson::ReadInt(Entry, TEXT("duplicate_dp_per_card"), DefaultDuplicateDP);
		Pack.bAllCards = DAEconomyJson::ReadBool(Entry, TEXT("all_cards"));
		Pack.bPreferUnowned = DAEconomyJson::ReadBool(Entry, TEXT("prefer_unowned"));
		Pack.bAllowDuplicatesInPack = DAEconomyJson::ReadBool(Entry, TEXT("allow_duplicates_in_pack"), bDefaultAllowDuplicates);
		Pack.RarePlusWeights = DefaultRarePlusWeights;
		Pack.bProvisional = !DAEconomyJson::ReadString(Entry, TEXT("canon_status"), DefaultStatus).Equals(TEXT("final"), ESearchCase::IgnoreCase);

		const TArray<TSharedPtr<FJsonValue>>* SlotArray = nullptr;
		if (Entry->TryGetArrayField(TEXT("slots"), SlotArray) && SlotArray)
		{
			for (const TSharedPtr<FJsonValue>& SlotValue : *SlotArray)
			{
				const TSharedPtr<FJsonObject> SlotObject = SlotValue.IsValid() ? SlotValue->AsObject() : nullptr;
				if (!SlotObject.IsValid())
				{
					continue;
				}
				FDAEPackSlot Slot;
				Slot.Type = ParseSlotType(DAEconomyJson::ReadString(SlotObject, TEXT("type"), TEXT("rare_plus")));
				EDAECardRarity Rarity;
				if (DAEconomyJson::ParseRarity(DAEconomyJson::ReadString(SlotObject, TEXT("rarity")), Rarity))
				{
					Slot.Rarity = Rarity;
				}
				const TArray<TSharedPtr<FJsonValue>>* Weights = nullptr;
				if (SlotObject->TryGetArrayField(TEXT("weights"), Weights) && Weights)
				{
					for (const TSharedPtr<FJsonValue>& WeightValue : *Weights)
					{
						const TSharedPtr<FJsonObject> WeightObject = WeightValue.IsValid() ? WeightValue->AsObject() : nullptr;
						if (!WeightObject.IsValid())
						{
							continue;
						}
						FDAERarityWeight Weight;
						if (DAEconomyJson::ParseRarity(DAEconomyJson::ReadString(WeightObject, TEXT("rarity")), Weight.Rarity))
						{
							Weight.Weight = DAEconomyJson::ReadInt(WeightObject, TEXT("weight"), 1);
							if (Weight.Weight > 0)
							{
								Slot.Weights.Add(Weight);
							}
						}
					}
				}
				Pack.Slots.Add(Slot);
			}
		}

		// Tolerate hand-authored packs that only set pack_size.
		if (Pack.Slots.Num() != Pack.PackSize)
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Shop: pack '%s' has %d slots for pack_size %d; regenerating slots."),
				*Pack.Id, Pack.Slots.Num(), Pack.PackSize);
			Pack.Slots.Reset();
			for (int32 SlotIndex = 0; SlotIndex < Pack.PackSize; ++SlotIndex)
			{
				FDAEPackSlot Slot;
				Slot.Type = SlotIndex >= Pack.PackSize - 2 ? EDAEPackSlotType::RarePlus : EDAEPackSlotType::FixedRarity;
				Slot.Rarity = EDAECardRarity::Common;
				Pack.Slots.Add(Slot);
			}
		}

		const TArray<TSharedPtr<FJsonValue>>* PoolArray = nullptr;
		if (Entry->TryGetArrayField(TEXT("pools"), PoolArray) && PoolArray)
		{
			for (const TSharedPtr<FJsonValue>& PoolValue : *PoolArray)
			{
				const TSharedPtr<FJsonObject> PoolObject = PoolValue.IsValid() ? PoolValue->AsObject() : nullptr;
				if (!PoolObject.IsValid())
				{
					continue;
				}
				FDAERarityPool Pool;
				if (!DAEconomyJson::ParseRarity(DAEconomyJson::ReadString(PoolObject, TEXT("rarity")), Pool.Rarity))
				{
					continue;
				}
				Pool.Cards = DAEconomyJson::ReadIntArray(PoolObject, TEXT("cards"));
				Pool.Cards.Sort();
				Pool.Cards.SetNum(Algo::Unique(Pool.Cards));
				Pack.Pools.Add(MoveTemp(Pool));
			}
		}

		const TSharedPtr<FJsonObject>* UnlockObject = nullptr;
		if (Entry->TryGetObjectField(TEXT("unlock"), UnlockObject) && UnlockObject && UnlockObject->IsValid())
		{
			Pack.UnlockDescription = DAEconomyJson::ReadString(*UnlockObject, TEXT("description"));
			const TArray<TSharedPtr<FJsonValue>>* Conditions = nullptr;
			if ((*UnlockObject)->TryGetArrayField(TEXT("conditions"), Conditions) && Conditions)
			{
				for (const TSharedPtr<FJsonValue>& ConditionValue : *Conditions)
				{
					const TSharedPtr<FJsonObject> ConditionObject = ConditionValue.IsValid() ? ConditionValue->AsObject() : nullptr;
					if (!ConditionObject.IsValid())
					{
						continue;
					}
					FDAEUnlockCondition Condition;
					Condition.Type = ParseUnlockType(DAEconomyJson::ReadString(ConditionObject, TEXT("type")));
					Condition.Key = DAEconomyJson::ReadString(ConditionObject, TEXT("key"));
					Condition.Value = DAEconomyJson::ReadInt(ConditionObject, TEXT("value"));
					Condition.Description = DAEconomyJson::ReadString(ConditionObject, TEXT("description"));
					Pack.UnlockConditions.Add(Condition);
				}
			}
		}

		if (Pack.Id.IsEmpty() || Pack.Name.IsEmpty())
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Shop: skipping a pack with an empty id/name."));
			continue;
		}
		if (PackIndexById.Contains(Pack.Id))
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("Shop: duplicate pack id '%s' skipped."), *Pack.Id);
			continue;
		}

		PackIndexById.Add(Pack.Id, Packs.Num());
		Packs.Add(MoveTemp(Pack));
	}

	if (Packs.Num() == 0)
	{
		OutError = TEXT("Shop packs.json produced no valid packs.");
		return false;
	}
	return true;
}

const FDAEPackDef* UDAShopSubsystem::FindPack(const FString& PackId) const
{
	const int32* Index = PackIndexById.Find(PackId);
	return Index && Packs.IsValidIndex(*Index) ? &Packs[*Index] : nullptr;
}

bool UDAShopSubsystem::GetPackDef(const FString& PackId, FDAEPackDef& OutPack) const
{
	if (const FDAEPackDef* Pack = FindPack(PackId))
	{
		OutPack = *Pack;
		return true;
	}
	return false;
}

FDAEUnlockContext UDAShopSubsystem::GetUnlockContext() const
{
	if (UnlockContextProvider)
	{
		return UnlockContextProvider();
	}
	return UnlockContext;
}

void UDAShopSubsystem::SetUnlockContextProvider(TFunction<FDAEUnlockContext()> InProvider)
{
	UnlockContextProvider = MoveTemp(InProvider);
	RefreshUnlocks();
}

void UDAShopSubsystem::SetUnlockContext(const FDAEUnlockContext& NewContext)
{
	UnlockContextProvider = nullptr;
	UnlockContext = NewContext;
	RefreshUnlocks();
}

FDAEUnlockContext UDAShopSubsystem::GetUnlockContextCopy() const
{
	return GetUnlockContext();
}

void UDAShopSubsystem::RefreshUnlocks()
{
	OnShopChanged.Broadcast();
}

void UDAShopSubsystem::SetWalletHandlers(
	TFunction<int32()> InGetDP,
	TFunction<bool(int32)> InSpendDP,
	TFunction<void(int32, const FString&)> InCreditDP)
{
	if (!InGetDP || !InSpendDP)
	{
		ClearWalletHandlers();
		return;
	}
	GetDPHandler = MoveTemp(InGetDP);
	SpendDPHandler = MoveTemp(InSpendDP);
	CreditDPHandler = MoveTemp(InCreditDP);
	bInternalWallet = false;
}

void UDAShopSubsystem::ClearWalletHandlers()
{
	GetDPHandler = nullptr;
	SpendDPHandler = nullptr;
	CreditDPHandler = nullptr;
	bInternalWallet = true;
}

int32 UDAShopSubsystem::GetDP() const
{
	if (GetDPHandler)
	{
		return GetDPHandler();
	}
	return CachedDP;
}

void UDAShopSubsystem::SetDebugDP(int32 NewDP)
{
	ClearWalletHandlers();
	CachedDP = FMath::Max(0, NewDP);
	OnShopChanged.Broadcast();
}

bool UDAShopSubsystem::SpendDP(int32 Amount, const FString& Reason)
{
	if (Amount <= 0)
	{
		return true;
	}
	if (SpendDPHandler)
	{
		return SpendDPHandler(Amount);
	}
	if (CachedDP < Amount)
	{
		return false;
	}
	CachedDP -= Amount;
	return true;
}

void UDAShopSubsystem::CreditDP(int32 Amount, const FString& Reason)
{
	if (Amount <= 0)
	{
		return;
	}
	if (CreditDPHandler)
	{
		CreditDPHandler(Amount, Reason);
		return;
	}
	CachedDP += Amount;
}

bool UDAShopSubsystem::IsConditionMet(const FDAEUnlockCondition& Condition, FString& OutReason) const
{
	const FDAEUnlockContext Context = GetUnlockContext();
	switch (Condition.Type)
	{
	case EDAEUnlockConditionType::Start:
		return true;
	case EDAEUnlockConditionType::Tutorial:
		return Context.HasTutorial(Condition.Key);
	case EDAEUnlockConditionType::Event:
		return Context.HasEvent(Condition.Key);
	case EDAEUnlockConditionType::Counter:
		return Context.Counters.FindRef(Condition.Key) >= Condition.Value;
	case EDAEUnlockConditionType::Title:
		return Context.HasTitle(Condition.Key);
	case EDAEUnlockConditionType::DormChanges:
		return Context.DormChanges >= Condition.Value;
	case EDAEUnlockConditionType::VisitedAllDorms:
		return Context.HasVisitedAllDorms();
	case EDAEUnlockConditionType::PackCompletion:
	{
		if (Context.PackCompletion.FindRef(Condition.Key) >= static_cast<float>(Condition.Value))
		{
			return true;
		}
		return GetPackCompletionPercent(Condition.Key) >= static_cast<float>(Condition.Value);
	}
	case EDAEUnlockConditionType::CollectionPercent:
	{
		if (Context.CollectionPercent >= static_cast<float>(Condition.Value))
		{
			return true;
		}
		return GetCollectionPercent() >= static_cast<float>(Condition.Value);
	}
	case EDAEUnlockConditionType::LocationDuels:
		return Context.LocationDuelCounts.FindRef(Condition.Key) >= Condition.Value;
	case EDAEUnlockConditionType::MonthAtLeast:
		return Context.MonthIndex >= Condition.Value;
	case EDAEUnlockConditionType::Flag:
		return Context.HasFlag(Condition.Key);
	case EDAEUnlockConditionType::Unknown:
	default:
		OutReason = ConditionText(Condition);
		return false;
	}
}

bool UDAShopSubsystem::EvaluateUnlock(const FDAEPackDef& Pack, FString& OutReason) const
{
	for (const FDAEUnlockCondition& Condition : Pack.UnlockConditions)
	{
		FString ConditionReason;
		if (!IsConditionMet(Condition, ConditionReason))
		{
			OutReason = !Pack.UnlockDescription.IsEmpty() ? Pack.UnlockDescription : ConditionText(Condition);
			return false;
		}
	}
	OutReason.Reset();
	return true;
}

FString UDAShopSubsystem::GetUnlockReason(const FString& PackId) const
{
	const FDAEPackDef* Pack = FindPack(PackId);
	if (!Pack)
	{
		return TEXT("Unknown booster pack.");
	}
	FString Reason;
	if (EvaluateUnlock(*Pack, Reason))
	{
		return TEXT("Available.");
	}
	return Reason;
}

float UDAShopSubsystem::GetCollectionPercent() const
{
	UGameInstance* GI = GetGameInstance();
	UDAInventorySubsystem* Inventory = GI ? GI->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	if (Inventory)
	{
		return Inventory->GetCollectionStats().CompletionPercent;
	}
	return FMath::Clamp(GetUnlockContext().CollectionPercent, 0.f, 100.f);
}

float UDAShopSubsystem::GetPackCompletionPercent(const FString& PackId) const
{
	const FDAEPackDef* Pack = FindPack(PackId);
	if (!Pack)
	{
		return 0.f;
	}

	UGameInstance* GI = GetGameInstance();
	UDAInventorySubsystem* Inventory = GI ? GI->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	if (!Inventory)
	{
		return FMath::Clamp(GetUnlockContext().PackCompletion.FindRef(PackId), 0.f, 100.f);
	}

	if (Pack->bAllCards)
	{
		return Inventory->GetCollectionStats().CompletionPercent;
	}

	TSet<int32> UniqueCards;
	for (const FDAERarityPool& Pool : Pack->Pools)
	{
		for (const int32 CardId : Pool.Cards)
		{
			UniqueCards.Add(CardId);
		}
	}
	if (UniqueCards.Num() == 0)
	{
		return 0.f;
	}
	int32 Owned = 0;
	for (const int32 CardId : UniqueCards)
	{
		if (Inventory->HasCard(CardId, 1))
		{
			Owned++;
		}
	}
	return static_cast<float>(Owned) * 100.f / static_cast<float>(UniqueCards.Num());
}

int32 UDAShopSubsystem::GetLastPurchaseDay(const FString& PackId) const
{
	const int32* Day = LastPurchaseDay.Find(PackId);
	return Day ? *Day : -1;
}

int32 UDAShopSubsystem::GetNextAvailableDay(const FString& PackId) const
{
	const FDAEPackDef* Pack = FindPack(PackId);
	const int32 Last = GetLastPurchaseDay(PackId);
	if (!Pack || Last < 0)
	{
		return -1;
	}
	return Last + FMath::Max(1, Pack->RestockDays);
}

int32 UDAShopSubsystem::GetPurchaseCount(const FString& PackId) const
{
	return PurchaseCounts.FindRef(PackId);
}

int32 UDAShopSubsystem::GetRemainingStock(const FString& PackId) const
{
	const FDAEPackDef* Pack = FindPack(PackId);
	if (!Pack || Pack->Stock <= 0)
	{
		return -1;
	}
	return FMath::Max(0, Pack->Stock - GetPurchaseCount(PackId));
}

bool UDAShopSubsystem::CheckPurchase(const FString& PackId, FString& OutReason, EDAEPurchaseBlock& OutBlock) const
{
	OutReason.Reset();
	OutBlock = EDAEPurchaseBlock::None;

	const FDAEPackDef* Pack = FindPack(PackId);
	if (!Pack)
	{
		OutBlock = EDAEPurchaseBlock::PackNotFound;
		OutReason = TEXT("Unknown booster pack.");
		return false;
	}
	if (!Pack->HasAnyPool())
	{
		OutBlock = EDAEPurchaseBlock::InvalidPack;
		OutReason = TEXT("This booster pack has no cards in its pool.");
		return false;
	}
	FString UnlockReason;
	if (!EvaluateUnlock(*Pack, UnlockReason))
	{
		OutBlock = EDAEPurchaseBlock::Locked;
		OutReason = UnlockReason;
		return false;
	}

	UGameInstance* GI = GetGameInstance();
	UDAInventorySubsystem* Inventory = GI ? GI->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	if (!Inventory)
	{
		OutBlock = EDAEPurchaseBlock::NoInventory;
		OutReason = TEXT("The card trunk is not available.");
		return false;
	}

	if (Pack->Stock > 0 && PurchaseCounts.FindRef(PackId) >= Pack->Stock)
	{
		OutBlock = EDAEPurchaseBlock::SoldOut;
		OutReason = TEXT("This booster pack is sold out.");
		return false;
	}

	const int32 DP = GetDP();
	if (DP < Pack->Price)
	{
		OutBlock = EDAEPurchaseBlock::InsufficientDP;
		OutReason = FString::Printf(TEXT("You need %d more DP."), Pack->Price - DP);
		return false;
	}

	const FDAEUnlockContext Context = GetUnlockContext();
	const int32 LastDay = GetLastPurchaseDay(PackId);
	if (Context.DayNumber >= 0 && LastDay >= 0)
	{
		const int32 RestockDays = FMath::Max(1, Pack->RestockDays);
		if (Context.DayNumber - LastDay < RestockDays)
		{
			OutBlock = EDAEPurchaseBlock::Restocking;
			OutReason = FString::Printf(TEXT("Sold out. Restocks in %d day(s)."), RestockDays - (Context.DayNumber - LastDay));
			return false;
		}
	}

	return true;
}

bool UDAShopSubsystem::CanPurchase(const FString& PackId, FString& OutReason) const
{
	EDAEPurchaseBlock Block;
	return CheckPurchase(PackId, OutReason, Block);
}

FDAEPackView UDAShopSubsystem::MakeView(const FDAEPackDef& Pack) const
{
	FDAEPackView View;
	View.PackId = Pack.Id;
	View.Name = Pack.Name;
	View.Category = Pack.Category;
	View.Price = Pack.Price;
	View.PackSize = Pack.PackSize;
	View.RestockDays = Pack.RestockDays;
	View.LastPurchaseDay = GetLastPurchaseDay(Pack.Id);

	FString Reason;
	EDAEPurchaseBlock Block;
	View.bCanPurchase = CheckPurchase(Pack.Id, Reason, Block);
	View.Block = Block;
	View.bUnlocked = Block != EDAEPurchaseBlock::Locked &&
		Block != EDAEPurchaseBlock::PackNotFound &&
		Block != EDAEPurchaseBlock::InvalidPack;
	View.UnlockReason = View.bUnlocked ? TEXT("Available.") : Reason;
	View.StatusText = View.bCanPurchase
		? TEXT("Available")
		: (View.bUnlocked ? Reason : View.UnlockReason);

	const int32 Last = View.LastPurchaseDay;
	if (Last >= 0)
	{
		View.NextAvailableDay = Last + FMath::Max(1, Pack.RestockDays);
	}
	return View;
}

TArray<FDAEPackView> UDAShopSubsystem::GetCatalogue() const
{
	TArray<FDAEPackView> Views;
	Views.Reserve(Packs.Num());
	for (const FDAEPackDef& Pack : Packs)
	{
		Views.Add(MakeView(Pack));
	}
	return Views;
}

TArray<FDAEPackView> UDAShopSubsystem::GetVisiblePacks() const
{
	TArray<FDAEPackView> Views;
	for (const FDAEPackDef& Pack : Packs)
	{
		FDAEPackView View = MakeView(Pack);
		if (View.bUnlocked)
		{
			Views.Add(MoveTemp(View));
		}
	}
	return Views;
}

bool UDAShopSubsystem::GetPackView(const FString& PackId, FDAEPackView& OutView) const
{
	const FDAEPackDef* Pack = FindPack(PackId);
	if (!Pack)
	{
		return false;
	}
	OutView = MakeView(*Pack);
	return true;
}

void UDAShopSubsystem::MarkPurchased(const FString& PackId)
{
	const FDAEUnlockContext Context = GetUnlockContext();
	if (Context.DayNumber >= 0)
	{
		LastPurchaseDay.Add(PackId, Context.DayNumber);
	}
	PurchaseCounts.FindOrAdd(PackId)++;
}

bool UDAShopSubsystem::PurchasePack(const FString& PackId, int32 Seed, FDAEPurchaseResult& OutResult)
{
	OutResult = FDAEPurchaseResult();
	OutResult.PackId = PackId;
	OutResult.DPBefore = GetDP();
	OutResult.DPAfter = OutResult.DPBefore;

	const FDAEPackDef* Pack = FindPack(PackId);
	if (Pack)
	{
		OutResult.Price = Pack->Price;
	}

	FString Reason;
	EDAEPurchaseBlock Block = EDAEPurchaseBlock::None;
	if (!CheckPurchase(PackId, Reason, Block))
	{
		OutResult.Block = Block;
		OutResult.ErrorCode = TEXT("purchase_blocked");
		OutResult.ErrorMessage = Reason;
		return false;
	}

	if (!SpendDP(Pack->Price, FString::Printf(TEXT("pack:%s"), *PackId)))
	{
		OutResult.Block = EDAEPurchaseBlock::WalletRejected;
		OutResult.ErrorCode = TEXT("dp_deduction_failed");
		OutResult.ErrorMessage = TEXT("The DP payment was rejected.");
		OutResult.DPAfter = GetDP();
		return false;
	}

	UGameInstance* GI = GetGameInstance();
	UDAInventorySubsystem* Inventory = GI ? GI->GetSubsystem<UDAInventorySubsystem>() : nullptr;
	if (!Inventory)
	{
		CreditDP(Pack->Price, TEXT("refund:no_inventory"));
		OutResult.Block = EDAEPurchaseBlock::NoInventory;
		OutResult.ErrorCode = TEXT("inventory_unavailable");
		OutResult.ErrorMessage = TEXT("The card trunk is not available; your DP was refunded.");
		OutResult.DPAfter = GetDP();
		return false;
	}

	const FDAEPackOpenResult OpenResult = Inventory->OpenPackDefinition(*Pack, Seed, true);
	if (!OpenResult.bSuccess)
	{
		CreditDP(Pack->Price, TEXT("refund:pack_open_failed"));
		OutResult.Block = EDAEPurchaseBlock::OpenFailed;
		OutResult.ErrorCode = OpenResult.ErrorCode;
		OutResult.ErrorMessage = OpenResult.ErrorMessage;
		OutResult.DPAfter = GetDP();
		return false;
	}

	if (OpenResult.DPFromDuplicates > 0)
	{
		CreditDP(OpenResult.DPFromDuplicates, TEXT("duplicate_compensation"));
	}

	MarkPurchased(PackId);

	OutResult.bPurchased = true;
	OutResult.Block = EDAEPurchaseBlock::None;
	OutResult.Open = OpenResult;
	OutResult.Open.DPBefore = OutResult.DPBefore;
	OutResult.DPAfter = GetDP();
	OutResult.Open.DPAfter = OutResult.DPAfter;

	OnPackPurchased.Broadcast(OutResult, OutResult.DPAfter);
	OnShopChanged.Broadcast();
	return true;
}

TArray<FString> UDAShopSubsystem::ValidateCatalogue() const
{
	TArray<FString> Issues;
	if (Packs.Num() != 48)
	{
		Issues.Add(FString::Printf(TEXT("Expected 48 packs, found %d."), Packs.Num()));
	}

	UGameInstance* GI = GetGameInstance();
	const UCardDatabaseSubsystem* Database = GI ? GI->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
	TSet<int32> Obtainable;
	TSet<FString> SeenIds;
	static const TSet<FString> KnownCategories = {
		TEXT("Basic"),
		TEXT("Medium"),
		TEXT("Special"),
		TEXT("Attribute"),
		TEXT("Type"),
		TEXT("Spell/Trap"),
		TEXT("Expert")
	};

	for (const FDAEPackDef& Pack : Packs)
	{
		if (Pack.Id.IsEmpty()) Issues.Add(TEXT("A pack has an empty id."));
		if (Pack.Name.IsEmpty()) Issues.Add(FString::Printf(TEXT("Pack '%s' has an empty name."), *Pack.Id));
		if (SeenIds.Contains(Pack.Id)) Issues.Add(FString::Printf(TEXT("Duplicate pack id '%s'."), *Pack.Id));
		SeenIds.Add(Pack.Id);
		if (Pack.Category.IsEmpty() || !KnownCategories.Contains(Pack.Category))
		{
			Issues.Add(FString::Printf(TEXT("Pack '%s' references missing set/category '%s'."), *Pack.Id, *Pack.Category));
		}
		if (Pack.Source.IsEmpty()) Issues.Add(FString::Printf(TEXT("Pack '%s' has no data source."), *Pack.Id));
		if (Pack.Price <= 0) Issues.Add(FString::Printf(TEXT("Pack '%s' has a non-positive price."), *Pack.Id));
		if (Pack.PackSize <= 0) Issues.Add(FString::Printf(TEXT("Pack '%s' has a non-positive pack size."), *Pack.Id));
		if (Pack.RestockDays <= 0) Issues.Add(FString::Printf(TEXT("Pack '%s' has a non-positive restock period."), *Pack.Id));
		if (Pack.PurchaseLimit <= 0) Issues.Add(FString::Printf(TEXT("Pack '%s' has a non-positive purchase limit."), *Pack.Id));
		if (Pack.Stock < 0) Issues.Add(FString::Printf(TEXT("Pack '%s' has negative stock."), *Pack.Id));
		if (Pack.DuplicateDPPerCard < 0) Issues.Add(FString::Printf(TEXT("Pack '%s' has negative duplicate DP."), *Pack.Id));
		if (Pack.Slots.Num() != Pack.PackSize) Issues.Add(FString::Printf(TEXT("Pack '%s' slot count %d != pack size %d."), *Pack.Id, Pack.Slots.Num(), Pack.PackSize));
		if (!Pack.HasAnyPool()) Issues.Add(FString::Printf(TEXT("Pack '%s' has no pools."), *Pack.Id));
		if (Pack.bAllCards && Pack.Pools.Num() == 0)
		{
			Issues.Add(FString::Printf(TEXT("Pack '%s' is all-cards but has no materialised pool."), *Pack.Id));
		}
		if (Pack.UnlockDescription.IsEmpty()) Issues.Add(FString::Printf(TEXT("Pack '%s' has no unlock description."), *Pack.Id));
		if (Pack.UnlockConditions.Num() == 0) Issues.Add(FString::Printf(TEXT("Pack '%s' has no unlock conditions."), *Pack.Id));

		int32 DefaultWeightTotal = 0;
		for (const FDAERarityWeight& Weight : Pack.RarePlusWeights)
		{
			if (Weight.Weight <= 0)
			{
				Issues.Add(FString::Printf(TEXT("Pack '%s' has a non-positive default rare-plus weight."), *Pack.Id));
			}
			else
			{
				DefaultWeightTotal += Weight.Weight;
			}
		}
		if (DefaultWeightTotal != 100)
		{
			Issues.Add(FString::Printf(TEXT("Pack '%s' default rare-plus weights sum to %d (expected 100)."), *Pack.Id, DefaultWeightTotal));
		}

		for (int32 SlotIndex = 0; SlotIndex < Pack.Slots.Num(); ++SlotIndex)
		{
			const FDAEPackSlot& Slot = Pack.Slots[SlotIndex];
			if (Slot.Type == EDAEPackSlotType::FixedRarity)
			{
				if (!Pack.FindPool(Slot.Rarity))
				{
					Issues.Add(FString::Printf(TEXT("Pack '%s' slot %d has no %s pool."), *Pack.Id, SlotIndex, *DAEconomy::RarityToString(Slot.Rarity)));
				}
			}
			else if (Slot.Type == EDAEPackSlotType::RarePlus)
			{
				const TArray<FDAERarityWeight>& Weights = Slot.Weights.Num() > 0 ? Slot.Weights : Pack.RarePlusWeights;
				int32 TotalWeight = 0;
				bool bHasUsablePool = false;
				for (const FDAERarityWeight& Weight : Weights)
				{
					if (Weight.Weight <= 0)
					{
						Issues.Add(FString::Printf(TEXT("Pack '%s' slot %d has a non-positive rare-plus weight."), *Pack.Id, SlotIndex));
						continue;
					}
					TotalWeight += Weight.Weight;
					if (Pack.FindPool(Weight.Rarity))
					{
						bHasUsablePool = true;
					}
				}
				if (TotalWeight <= 0)
				{
					Issues.Add(FString::Printf(TEXT("Pack '%s' slot %d has no usable rare-plus weight."), *Pack.Id, SlotIndex));
				}
				if (!bHasUsablePool)
				{
					Issues.Add(FString::Printf(TEXT("Pack '%s' slot %d has no non-empty rarity pool."), *Pack.Id, SlotIndex));
				}
			}
		}

		TSet<int32> PackPool;
		for (const FDAERarityPool& Pool : Pack.Pools)
		{
			for (const int32 CardId : Pool.Cards)
			{
				if (PackPool.Contains(CardId))
				{
					Issues.Add(FString::Printf(TEXT("Pack '%s' lists card %d more than once."), *Pack.Id, CardId));
				}
				PackPool.Add(CardId);
				Obtainable.Add(CardId);
				if (Database && !Database->FindCard(CardId))
				{
					Issues.Add(FString::Printf(TEXT("Pack '%s' references missing card %d."), *Pack.Id, CardId));
				}
			}
		}
		if (Pack.bAllCards && Database)
		{
			TArray<int32> AllCards;
			Database->GetCards().GetKeys(AllCards);
			for (const int32 CardId : AllCards)
			{
				Obtainable.Add(CardId);
			}
		}
		for (const FDAEUnlockCondition& Condition : Pack.UnlockConditions)
		{
			if (Condition.Type == EDAEUnlockConditionType::Unknown)
			{
				Issues.Add(FString::Printf(TEXT("Pack '%s' has an unknown unlock condition."), *Pack.Id));
			}
		}
	}

	if (Database)
	{
		TArray<int32> Missing;
		for (const TPair<int32, FCardRecord>& Pair : Database->GetCards())
		{
			if (!Obtainable.Contains(Pair.Key))
			{
				Missing.Add(Pair.Key);
			}
		}
		if (Missing.Num() > 0)
		{
			Issues.Add(FString::Printf(TEXT("%d cards are not obtainable from any pack (first: %d)."), Missing.Num(), Missing[0]));
		}
	}
	return Issues;
}

FString UDAShopSubsystem::ExportStateJson() const
{
	const TSharedPtr<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetNumberField(TEXT("version"), 1);
	Root->SetNumberField(TEXT("cached_dp"), CachedDP);
	Root->SetBoolField(TEXT("internal_wallet"), bInternalWallet);

	const TSharedPtr<FJsonObject> LastObject = MakeShared<FJsonObject>();
	for (const TPair<FString, int32>& Pair : LastPurchaseDay)
	{
		LastObject->SetNumberField(Pair.Key, Pair.Value);
	}
	Root->SetObjectField(TEXT("last_purchase_day"), LastObject);

	const TSharedPtr<FJsonObject> CountObject = MakeShared<FJsonObject>();
	for (const TPair<FString, int32>& Pair : PurchaseCounts)
	{
		CountObject->SetNumberField(Pair.Key, Pair.Value);
	}
	Root->SetObjectField(TEXT("purchase_counts"), CountObject);

	return DAEconomyJson::WriteObject(Root);
}

bool UDAShopSubsystem::ImportStateJson(const FString& Json, FString& OutError)
{
	TSharedPtr<FJsonValue> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid() || !Root->AsObject().IsValid())
	{
		OutError = TEXT("Shop JSON could not be parsed.");
		return false;
	}

	const TSharedPtr<FJsonObject> Object = Root->AsObject();
	TMap<FString, int32> NewLast;
	TMap<FString, int32> NewCounts;

	const TSharedPtr<FJsonObject>* LastObject = nullptr;
	if (Object->TryGetObjectField(TEXT("last_purchase_day"), LastObject) && LastObject && LastObject->IsValid())
	{
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*LastObject)->Values)
		{
			if (Pair.Value.IsValid())
			{
				NewLast.Add(Pair.Key, static_cast<int32>(Pair.Value->AsNumber()));
			}
		}
	}
	const TSharedPtr<FJsonObject>* CountObject = nullptr;
	if (Object->TryGetObjectField(TEXT("purchase_counts"), CountObject) && CountObject && CountObject->IsValid())
	{
		for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*CountObject)->Values)
		{
			if (Pair.Value.IsValid())
			{
				NewCounts.Add(Pair.Key, static_cast<int32>(Pair.Value->AsNumber()));
			}
		}
	}

	LastPurchaseDay = MoveTemp(NewLast);
	PurchaseCounts = MoveTemp(NewCounts);
	Object->TryGetNumberField(TEXT("cached_dp"), CachedDP);
	CachedDP = FMath::Max(0, CachedDP);
	Object->TryGetBoolField(TEXT("internal_wallet"), bInternalWallet);
	if (bInternalWallet)
	{
		GetDPHandler = nullptr;
		SpendDPHandler = nullptr;
		CreditDPHandler = nullptr;
	}
	OnShopChanged.Broadcast();
	return true;
}

FDAEShopSaveData UDAShopSubsystem::GetSaveData() const
{
	FDAEShopSaveData Data;
	Data.Version = 1;
	Data.CachedDP = CachedDP;
	Data.bInternalWallet = bInternalWallet;
	Data.LastPurchaseDay = LastPurchaseDay;
	Data.PurchaseCounts = PurchaseCounts;
	return Data;
}

bool UDAShopSubsystem::ApplySaveData(const FDAEShopSaveData& Data, FString& OutError)
{
	if (Data.Version < 0)
	{
		OutError = TEXT("Unknown shop save version.");
		return false;
	}
	LastPurchaseDay = Data.LastPurchaseDay;
	PurchaseCounts = Data.PurchaseCounts;
	CachedDP = FMath::Max(0, Data.CachedDP);
	bInternalWallet = Data.bInternalWallet;
	if (bInternalWallet)
	{
		GetDPHandler = nullptr;
		SpendDPHandler = nullptr;
		CreditDPHandler = nullptr;
	}
	else if (!GetDPHandler || !SpendDPHandler)
	{
		// The save expected A02's wallet; if it has not registered yet, keep the
		// cached DP intact and leave the fallback active until SetWalletHandlers.
		bInternalWallet = true;
	}
	OnShopChanged.Broadcast();
	return true;
}

void UDAShopSubsystem::ResetPurchaseState()
{
	LastPurchaseDay.Reset();
	PurchaseCounts.Reset();
	ClearWalletHandlers();
	CachedDP = 3000;
	bInternalWallet = true;
	OnShopChanged.Broadcast();
}
