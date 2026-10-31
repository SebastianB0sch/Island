#include "DAEconomyTests.h"

#include "DAInventorySubsystem.h"
#include "DADeckLogic.h"
#include "DAShopSubsystem.h"
#include "DAStorySubsystem.h"
#include "DACardRecords.h"
#include "DuelAcademyIsland.h"

#include "Engine/GameInstance.h"
#include "Misc/Paths.h"

namespace
{
	struct FTestReport
	{
		int32 Passed = 0;
		int32 Failed = 0;
		TArray<FString> Lines;
		TArray<FString> Failures;

		void Check(bool bPassed, const FString& Name)
		{
			if (bPassed)
			{
				Passed++;
				Lines.Add(FString::Printf(TEXT("PASS  %s"), *Name));
			}
			else
			{
				Failed++;
				Failures.Add(Name);
				Lines.Add(FString::Printf(TEXT("FAIL  %s"), *Name));
			}
		}

		void CheckEqual(int32 Actual, int32 Expected, const FString& Name)
		{
			Check(Actual == Expected, FString::Printf(TEXT("%s (expected %d, got %d)"), *Name, Expected, Actual));
		}

		void CheckTrue(bool bValue, const FString& Name)
		{
			Check(bValue, Name);
		}

		FString ToString() const
		{
			FString Out = TEXT("============ DA ECONOMY SELF-TEST ============\n");
			for (const FString& Line : Lines)
			{
				Out += Line;
				Out += TEXT("\n");
			}
			Out += FString::Printf(TEXT("RESULT: %d passed, %d failed\n"), Passed, Failed);
			if (Failed > 0)
			{
				Out += TEXT("FAILED CHECKS:\n");
				for (const FString& Failure : Failures)
				{
					Out += TEXT("  - ");
					Out += Failure;
					Out += TEXT("\n");
				}
			}
			Out += TEXT("=============================================");
			return Out;
		}
	};

	void SetShopContext(UDAShopSubsystem* Shop, const FDAEUnlockContext& Context)
	{
		Shop->SetUnlockContext(Context);
	}

	bool HasErrorCode(const TArray<FDAEDeckError>& Errors, const TCHAR* Code)
	{
		const FName Wanted(Code);
		for (const FDAEDeckError& Error : Errors)
		{
			if (Error.Code == Wanted)
			{
				return true;
			}
		}
		return false;
	}

	FString PackSignature(const FDAEPackOpenResult& Result)
	{
		FString Signature;
		for (const FDAEPackCardReveal& Card : Result.Cards)
		{
			Signature += FString::Printf(TEXT("%d:%d|"), Card.CardId, static_cast<int32>(Card.Rarity));
		}
		return Signature;
	}

	TSet<int32> CollectPoolIds(const FDAEPackDef& Pack)
	{
		TSet<int32> Ids;
		for (const FDAERarityPool& Pool : Pack.Pools)
		{
			for (const int32 CardId : Pool.Cards)
			{
				Ids.Add(CardId);
			}
		}
		return Ids;
	}

	FDAEUnlockContext BuildAllUnlockContext(const TArray<FDAEPackDef>& Packs)
	{
		FDAEUnlockContext Context;
		Context.DayNumber = 1000;
		Context.MonthIndex = 12;
		Context.CollectionPercent = 100.f;
		Context.DormsVisited.Add(TEXT("Slifer"));
		Context.DormsVisited.Add(TEXT("Ra"));
		Context.DormsVisited.Add(TEXT("Obelisk"));

		for (const FDAEPackDef& Pack : Packs)
		{
			for (const FDAEUnlockCondition& Condition : Pack.UnlockConditions)
			{
				switch (Condition.Type)
				{
				case EDAEUnlockConditionType::Tutorial:
					Context.CompletedTutorials.AddUnique(Condition.Key);
					break;
				case EDAEUnlockConditionType::Event:
					Context.CompletedEvents.AddUnique(Condition.Key);
					break;
				case EDAEUnlockConditionType::Counter:
				{
					int32& Value = Context.Counters.FindOrAdd(Condition.Key);
					Value = FMath::Max(Value, Condition.Value);
					break;
				}
				case EDAEUnlockConditionType::Title:
					Context.Titles.AddUnique(Condition.Key);
					break;
				case EDAEUnlockConditionType::DormChanges:
					Context.DormChanges = FMath::Max(Context.DormChanges, Condition.Value);
					break;
				case EDAEUnlockConditionType::PackCompletion:
					Context.PackCompletion.FindOrAdd(Condition.Key) = 100.f;
					break;
				case EDAEUnlockConditionType::CollectionPercent:
					Context.CollectionPercent = FMath::Max(Context.CollectionPercent, static_cast<float>(Condition.Value));
					break;
				case EDAEUnlockConditionType::LocationDuels:
				{
					int32& Value = Context.LocationDuelCounts.FindOrAdd(Condition.Key);
					Value = FMath::Max(Value, Condition.Value);
					break;
				}
				case EDAEUnlockConditionType::MonthAtLeast:
					Context.MonthIndex = FMath::Max(Context.MonthIndex, Condition.Value);
					break;
				case EDAEUnlockConditionType::Flag:
					Context.Flags.AddUnique(Condition.Key);
					break;
				case EDAEUnlockConditionType::Start:
				case EDAEUnlockConditionType::VisitedAllDorms:
				case EDAEUnlockConditionType::Unknown:
				default:
					break;
				}
			}
		}
		return Context;
	}

	TArray<int32> PickNonFusionCards(UCardDatabaseSubsystem* Database, const FDAEDeckRules& Rules, int32 Count)
	{
		TArray<int32> Cards;
		if (!Database)
		{
			return Cards;
		}
		for (const TPair<int32, FCardRecord>& Pair : Database->GetCards())
		{
			if (!Pair.Value.CardType.Contains(TEXT("Fusion")) && Rules.GetCopyLimit(Pair.Key) >= Rules.MaxCopies)
			{
				Cards.Add(Pair.Key);
				if (Cards.Num() >= Count)
				{
					break;
				}
			}
		}
		Cards.Sort();
		return Cards;
	}

	TArray<int32> PickFusionCards(UCardDatabaseSubsystem* Database, const FDAEDeckRules& Rules, int32 Count)
	{
		TArray<int32> Cards;
		if (!Database)
		{
			return Cards;
		}
		for (const TPair<int32, FCardRecord>& Pair : Database->GetCards())
		{
			if (Pair.Value.CardType.Contains(TEXT("Fusion")) && Rules.GetCopyLimit(Pair.Key) >= Rules.MaxCopies)
			{
				Cards.Add(Pair.Key);
				if (Cards.Num() >= Count)
				{
					break;
				}
			}
		}
		Cards.Sort();
		return Cards;
	}

	FDAEDeck BuildDeck(const TArray<int32>& Main, const TArray<int32>& Extra)
	{
		FDAEDeck Deck;
		Deck.Id = TEXT("test_deck");
		Deck.Name = TEXT("Test Deck");
		Deck.Main = Main;
		Deck.Extra = Extra;
		return Deck;
	}

	void GrantCopies(UDAInventorySubsystem* Inventory, const TArray<int32>& Cards, int32 Copies)
	{
		for (const int32 CardId : Cards)
		{
			Inventory->AddCard(CardId, Copies);
		}
	}

	void TestCatalogue(FTestReport& Report, UDAShopSubsystem* Shop, UCardDatabaseSubsystem* Database)
	{
		Report.CheckEqual(Shop->GetPackCount(), 48, TEXT("catalogue has 48 packs"));
		Report.CheckTrue(Shop->ValidateCatalogue().Num() == 0, TEXT("catalogue validation is clean"));

		TSet<FString> Ids;
		TSet<int32> Obtainable;
		bool bPricesValid = true;
		bool bSlotsValid = true;
		bool bWeightTablesValid = true;
		int32 EmptyPools = 0;
		int32 MissingCardRefs = 0;
		int32 DuplicatePoolCards = 0;
		int32 BadFixedSlots = 0;
		int32 BadRarePlusWeights = 0;
		int32 BadPackMetadata = 0;
		int32 MissingUnlockData = 0;
		int32 MissingSets = 0;
		for (const FDAEPackDef& Pack : Shop->GetPacksRef())
		{
			Ids.Add(Pack.Id);
			if (Pack.Price <= 0) bPricesValid = false;
			if (Pack.Slots.Num() != Pack.PackSize) bSlotsValid = false;
			if (Pack.Price <= 0 || Pack.Stock < 0 || Pack.RestockDays <= 0 || Pack.PurchaseLimit <= 0)
			{
				BadPackMetadata++;
			}
			if (Pack.UnlockDescription.IsEmpty() || Pack.UnlockConditions.Num() == 0)
			{
				MissingUnlockData++;
			}
			if (Pack.Category.IsEmpty() || Pack.Source.IsEmpty())
			{
				MissingSets++;
			}
			if (!Pack.HasAnyPool())
			{
				EmptyPools++;
			}
			for (const FDAERarityWeight& Weight : Pack.RarePlusWeights)
			{
				if (Weight.Weight <= 0)
				{
					bWeightTablesValid = false;
				}
			}
			int32 DefaultWeightTotal = 0;
			for (const FDAERarityWeight& Weight : Pack.RarePlusWeights)
			{
				if (Weight.Weight > 0) DefaultWeightTotal += Weight.Weight;
			}
			if (DefaultWeightTotal != 100) bWeightTablesValid = false;

			for (const FDAEPackSlot& Slot : Pack.Slots)
			{
				if (Slot.Type == EDAEPackSlotType::FixedRarity && !Pack.FindPool(Slot.Rarity))
				{
					BadFixedSlots++;
				}
				if (Slot.Type == EDAEPackSlotType::RarePlus)
				{
					const TArray<FDAERarityWeight>& Weights = Slot.Weights.Num() > 0 ? Slot.Weights : Pack.RarePlusWeights;
					int32 TotalWeight = 0;
					bool bHasUsablePool = false;
					for (const FDAERarityWeight& Weight : Weights)
					{
						if (Weight.Weight <= 0) continue;
						TotalWeight += Weight.Weight;
						if (Pack.FindPool(Weight.Rarity)) bHasUsablePool = true;
					}
					if (TotalWeight <= 0 || !bHasUsablePool) BadRarePlusWeights++;
				}
			}

			TSet<int32> PackPool;
			for (const FDAERarityPool& Pool : Pack.Pools)
			{
				for (const int32 CardId : Pool.Cards)
				{
					if (PackPool.Contains(CardId)) DuplicatePoolCards++;
					PackPool.Add(CardId);
					Obtainable.Add(CardId);
					if (!Database->FindCard(CardId)) MissingCardRefs++;
				}
			}
			if (Pack.bAllCards && PackPool.Num() == 0) EmptyPools++;
		}
		Report.CheckEqual(Ids.Num(), 48, TEXT("pack ids are unique"));
		Report.CheckTrue(bPricesValid, TEXT("every pack has a positive price"));
		Report.CheckTrue(bSlotsValid, TEXT("every pack slot count matches pack size"));
		Report.CheckEqual(EmptyPools, 0, TEXT("every pack has a non-empty materialised pool"));
		Report.CheckEqual(MissingCardRefs, 0, TEXT("every pack pool card id exists in the 1200-card database"));
		Report.CheckEqual(DuplicatePoolCards, 0, TEXT("no pack lists a card id twice in its pools"));
		Report.CheckEqual(BadFixedSlots, 0, TEXT("every fixed slot has a matching non-empty rarity pool"));
		Report.CheckEqual(BadRarePlusWeights, 0, TEXT("every rare-plus slot has positive weights and a usable pool"));
		Report.CheckTrue(bWeightTablesValid, TEXT("default rare-plus weight tables sum to 100"));
		Report.CheckEqual(BadPackMetadata, 0, TEXT("every pack has price/stock/restock/purchase-limit metadata"));
		Report.CheckEqual(MissingUnlockData, 0, TEXT("every pack has unlock text and conditions"));
		Report.CheckEqual(MissingSets, 0, TEXT("every pack references a known set/category and source"));
		Report.CheckEqual(Obtainable.Num(), 1200, TEXT("all 1200 cards are obtainable from packs"));
		Report.CheckEqual(Shop->GetCatalogue().Num(), 48, TEXT("shop catalogue rows = 48"));
	}

	void TestInventory(FTestReport& Report, UDAInventorySubsystem* Inventory, UCardDatabaseSubsystem* Database)
	{
		Inventory->ResetCollection();
		Inventory->SetMaxOwnedCopies(3);

		for (const TPair<int32, FCardRecord>& Pair : Database->GetCards())
		{
			Inventory->AddCard(Pair.Key, 1);
		}
		const FDAECollectionStats FullStats = Inventory->GetCollectionStats();
		Report.CheckEqual(FullStats.UniqueCards, 1200, TEXT("inventory holds all 1200 unique cards"));
		Report.CheckEqual(FullStats.TotalCards, 1200, TEXT("inventory total cards = 1200"));
		Report.CheckTrue(FMath::IsNearlyEqual(FullStats.CompletionPercent, 100.f, 0.01f), TEXT("collection completion = 100%"));

		for (const TPair<int32, FCardRecord>& Pair : Database->GetCards())
		{
			Inventory->RemoveCard(Pair.Key, 1);
		}
		Report.CheckEqual(Inventory->GetCollectionSize(), 0, TEXT("inventory remove-all empties the trunk"));

		Inventory->ResetCollection();
		const int32 Added = Inventory->AddCard(1, 5);
		Report.CheckEqual(Added, 3, TEXT("ownership copy cap accepts 3 of 5"));
		Report.CheckEqual(Inventory->GetCount(1), 3, TEXT("ownership copy cap stores 3"));
		Report.CheckEqual(Inventory->AddCard(1, 1), 0, TEXT("ownership copy cap rejects a 4th copy"));
		Report.CheckEqual(Inventory->RemoveCard(1, 1), 1, TEXT("remove one copy"));
		const int32 AddedAfter = Inventory->AddCard(1, 2);
		Report.CheckEqual(AddedAfter, 1, TEXT("copy limit refills the one missing copy"));
		Report.CheckEqual(Inventory->GetCount(1), 3, TEXT("copy limit refills to 3"));

		Inventory->SetMaxOwnedCopies(0);
		Report.CheckEqual(Inventory->AddCard(1, 10), 10, TEXT("unlimited ownership mode accepts 10"));
		Inventory->SetMaxOwnedCopies(3);
		Inventory->ResetCollection();

		// Ante round-trip.
		Inventory->AddCard(1, 1);
		Report.CheckTrue(Inventory->RemoveCardForAnte(1, TEXT("duel_a"), TEXT("test")), TEXT("ante removal succeeds"));
		Report.CheckEqual(Inventory->GetCount(1), 0, TEXT("ante card leaves the trunk"));
		Report.CheckEqual(Inventory->GetPendingAnte().Num(), 1, TEXT("ante stake is tracked"));
		Report.CheckTrue(Inventory->ReturnAnteCard(TEXT("duel_a")), TEXT("ante return succeeds"));
		Report.CheckEqual(Inventory->GetCount(1), 1, TEXT("ante card returns to the trunk"));
		Report.CheckTrue(Inventory->RemoveCardForAnte(1, TEXT("duel_b"), TEXT("test")), TEXT("second ante removal succeeds"));
		Report.CheckTrue(Inventory->CommitAnteLoss(TEXT("duel_b")), TEXT("ante loss commits"));
		Report.CheckEqual(Inventory->GetCount(1), 0, TEXT("lost ante card stays gone"));

		// Stats and filters.
		Inventory->ResetCollection();
		Inventory->AddCard(1, 1);   // Blue-Eyes White Dragon
		Inventory->AddCard(2, 2);   // Mystical Elf
		Inventory->AddCard(40, 1);  // Red-Eyes B. Dragon
		const FDAECollectionStats Stats = Inventory->GetCollectionStats();
		Report.CheckEqual(Stats.UniqueCards, 3, TEXT("collection stats unique count"));
		Report.CheckEqual(Stats.TotalCards, 4, TEXT("collection stats total count"));

		FDAECardFilter MonsterFilter;
		MonsterFilter.bMonstersOnly = true;
		const TArray<int32> Monsters = Inventory->FilterCollection(MonsterFilter);
		Report.CheckTrue(Monsters.Num() >= 3, TEXT("monster filter returns monsters"));

		const TArray<int32> Sorted = Inventory->SortCards(Monsters, EDAECardSortKey::Attack, true);
		bool bSortedDescending = true;
		for (int32 Index = 1; Index < Sorted.Num(); ++Index)
		{
			const FCardRecord* Prev = Database->FindCard(Sorted[Index - 1]);
			const FCardRecord* Curr = Database->FindCard(Sorted[Index]);
			if (Prev && Curr && Prev->Atk < Curr->Atk)
			{
				bSortedDescending = false;
				break;
			}
		}
		Report.CheckTrue(bSortedDescending, TEXT("collection sort by ATK descending"));

		// Save-friendly payload round-trip.
		Inventory->AddCard(3, 1);
		const FString InventoryJson = Inventory->ExportStateJson();
		const int32 SavedCount = Inventory->GetCount(1);
		Inventory->ResetCollection();
		FString InventoryError;
		Report.CheckTrue(Inventory->ImportStateJson(InventoryJson, InventoryError), TEXT("inventory JSON imports"));
		Report.CheckEqual(Inventory->GetCount(1), SavedCount, TEXT("inventory JSON round-trip preserves counts"));
		Report.CheckEqual(Inventory->GetCollectionSize(), 5, TEXT("inventory JSON round-trip preserves total"));
	}

	void TestPacks(FTestReport& Report, UDAInventorySubsystem* Inventory, UDAShopSubsystem* Shop, UCardDatabaseSubsystem* Database)
	{
		Inventory->ResetCollection();
		Inventory->SetMaxOwnedCopies(3);

		FDAEPackDef Basic;
		Report.CheckTrue(Shop->GetPackDef(TEXT("basic_1a"), Basic), TEXT("basic_1a definition exists"));

		const FDAEPackOpenResult First = Inventory->OpenPackDefinition(Basic, 12345, false);
		const FDAEPackOpenResult Second = Inventory->OpenPackDefinition(Basic, 12345, false);
		Report.CheckTrue(First.bSuccess && Second.bSuccess, TEXT("pack preview succeeds"));
		Report.CheckEqual(First.Cards.Num(), Basic.PackSize, TEXT("pack preview returns pack_size cards"));
		Report.CheckTrue(PackSignature(First) == PackSignature(Second), TEXT("same seed = identical pack reveal"));
		Report.CheckTrue(PackSignature(First) != PackSignature(Inventory->OpenPackDefinition(Basic, 54321, false)), TEXT("different seeds differ"));

		TSet<FString> Signatures;
		for (int32 Seed = 1; Seed <= 10; ++Seed)
		{
			Signatures.Add(PackSignature(Inventory->OpenPackDefinition(Basic, Seed, false)));
		}
		Report.CheckTrue(Signatures.Num() > 5, TEXT("seeded pack rolls vary across seeds"));

		// Rare-plus slot distribution: 20,000 previews of basic_1a, slot 5.
		const int32 Iterations = 20000;
		int32 Rare = 0;
		int32 Super = 0;
		int32 Ultra = 0;
		int32 Secret = 0;
		bool bPoolMembership = true;
		TSet<int32> BasicPool;
		for (const FDAERarityPool& Pool : Basic.Pools)
		{
			for (const int32 CardId : Pool.Cards) BasicPool.Add(CardId);
		}
		for (int32 Index = 0; Index < Iterations; ++Index)
		{
			const FDAEPackOpenResult Result = Inventory->OpenPackDefinition(Basic, 1000 + Index, false);
			if (!Result.bSuccess || Result.Cards.Num() != Basic.PackSize)
			{
				bPoolMembership = false;
				break;
			}
			for (const FDAEPackCardReveal& Card : Result.Cards)
			{
				if (!BasicPool.Contains(Card.CardId))
				{
					bPoolMembership = false;
				}
			}
			switch (Result.Cards.Last().Rarity)
			{
			case EDAECardRarity::Rare: Rare++; break;
			case EDAECardRarity::SuperRare: Super++; break;
			case EDAECardRarity::UltraRare: Ultra++; break;
			case EDAECardRarity::SecretRare: Secret++; break;
			default: break;
			}
		}
		Report.CheckTrue(bPoolMembership, TEXT("pack card ids stay inside the printed pool"));
		Report.CheckTrue(Rare >= 13200 && Rare <= 14800, FString::Printf(TEXT("rare-plus Rare odds ~70%% (got %.2f%%)"), Rare * 100.f / Iterations));
		Report.CheckTrue(Super >= 3800 && Super <= 5000, FString::Printf(TEXT("rare-plus Super odds ~22%% (got %.2f%%)"), Super * 100.f / Iterations));
		Report.CheckTrue(Ultra >= 800 && Ultra <= 1600, FString::Printf(TEXT("rare-plus Ultra odds ~6%% (got %.2f%%)"), Ultra * 100.f / Iterations));
		Report.CheckTrue(Secret >= 100 && Secret <= 700, FString::Printf(TEXT("rare-plus Secret odds ~2%% (got %.2f%%)"), Secret * 100.f / Iterations));

		// Every pack opens cleanly and returns exactly pack_size cards.
		bool bAllOpen = true;
		for (const FDAEPackDef& Pack : Shop->GetPacksRef())
		{
			for (int32 Seed = 0; Seed < 50; ++Seed)
			{
				const FDAEPackOpenResult Result = Inventory->OpenPackDefinition(Pack, 9000 + Seed, false);
				if (!Result.bSuccess || Result.Cards.Num() != Pack.PackSize)
				{
					bAllOpen = false;
					break;
				}
			}
		}
		Report.CheckTrue(bAllOpen, TEXT("all 48 packs open with the correct card count"));

		// Real pack application + duplicate handling.
		Inventory->ResetCollection();
		const FDAEPackOpenResult Applied = Inventory->OpenPackDefinition(Basic, 777, true);
		Report.CheckTrue(Applied.bSuccess, TEXT("pack application succeeds"));
		Report.CheckEqual(Inventory->GetCollectionSize(), Basic.PackSize, TEXT("pack application adds pack_size cards"));

		for (const FDAERarityPool& Pool : Basic.Pools)
		{
			for (const int32 CardId : Pool.Cards)
			{
				Inventory->AddCard(CardId, 3);
			}
		}
		const FDAEPackOpenResult Duplicates = Inventory->OpenPackDefinition(Basic, 888, true);
		Report.CheckTrue(Duplicates.bSuccess, TEXT("duplicate-heavy pack still succeeds"));
		Report.CheckEqual(Duplicates.DPFromDuplicates, Basic.PackSize * Basic.DuplicateDPPerCard, TEXT("duplicates convert to DP"));
		Report.CheckEqual(Inventory->GetCount(Duplicates.Cards[0].CardId), 3, TEXT("duplicates do not exceed ownership cap"));

		// Dorothy's Gift can target every card.
		FDAEPackDef Dorothy;
		Report.CheckTrue(Shop->GetPackDef(TEXT("dorothys_gift"), Dorothy), TEXT("Dorothy's Gift definition exists"));
		Report.CheckTrue(Dorothy.bAllCards && Dorothy.bPreferUnowned, TEXT("Dorothy's Gift is all-cards and prefers unowned"));
		Inventory->ResetCollection();
		const FDAEPackOpenResult DorothyResult = Inventory->OpenPackDefinition(Dorothy, 4242, true);
		Report.CheckTrue(DorothyResult.bSuccess, TEXT("Dorothy's Gift opens"));
		Report.CheckEqual(DorothyResult.Cards.Num(), 7, TEXT("Dorothy's Gift reveals 7 cards"));
		bool bDorothyNew = true;
		for (const FDAEPackCardReveal& Card : DorothyResult.Cards)
		{
			if (!Card.bNew) bDorothyNew = false;
		}
		Report.CheckTrue(bDorothyNew, TEXT("Dorothy's Gift prioritises unowned cards on an empty trunk"));
	}

	void TestDorothysGift(FTestReport& Report, UDAInventorySubsystem* Inventory, UDAShopSubsystem* Shop, UCardDatabaseSubsystem* Database)
	{
		Inventory->ResetCollection();
		Inventory->SetMaxOwnedCopies(3);
		Shop->ResetPurchaseState();
		Shop->SetDebugDP(5000);

		FDAEPackDef Dorothy;
		Report.CheckTrue(Shop->GetPackDef(TEXT("dorothys_gift"), Dorothy), TEXT("Dorothy's Gift definition exists"));
		Report.CheckEqual(Dorothy.Price, 1000, TEXT("Dorothy's Gift price is 1000 DP"));
		Report.CheckEqual(Dorothy.PackSize, 7, TEXT("Dorothy's Gift pack size is 7"));
		Report.CheckEqual(Dorothy.RestockDays, 7, TEXT("Dorothy's Gift restocks weekly"));
		Report.CheckTrue(Dorothy.bAllCards && Dorothy.bPreferUnowned, TEXT("Dorothy's Gift is all-cards and prefers unowned"));
		Report.CheckEqual(Dorothy.Stock, 0, TEXT("Dorothy's Gift canon stock is unlimited"));
		Report.CheckEqual(Dorothy.Pools.Num(), 5, TEXT("Dorothy's Gift materialises five rarity pools"));

		TSet<int32> PoolIds;
		int32 PoolEntries = 0;
		bool bPoolIdsValid = true;
		for (const FDAERarityPool& Pool : Dorothy.Pools)
		{
			for (const int32 CardId : Pool.Cards)
			{
				PoolEntries++;
				PoolIds.Add(CardId);
				if (!Database->FindCard(CardId)) bPoolIdsValid = false;
			}
		}
		Report.CheckEqual(PoolIds.Num(), 1200, TEXT("Dorothy's Gift pool holds all 1200 unique cards"));
		Report.CheckEqual(PoolEntries, 1200, TEXT("Dorothy's Gift pool copy weight is one per card"));
		Report.CheckTrue(bPoolIdsValid, TEXT("Dorothy's Gift pool ids exist in the card database"));
		bool bCoversAllCards = true;
		for (int32 CardId = 1; CardId <= 1200; ++CardId)
		{
			if (!PoolIds.Contains(CardId))
			{
				bCoversAllCards = false;
				break;
			}
		}
		Report.CheckTrue(bCoversAllCards, TEXT("Dorothy's Gift pool covers every card id 1..1200"));

		FDAEUnlockContext Context;
		Context.DayNumber = 400;
		Context.CollectionPercent = 89.f;
		SetShopContext(Shop, Context);
		FString LockReason;
		Report.CheckTrue(!Shop->CanPurchase(TEXT("dorothys_gift"), LockReason), TEXT("Dorothy's Gift stays locked below 90% collection"));
		Report.CheckTrue(!LockReason.IsEmpty(), TEXT("Dorothy's Gift lock has a reason"));
		Context.CollectionPercent = 90.f;
		SetShopContext(Shop, Context);
		Report.CheckTrue(Shop->CanPurchase(TEXT("dorothys_gift"), LockReason), TEXT("Dorothy's Gift unlocks at 90% collection"));

		FDAEPurchaseResult Purchase;
		Report.CheckTrue(Shop->PurchasePack(TEXT("dorothys_gift"), 4242, Purchase), TEXT("Dorothy's Gift purchase succeeds"));
		Report.CheckEqual(Purchase.Price, 1000, TEXT("Dorothy's Gift purchase reports its price"));
		Report.CheckEqual(Purchase.DPBefore, 5000, TEXT("Dorothy's Gift DP before purchase"));
		Report.CheckEqual(Purchase.DPAfter, 4000, TEXT("Dorothy's Gift DP after purchase"));
		Report.CheckEqual(Shop->GetDP(), 4000, TEXT("Dorothy's Gift deducts exactly 1000 DP"));
		Report.CheckEqual(Purchase.Open.Cards.Num(), 7, TEXT("Dorothy's Gift reveals 7 cards"));
		Report.CheckEqual(Inventory->GetCollectionSize(), 7, TEXT("Dorothy's Gift adds 7 cards to an empty trunk"));
		Report.CheckEqual(Inventory->GetCollectionStats().UniqueCards, 7, TEXT("Dorothy's Gift adds 7 unique cards on an empty trunk"));
		bool bAllNew = true;
		bool bRevealIdsValid = true;
		TSet<int32> Revealed;
		for (const FDAEPackCardReveal& Card : Purchase.Open.Cards)
		{
			if (!Card.bNew) bAllNew = false;
			if (!Database->FindCard(Card.CardId)) bRevealIdsValid = false;
			Revealed.Add(Card.CardId);
		}
		Report.CheckTrue(bAllNew, TEXT("Dorothy's Gift marks cards new on an empty trunk"));
		Report.CheckTrue(bRevealIdsValid, TEXT("Dorothy's Gift reveal ids exist in the card database"));
		Report.CheckEqual(Revealed.Num(), 7, TEXT("Dorothy's Gift reveal has no duplicate cards"));

		Report.CheckEqual(Shop->GetPurchaseCount(TEXT("dorothys_gift")), 1, TEXT("Dorothy's Gift purchase count increments"));
		Report.CheckEqual(Shop->GetRemainingStock(TEXT("dorothys_gift")), -1, TEXT("Dorothy's Gift unlimited stock stays unlimited"));
		Report.CheckEqual(Shop->GetLastPurchaseDay(TEXT("dorothys_gift")), 400, TEXT("Dorothy's Gift records its purchase day"));
		Report.CheckEqual(Shop->GetNextAvailableDay(TEXT("dorothys_gift")), 407, TEXT("Dorothy's Gift next purchase day is +7"));

		Context.DayNumber = 406;
		SetShopContext(Shop, Context);
		FDAEPurchaseResult Early;
		Report.CheckTrue(!Shop->PurchasePack(TEXT("dorothys_gift"), 4243, Early), TEXT("Dorothy's Gift blocks a purchase one day early"));
		Report.CheckEqual(static_cast<int32>(Early.Block), static_cast<int32>(EDAEPurchaseBlock::Restocking), TEXT("Dorothy's Gift early purchase is restocking"));
		Context.DayNumber = 407;
		SetShopContext(Shop, Context);
		FDAEPurchaseResult Restocked;
		Report.CheckTrue(Shop->PurchasePack(TEXT("dorothys_gift"), 4244, Restocked), TEXT("Dorothy's Gift restock boundary allows day +7"));
		Report.CheckEqual(Restocked.DPBefore, 4000, TEXT("Dorothy's Gift restock DP before"));
		Report.CheckEqual(Restocked.DPAfter, 3000, TEXT("Dorothy's Gift restock DP after"));

		// Duplicate-heavy purchase: every card is already at the 3-copy cap.
		Inventory->ResetCollection();
		for (const TPair<int32, FCardRecord>& Pair : Database->GetCards())
		{
			Inventory->AddCard(Pair.Key, 3);
		}
		Shop->ResetPurchaseState();
		Shop->SetDebugDP(1000);
		Context = FDAEUnlockContext();
		Context.DayNumber = 500;
		Context.CollectionPercent = 100.f;
		SetShopContext(Shop, Context);
		const int32 InventoryBefore = Inventory->GetCollectionSize();
		FDAEPurchaseResult Duplicates;
		Report.CheckTrue(Shop->PurchasePack(TEXT("dorothys_gift"), 777, Duplicates), TEXT("Dorothy's Gift duplicate-heavy purchase succeeds"));
		Report.CheckEqual(Duplicates.Open.Cards.Num(), 7, TEXT("Dorothy's Gift duplicate purchase reveals 7 cards"));
		Report.CheckEqual(Duplicates.Open.DPFromDuplicates, 7 * Dorothy.DuplicateDPPerCard, TEXT("Dorothy's Gift duplicates convert to DP"));
		Report.CheckEqual(Duplicates.DPAfter, 1000 - 1000 + 7 * Dorothy.DuplicateDPPerCard, TEXT("Dorothy's Gift DP arithmetic includes duplicate compensation"));
		Report.CheckEqual(Inventory->GetCollectionSize(), InventoryBefore, TEXT("Dorothy's Gift duplicates leave inventory counts unchanged"));
		bool bAtCap = true;
		for (const FDAEPackCardReveal& Card : Duplicates.Open.Cards)
		{
			if (Inventory->GetCount(Card.CardId) != 3) bAtCap = false;
		}
		Report.CheckTrue(bAtCap, TEXT("Dorothy's Gift duplicate reveals stay at the 3-copy cap"));
		Report.CheckTrue(Duplicates.DPAfter >= 0, TEXT("Dorothy's Gift duplicate DP never goes negative"));
	}

	void TestBulkEconomy(FTestReport& Report, UDAInventorySubsystem* Inventory, UDAShopSubsystem* Shop, UCardDatabaseSubsystem* Database)
	{
		Inventory->ResetCollection();
		Inventory->SetMaxOwnedCopies(3);
		Shop->ResetPurchaseState();
		Shop->SetDebugDP(1000000);
		SetShopContext(Shop, BuildAllUnlockContext(Shop->GetPacksRef()));

		bool bPreviewCounts = true;
		bool bPreviewIds = true;
		bool bPreviewPools = true;
		bool bPreviewDuplicates = true;
		bool bPreviewDeterministic = true;
		bool bPreviewDPValid = true;
		int32 PreviewCount = 0;
		for (const FDAEPackDef& Pack : Shop->GetPacksRef())
		{
			const TSet<int32> PoolIds = CollectPoolIds(Pack);
			for (int32 Seed = 1; Seed <= 10; ++Seed)
			{
				const FDAEPackOpenResult First = Inventory->OpenPackDefinition(Pack, Seed, false);
				const FDAEPackOpenResult Second = Inventory->OpenPackDefinition(Pack, Seed, false);
				PreviewCount++;
				if (!First.bSuccess || First.Cards.Num() != Pack.PackSize) bPreviewCounts = false;
				if (PackSignature(First) != PackSignature(Second)) bPreviewDeterministic = false;
				if (First.DPFromDuplicates < 0) bPreviewDPValid = false;
				TSet<int32> Seen;
				for (const FDAEPackCardReveal& Card : First.Cards)
				{
					if (!Database->FindCard(Card.CardId)) bPreviewIds = false;
					if (!Pack.bAllCards && !PoolIds.Contains(Card.CardId)) bPreviewPools = false;
					if (!Pack.bAllowDuplicatesInPack && Seen.Contains(Card.CardId)) bPreviewDuplicates = false;
					Seen.Add(Card.CardId);
				}
			}
		}
		Report.CheckEqual(PreviewCount, 48 * 10, TEXT("bulk preview opens every pack 10 times"));
		Report.CheckTrue(bPreviewCounts, TEXT("bulk preview always returns pack_size cards"));
		Report.CheckTrue(bPreviewIds, TEXT("bulk preview has no invalid card ids"));
		Report.CheckTrue(bPreviewPools, TEXT("bulk preview stays inside the printed pool"));
		Report.CheckTrue(bPreviewDuplicates, TEXT("bulk preview avoids in-pack duplicates"));
		Report.CheckTrue(bPreviewDeterministic, TEXT("bulk preview is deterministic per pack and seed"));
		Report.CheckTrue(bPreviewDPValid, TEXT("bulk preview duplicate DP is non-negative"));

		// Bulk purchase: every pack ten times, each time exactly on its restock boundary.
		Inventory->ResetCollection();
		Shop->ResetPurchaseState();
		Shop->SetDebugDP(1000000);
		const int32 StartDP = Shop->GetDP();
		FDAEUnlockContext Context = BuildAllUnlockContext(Shop->GetPacksRef());
		SetShopContext(Shop, Context);

		int32 Spent = 0;
		int32 Credited = 0;
		int32 Purchases = 0;
		bool bPurchaseSuccess = true;
		bool bPurchaseCards = true;
		bool bPurchaseIds = true;
		bool bDPNonNegative = true;
		bool bStockCounts = true;
		bool bStockNonNegative = true;
		for (const FDAEPackDef& Pack : Shop->GetPacksRef())
		{
			if (Pack.Stock < 0) bStockNonNegative = false;
			const int32 Runs = 10;
			for (int32 Run = 0; Run < Runs; ++Run)
			{
				Context.DayNumber = 1000 + Run * FMath::Max(1, Pack.RestockDays);
				SetShopContext(Shop, Context);
				FDAEPurchaseResult Purchase;
				if (!Shop->PurchasePack(Pack.Id, 7000 + Run, Purchase))
				{
					bPurchaseSuccess = false;
					continue;
				}
				Purchases++;
				Spent += Purchase.Price;
				Credited += Purchase.Open.DPFromDuplicates;
				if (Purchase.Open.Cards.Num() != Pack.PackSize) bPurchaseCards = false;
				if (Purchase.DPAfter < 0 || Shop->GetDP() < 0) bDPNonNegative = false;
				for (const FDAEPackCardReveal& Card : Purchase.Open.Cards)
				{
					if (!Database->FindCard(Card.CardId)) bPurchaseIds = false;
				}
			}
			const int32 ExpectedRemaining = Pack.Stock > 0 ? Pack.Stock - Runs : -1;
			if (Shop->GetRemainingStock(Pack.Id) != ExpectedRemaining) bStockCounts = false;
			if (Shop->GetPurchaseCount(Pack.Id) != Runs) bStockCounts = false;
			if (Shop->GetRemainingStock(Pack.Id) < -1) bStockNonNegative = false;
			if (Shop->GetPurchaseCount(Pack.Id) < 0) bStockNonNegative = false;
		}
		Report.CheckTrue(bPurchaseSuccess, TEXT("bulk purchases succeed for all 48 packs x10"));
		Report.CheckEqual(Purchases, 48 * 10, TEXT("bulk purchase count is 480"));
		Report.CheckTrue(bPurchaseCards, TEXT("bulk purchase always applies pack_size cards"));
		Report.CheckTrue(bPurchaseIds, TEXT("bulk purchase has no invalid card ids"));
		Report.CheckTrue(bDPNonNegative, TEXT("bulk purchase never drives DP negative"));
		Report.CheckTrue(bStockNonNegative, TEXT("bulk catalogue stock and counters stay non-negative"));
		Report.CheckTrue(bStockCounts, TEXT("bulk purchase decrements finite stock and keeps unlimited stock at -1"));
		Report.CheckEqual(Shop->GetDP(), StartDP - Spent + Credited, TEXT("bulk purchase DP ledger balances"));
	}

	void TestPendingPackGrants(FTestReport& Report, UDAInventorySubsystem* Inventory, UDAShopSubsystem* Shop)
	{
		UGameInstance* GI = Inventory->GetGameInstance();
		UDAStorySubsystem* Story = GI ? GI->GetSubsystem<UDAStorySubsystem>() : nullptr;
		Report.CheckTrue(Story != nullptr, TEXT("story subsystem is available for pending pack grants"));
		if (!Story)
		{
			return;
		}

		const FString SavedStory = Story->SaveState();
		FString StoryError;
		Report.CheckTrue(Story->LoadState(TEXT("{\"pending_packs\":{\"basic_1a\":1}}"), StoryError), TEXT("test queues a pending pack grant"));
		Report.CheckTrue(Story->GetPendingPackGrants().Contains(TEXT("basic_1a")), TEXT("pending pack grant is visible"));

		Inventory->ResetCollection();
		Inventory->SetMaxOwnedCopies(3);
		const int32 DPBefore = Shop->GetDP();
		const FDAEPackOpenResult Granted = Inventory->ConsumePendingPackGrant(TEXT("basic_1a"), 2468);
		Report.CheckTrue(Granted.bSuccess, TEXT("pending grant consumes and opens"));
		Report.CheckEqual(Granted.Cards.Num(), 5, TEXT("pending grant reveals a full pack"));
		Report.CheckEqual(Inventory->GetCollectionSize(), 5, TEXT("pending grant adds its cards to inventory"));
		Report.CheckTrue(!Story->GetPendingPackGrants().Contains(TEXT("basic_1a")), TEXT("successful consume removes the pending grant"));
		Report.CheckEqual(Shop->GetDP(), DPBefore, TEXT("pending grant does not spend DP"));

		const FDAEPackOpenResult Duplicate = Inventory->ConsumePendingPackGrant(TEXT("basic_1a"), 2468);
		Report.CheckTrue(!Duplicate.bSuccess, TEXT("duplicate pending grant consume is rejected"));
		Report.CheckTrue(Duplicate.ErrorCode == TEXT("no_pending_grant"), TEXT("duplicate consume reports no_pending_grant"));
		Report.CheckEqual(Inventory->GetCollectionSize(), 5, TEXT("duplicate consume adds no cards"));

		Report.CheckTrue(Story->LoadState(TEXT("{\"pending_packs\":{\"missing_pack\":1}}"), StoryError), TEXT("test queues an unknown pack grant"));
		const int32 InventoryBeforeMissing = Inventory->GetCollectionSize();
		const FDAEPackOpenResult Missing = Inventory->ConsumePendingPackGrant(TEXT("missing_pack"), 1);
		Report.CheckTrue(!Missing.bSuccess, TEXT("unknown pending pack fails"));
		Report.CheckTrue(Missing.ErrorCode == TEXT("pack_not_found"), TEXT("unknown pending pack reports pack_not_found"));
		Report.CheckTrue(Story->GetPendingPackGrants().Contains(TEXT("missing_pack")), TEXT("failed consume leaves the grant queued"));
		Report.CheckEqual(Inventory->GetCollectionSize(), InventoryBeforeMissing, TEXT("failed consume adds no cards"));

		FString RestoreError;
		Report.CheckTrue(Story->LoadState(SavedStory, RestoreError), TEXT("story state restores after the grant test"));
	}

	void TestDeckCatalogue(FTestReport& Report, UDADeckLogic* DeckLogic, UCardDatabaseSubsystem* Database)
	{
		DeckLogic->ResetToDefaults();
		const FDAEDeckRules& Rules = DeckLogic->GetRules();
		Report.CheckEqual(Rules.MaxExtra, 15, TEXT("deck rules cap the Extra Deck at 15"));
		Report.CheckEqual(Rules.MaxCopies, 3, TEXT("deck rules cap copies at 3"));

		auto CountNameCopies = [Database](const FDAEDeck& Deck)
		{
			TMap<FString, int32> Counts;
			for (const int32 CardId : Deck.Main)
			{
				if (const FCardRecord* Card = Database->FindCard(CardId)) Counts.FindOrAdd(Card->Name)++;
			}
			for (const int32 CardId : Deck.Extra)
			{
				if (const FCardRecord* Card = Database->FindCard(CardId)) Counts.FindOrAdd(Card->Name)++;
			}
			return Counts;
		};
		auto HasNameOverflow = [&Rules](const TMap<FString, int32>& Counts)
		{
			for (const TPair<FString, int32>& Pair : Counts)
			{
				if (Pair.Value > Rules.MaxCopies) return true;
			}
			return false;
		};

		const TArray<FStarterDeckDef> StarterDecks = DeckLogic->GetStarterDecks();
		bool bStarterLegal = true;
		bool bStarterExtra = true;
		bool bStarterNames = true;
		for (const FStarterDeckDef& Starter : StarterDecks)
		{
			FDAEDeck Deck = BuildDeck(Starter.Cards, Starter.Extra);
			Deck.Id = Starter.Id;
			Deck.Name = Starter.Name;
			TArray<FDAEDeckError> Errors;
			if (!UDADeckLogic::ValidateDeckAgainstRules(Deck, Rules, Database, nullptr, false, Errors)) bStarterLegal = false;
			if (Deck.Extra.Num() > Rules.MaxExtra) bStarterExtra = false;
			if (HasNameOverflow(CountNameCopies(Deck))) bStarterNames = false;
		}
		Report.CheckTrue(StarterDecks.Num() > 0, TEXT("starter decks are loaded"));
		Report.CheckTrue(bStarterLegal, TEXT("all starter decks are legal under the Year 1 banlist"));
		Report.CheckTrue(bStarterExtra, TEXT("all starter decks fit the 15-card Extra Deck"));
		Report.CheckTrue(bStarterNames, TEXT("all starter decks respect the 3-copy printed-name limit"));

		const TArray<FDAEDeck>& PlayerDecks = DeckLogic->GetPlayerDecksRef();
		bool bPlayerLegal = true;
		bool bPlayerExtra = true;
		bool bPlayerNames = true;
		for (const FDAEDeck& Deck : PlayerDecks)
		{
			TArray<FDAEDeckError> Errors;
			if (!UDADeckLogic::ValidateDeckAgainstRules(Deck, Rules, Database, nullptr, false, Errors)) bPlayerLegal = false;
			if (Deck.Extra.Num() > Rules.MaxExtra) bPlayerExtra = false;
			if (HasNameOverflow(CountNameCopies(Deck))) bPlayerNames = false;
		}
		Report.CheckTrue(PlayerDecks.Num() > 0, TEXT("player decks are loaded"));
		Report.CheckTrue(bPlayerLegal, TEXT("all player decks are legal under the Year 1 banlist"));
		Report.CheckTrue(bPlayerExtra, TEXT("all player decks fit the 15-card Extra Deck"));
		Report.CheckTrue(bPlayerNames, TEXT("all player decks respect the 3-copy printed-name limit"));
	}

	void TestDecks(FTestReport& Report, UDAInventorySubsystem* Inventory, UDADeckLogic* DeckLogic, UCardDatabaseSubsystem* Database)
	{
		Inventory->ResetCollection();
		Inventory->SetMaxOwnedCopies(3);
		DeckLogic->ResetToDefaults();

		const FDAEDeck* DefaultDeck = DeckLogic->FindPlayerDeck(TEXT("player_1"));
		Report.CheckTrue(DefaultDeck != nullptr, TEXT("default player deck exists"));
		if (!DefaultDeck)
		{
			return;
		}
		Report.CheckEqual(DefaultDeck->Main.Num(), 40, TEXT("default player deck has 40 main cards"));
		Report.CheckTrue(DefaultDeck->Extra.Num() <= 15, TEXT("default player deck extra <= 15"));

		const TArray<int32> DefaultMain = DefaultDeck->Main;
		const TArray<int32> DefaultExtra = DefaultDeck->Extra;
		GrantCopies(Inventory, DefaultMain, 1);
		GrantCopies(Inventory, DefaultExtra, 1);
		TArray<FDAEDeckError> DefaultErrors;
		Report.CheckTrue(DeckLogic->ValidateDeck(*DefaultDeck, DefaultErrors), TEXT("default player deck is legal"));

		// The A02 new-game path grants GetDefaultStarterCards(); it must own every
		// copy used by the default deck, including duplicates.
		Inventory->ResetCollection();
		const int32 GrantedStarterCards = Inventory->GrantStarterCollection(DeckLogic->GetDefaultStarterCards());
		Report.CheckEqual(GrantedStarterCards, 41, TEXT("starter grant owns all 41 deck copies"));
		Report.CheckTrue(DeckLogic->ValidateDeck(*DefaultDeck, DefaultErrors), TEXT("starter grant makes the default deck legal"));

		// 40-60 main.
		const TArray<int32> Twenty = PickNonFusionCards(Database, DeckLogic->GetRules(), 20);
		Report.CheckEqual(Twenty.Num(), 20, TEXT("found 20 non-fusion cards for the 60-card test"));
		Inventory->ResetCollection();
		GrantCopies(Inventory, Twenty, 3);
		TArray<int32> Main60;
		for (const int32 CardId : Twenty)
		{
			for (int32 Copy = 0; Copy < 3; ++Copy)
			{
				Main60.Add(CardId);
			}
		}
		const FDAEDeck Deck60 = BuildDeck(Main60, {});
		TArray<FDAEDeckError> Errors60;
		UDADeckLogic::ValidateDeckAgainstRules(Deck60, DeckLogic->GetRules(), Database, Inventory, true, Errors60);
		Report.CheckTrue(Errors60.Num() == 0, TEXT("60-card main deck is legal"));

		TArray<int32> Main61 = Main60;
		Main61.Add(Twenty[0]);
		const FDAEDeck Deck61 = BuildDeck(Main61, {});
		TArray<FDAEDeckError> Errors61;
		UDADeckLogic::ValidateDeckAgainstRules(Deck61, DeckLogic->GetRules(), Database, Inventory, false, Errors61);
		Report.CheckTrue(HasErrorCode(Errors61, TEXT("main_too_large")), TEXT("61-card main deck is rejected"));

		TArray<int32> Main39 = Main60;
		Main39.SetNum(39);
		const FDAEDeck Deck39 = BuildDeck(Main39, {});
		TArray<FDAEDeckError> Errors39;
		UDADeckLogic::ValidateDeckAgainstRules(Deck39, DeckLogic->GetRules(), Database, Inventory, false, Errors39);
		Report.CheckTrue(HasErrorCode(Errors39, TEXT("main_too_small")), TEXT("39-card main deck is rejected"));

		// 15-card extra deck.
		const TArray<int32> Fusions = PickFusionCards(Database, DeckLogic->GetRules(), 16);
		Report.CheckEqual(Fusions.Num(), 16, TEXT("found 16 fusion cards for the extra-deck test"));
		Inventory->ResetCollection();
		GrantCopies(Inventory, Fusions, 1);
		GrantCopies(Inventory, DefaultMain, 1);
		TArray<int32> Extra15(Fusions);
		Extra15.SetNum(15);
		const FDAEDeck ExtraDeck15 = BuildDeck(DefaultMain, Extra15);
		TArray<FDAEDeckError> ExtraErrors15;
		UDADeckLogic::ValidateDeckAgainstRules(ExtraDeck15, DeckLogic->GetRules(), Database, Inventory, true, ExtraErrors15);
		Report.CheckTrue(ExtraErrors15.Num() == 0, TEXT("15-card extra deck is legal"));
		const FDAEDeck ExtraDeck16 = BuildDeck(DefaultMain, Fusions);
		TArray<FDAEDeckError> ExtraErrors16;
		UDADeckLogic::ValidateDeckAgainstRules(ExtraDeck16, DeckLogic->GetRules(), Database, Inventory, false, ExtraErrors16);
		Report.CheckTrue(HasErrorCode(ExtraErrors16, TEXT("extra_too_large")), TEXT("16-card extra deck is rejected"));

		// Copy limit / banned / limited.
		Inventory->ResetCollection();
		Inventory->AddCard(1, 3);
		const FDAEDeck FourCopies = BuildDeck({ 1, 1, 1, 1 }, {});
		TArray<FDAEDeckError> CopyErrors;
		UDADeckLogic::ValidateDeckAgainstRules(FourCopies, DeckLogic->GetRules(), Database, Inventory, false, CopyErrors);
		Report.CheckTrue(HasErrorCode(CopyErrors, TEXT("copy_limit")), TEXT("4 copies of a card is rejected"));

		// The canon year 1 list loaded from Rules/banned_limited.json must apply.
		const FDAEDeck CanonBannedDeck = BuildDeck({ 141 }, {}); // Dark Hole: Forbidden
		TArray<FDAEDeckError> CanonBannedErrors;
		UDADeckLogic::ValidateDeckAgainstRules(CanonBannedDeck, DeckLogic->GetRules(), Database, nullptr, false, CanonBannedErrors);
		Report.CheckTrue(HasErrorCode(CanonBannedErrors, TEXT("banned_card")), TEXT("canon year-1 forbidden card is rejected"));

		const FDAEDeck CanonLimitedDeck = BuildDeck({ 13, 13 }, {}); // Right Leg: Limited 1
		TArray<FDAEDeckError> CanonLimitedErrors;
		UDADeckLogic::ValidateDeckAgainstRules(CanonLimitedDeck, DeckLogic->GetRules(), Database, nullptr, false, CanonLimitedErrors);
		Report.CheckTrue(HasErrorCode(CanonLimitedErrors, TEXT("limited_card")), TEXT("canon year-1 limited card copy count is rejected"));

		FDAEDeckRules CustomRules = DeckLogic->GetRules();
		CustomRules.Banned.Add(1);
		CustomRules.Limited.Add(2, 1);
		CustomRules.SemiLimited.Add(3, 2);
		const FDAEDeck BannedDeck = BuildDeck({ 1 }, {});
		TArray<FDAEDeckError> BannedErrors;
		UDADeckLogic::ValidateDeckAgainstRules(BannedDeck, CustomRules, Database, nullptr, false, BannedErrors);
		Report.CheckTrue(HasErrorCode(BannedErrors, TEXT("banned_card")), TEXT("banned card is rejected"));

		const FDAEDeck LimitedDeck = BuildDeck({ 2, 2 }, {});
		TArray<FDAEDeckError> LimitedErrors;
		UDADeckLogic::ValidateDeckAgainstRules(LimitedDeck, CustomRules, Database, nullptr, false, LimitedErrors);
		Report.CheckTrue(HasErrorCode(LimitedErrors, TEXT("limited_card")), TEXT("limited card copy count is rejected"));

		const FDAEDeck SemiDeck = BuildDeck({ 3, 3, 3 }, {});
		TArray<FDAEDeckError> SemiErrors;
		UDADeckLogic::ValidateDeckAgainstRules(SemiDeck, CustomRules, Database, nullptr, false, SemiErrors);
		Report.CheckTrue(HasErrorCode(SemiErrors, TEXT("limited_card")), TEXT("semi-limited card copy count is rejected"));

		// Owning a card is required for a player deck.
		Inventory->ResetCollection();
		TArray<FDAEDeckError> OwnershipErrors;
		const FDAEDeck OwnedDeck = BuildDeck({ 1 }, {});
		UDADeckLogic::ValidateDeckAgainstRules(OwnedDeck, DeckLogic->GetRules(), Database, Inventory, true, OwnershipErrors);
		Report.CheckTrue(HasErrorCode(OwnershipErrors, TEXT("not_owned")), TEXT("unowned cards are rejected"));

		// Editing operations.
		Inventory->ResetCollection();
		Inventory->AddCard(1, 1);
		Inventory->AddCard(2, 1);
		DeckLogic->ResetToDefaults();
		FString CreateError;
		const FString NewDeckId = DeckLogic->CreateDeck(TEXT("Editor Test"), CreateError);
		Report.CheckTrue(!NewDeckId.IsEmpty(), TEXT("create deck succeeds"));
		FString AddError;
		Report.CheckTrue(DeckLogic->AddCardToDeck(NewDeckId, 1, false, AddError), TEXT("add owned card to deck"));
		Report.CheckTrue(!DeckLogic->AddCardToDeck(NewDeckId, 1, false, AddError), TEXT("cannot add a second unowned copy"));
		Report.CheckTrue(DeckLogic->AddCardToDeck(NewDeckId, 2, false, AddError), TEXT("add second owned card"));
		Report.CheckTrue(DeckLogic->RemoveCardFromDeck(NewDeckId, 1, false, AddError), TEXT("remove card from deck"));
		Report.CheckTrue(DeckLogic->SwapCardInDeck(NewDeckId, 2, 1, false, AddError), TEXT("swap card in deck"));

		FString RenameError;
		Report.CheckTrue(DeckLogic->RenameDeck(NewDeckId, TEXT("Renamed Deck"), RenameError), TEXT("rename deck"));
		FString CopyId;
		FString CopyError;
		Report.CheckTrue(DeckLogic->CopyDeck(NewDeckId, TEXT("Copied Deck"), CopyId, CopyError), TEXT("copy deck"));
		Report.CheckTrue(CopyId != NewDeckId, TEXT("copied deck gets a fresh id"));
		FString EraseError;
		Report.CheckTrue(DeckLogic->EraseDeck(CopyId, EraseError), TEXT("erase deck"));

		// Save round-trip.
		const FString DeckJson = DeckLogic->ExportStateJson();
		const int32 DeckCount = DeckLogic->GetPlayerDecksRef().Num();
		DeckLogic->ResetToDefaults();
		FString DeckImportError;
		Report.CheckTrue(DeckLogic->ImportStateJson(DeckJson, DeckImportError), TEXT("deck JSON imports"));
		Report.CheckEqual(DeckLogic->GetPlayerDecksRef().Num(), DeckCount, TEXT("deck JSON round-trip preserves deck count"));

		// Fusion recipes use owned cards.
		Inventory->ResetCollection();
		GrantCopies(Inventory, DefaultMain, 1);
		Report.CheckTrue(DeckLogic->GetAvailableFusionRecipes().Num() > 0, TEXT("owned fusion materials expose recipes"));
	}

	void TestShop(FTestReport& Report, UDAInventorySubsystem* Inventory, UDAShopSubsystem* Shop, UDADeckLogic* DeckLogic)
	{
		Inventory->ResetCollection();
		DeckLogic->ResetToDefaults();
		Shop->ResetPurchaseState();
		Shop->SetDebugDP(1000);

		FDAEUnlockContext Context;
		Context.DayNumber = 100;
		SetShopContext(Shop, Context);

		FDAEPurchaseResult Purchase;
		Report.CheckTrue(Shop->PurchasePack(TEXT("basic_1a"), 42, Purchase), TEXT("successful pack purchase"));
		Report.CheckEqual(Purchase.Price, 100, TEXT("purchase reports the price"));
		Report.CheckEqual(Purchase.DPBefore, 1000, TEXT("purchase DP before"));
		Report.CheckEqual(Purchase.DPAfter, 900, TEXT("purchase DP after"));
		Report.CheckEqual(Purchase.Open.Cards.Num(), 5, TEXT("purchase opens 5 cards"));
		Report.CheckEqual(Inventory->GetCollectionSize(), 5, TEXT("purchase adds 5 cards"));
		FDAEPackDef BasicStockPack;
		Shop->GetPackDef(TEXT("basic_1a"), BasicStockPack);
		const int32 ExpectedStockAfterOne = BasicStockPack.Stock > 0 ? BasicStockPack.Stock - 1 : -1;
		Report.CheckEqual(Shop->GetPurchaseCount(TEXT("basic_1a")), 1, TEXT("finite-stock purchase count increments"));
		Report.CheckEqual(Shop->GetRemainingStock(TEXT("basic_1a")), ExpectedStockAfterOne, TEXT("finite stock decrements by one"));

		const int32 InventoryBefore = Inventory->GetCollectionSize();
		FDAEPurchaseResult RestockBlocked;
		Report.CheckTrue(!Shop->PurchasePack(TEXT("basic_1a"), 43, RestockBlocked), TEXT("same-day repurchase is blocked"));
		Report.CheckEqual(static_cast<int32>(RestockBlocked.Block), static_cast<int32>(EDAEPurchaseBlock::Restocking), TEXT("repurchase block reason = restocking"));
		Report.CheckEqual(Inventory->GetCollectionSize(), InventoryBefore, TEXT("blocked repurchase does not add cards"));
		Report.CheckEqual(Shop->GetDP(), 900, TEXT("blocked repurchase does not spend DP"));

		Context.DayNumber = 107;
		SetShopContext(Shop, Context);
		FDAEPurchaseResult Restocked;
		Report.CheckTrue(Shop->PurchasePack(TEXT("basic_1a"), 44, Restocked), TEXT("repurchase after restock succeeds"));

		// Insufficient DP is atomic.
		Inventory->ResetCollection();
		Shop->ResetPurchaseState();
		Shop->SetDebugDP(50);
		FDAEPurchaseResult Poor;
		Report.CheckTrue(!Shop->PurchasePack(TEXT("basic_1a"), 1, Poor), TEXT("insufficient DP purchase fails"));
		Report.CheckEqual(static_cast<int32>(Poor.Block), static_cast<int32>(EDAEPurchaseBlock::InsufficientDP), TEXT("insufficient DP block reason"));
		Report.CheckEqual(Shop->GetDP(), 50, TEXT("failed purchase leaves DP untouched"));
		Report.CheckEqual(Inventory->GetCollectionSize(), 0, TEXT("failed purchase leaves inventory untouched"));

		// Wallet rejection is atomic.
		Shop->SetWalletHandlers(
			[]() { return 1000; },
			[](int32) { return false; },
			[](int32, const FString&) {});
		FDAEPurchaseResult Rejected;
		Report.CheckTrue(!Shop->PurchasePack(TEXT("basic_1a"), 2, Rejected), TEXT("wallet rejection fails the purchase"));
		Report.CheckEqual(static_cast<int32>(Rejected.Block), static_cast<int32>(EDAEPurchaseBlock::WalletRejected), TEXT("wallet rejection block reason"));
		Report.CheckEqual(Inventory->GetCollectionSize(), 0, TEXT("wallet rejection leaves inventory untouched"));
		Shop->SetDebugDP(1000);

		// Locked pack until its event flag is pushed.
		Inventory->ResetCollection();
		Shop->ResetPurchaseState();
		Shop->SetDebugDP(1000);
		Context = FDAEUnlockContext();
		Context.DayNumber = 200;
		SetShopContext(Shop, Context);
		FString LockReason;
		Report.CheckTrue(!Shop->CanPurchase(TEXT("the_hero"), LockReason), TEXT("event pack is locked by default"));
		Report.CheckTrue(!LockReason.IsEmpty(), TEXT("locked pack has a reason"));
		Context.CompletedEvents.Add(TEXT("new_hero_summoning"));
		SetShopContext(Shop, Context);
		Report.CheckTrue(Shop->CanPurchase(TEXT("the_hero"), LockReason), TEXT("event pack unlocks when the event is complete"));

		// Duplicate compensation and exact DP arithmetic.
		Inventory->ResetCollection();
		Shop->ResetPurchaseState();
		Shop->SetDebugDP(1000);
		FDAEPackDef Basic;
		Shop->GetPackDef(TEXT("basic_1a"), Basic);
		TSet<int32> BasicPool;
		for (const FDAERarityPool& Pool : Basic.Pools)
		{
			for (const int32 CardId : Pool.Cards)
			{
				BasicPool.Add(CardId);
			}
		}
		for (const int32 CardId : BasicPool)
		{
			Inventory->AddCard(CardId, 3);
		}
		Context = FDAEUnlockContext();
		Context.DayNumber = 300;
		SetShopContext(Shop, Context);
		FDAEPurchaseResult DuplicatePurchase;
		Report.CheckTrue(Shop->PurchasePack(TEXT("basic_1a"), 7, DuplicatePurchase), TEXT("duplicate-heavy purchase succeeds"));
		Report.CheckEqual(DuplicatePurchase.Open.DPFromDuplicates, 5 * Basic.DuplicateDPPerCard, TEXT("duplicate compensation amount"));
		Report.CheckEqual(DuplicatePurchase.DPAfter, 1000 - 100 + 5 * Basic.DuplicateDPPerCard, TEXT("DP arithmetic includes duplicate compensation"));
		Report.CheckTrue(DuplicatePurchase.DPAfter >= 0, TEXT("DP never goes negative"));

		// Shop save round-trip.
		const FString ShopJson = Shop->ExportStateJson();
		const int32 SavedDP = Shop->GetDP();
		const int32 SavedLastDay = Shop->GetLastPurchaseDay(TEXT("basic_1a"));
		Shop->ResetPurchaseState();
		FString ShopImportError;
		Report.CheckTrue(Shop->ImportStateJson(ShopJson, ShopImportError), TEXT("shop JSON imports"));
		Report.CheckEqual(Shop->GetDP(), SavedDP, TEXT("shop JSON round-trip preserves DP"));
		Report.CheckEqual(Shop->GetLastPurchaseDay(TEXT("basic_1a")), SavedLastDay, TEXT("shop JSON round-trip preserves restock clock"));

		// Clean state for the host.
		Inventory->ResetCollection();
		Shop->ResetPurchaseState();
		DeckLogic->ResetToDefaults();
	}
}

FString DAEconomyTests::Run(
	UDAInventorySubsystem* Inventory,
	UDAShopSubsystem* Shop,
	UDADeckLogic* DeckLogic,
	UCardDatabaseSubsystem* Database)
{
	FTestReport Report;
	if (!Inventory || !Shop || !DeckLogic || !Database)
	{
		Report.Check(false, TEXT("all economy subsystems are available"));
		return Report.ToString();
	}

	Report.CheckEqual(Database->GetCardCount(), 1200, TEXT("card database has 1200 cards"));
	Report.CheckEqual(Shop->GetPackCount(), 48, TEXT("shop loaded 48 packs"));
	Report.CheckTrue(DeckLogic->GetPlayerDecksRef().Num() > 0, TEXT("deck logic loaded player decks"));

	TestCatalogue(Report, Shop, Database);
	TestInventory(Report, Inventory, Database);
	TestPacks(Report, Inventory, Shop, Database);
	TestDorothysGift(Report, Inventory, Shop, Database);
	TestBulkEconomy(Report, Inventory, Shop, Database);
	TestPendingPackGrants(Report, Inventory, Shop);
	TestDeckCatalogue(Report, DeckLogic, Database);
	TestDecks(Report, Inventory, DeckLogic, Database);
	TestShop(Report, Inventory, Shop, DeckLogic);

	// Leave a clean, playable default state in case the caller did not exit.
	Inventory->ResetCollection();
	Shop->ResetPurchaseState();
	DeckLogic->ResetToDefaults();

	UE_LOG(LogDuelAcademyIsland, Display, TEXT("DAEconomySelfTest: %d passed, %d failed."), Report.Passed, Report.Failed);
	return Report.ToString();
}
