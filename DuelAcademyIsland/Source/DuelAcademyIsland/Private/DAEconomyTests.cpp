#include "DAEconomyTests.h"

#include "DAInventorySubsystem.h"
#include "DADeckLogic.h"
#include "DAShopSubsystem.h"
#include "DACardRecords.h"
#include "DuelAcademyIsland.h"

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
		for (const FDAEPackDef& Pack : Shop->GetPacksRef())
		{
			Ids.Add(Pack.Id);
			if (Pack.Price <= 0) bPricesValid = false;
			if (Pack.Slots.Num() != Pack.PackSize) bSlotsValid = false;
			if (Pack.bAllCards)
			{
				TArray<int32> All;
				Database->GetCards().GetKeys(All);
				for (const int32 CardId : All)
				{
					Obtainable.Add(CardId);
				}
			}
			for (const FDAERarityPool& Pool : Pack.Pools)
			{
				for (const int32 CardId : Pool.Cards)
				{
					Obtainable.Add(CardId);
				}
			}
		}
		Report.CheckEqual(Ids.Num(), 48, TEXT("pack ids are unique"));
		Report.CheckTrue(bPricesValid, TEXT("every pack has a positive price"));
		Report.CheckTrue(bSlotsValid, TEXT("every pack slot count matches pack size"));
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
		Report.CheckTrue(DefaultDeck->Extra.Num() <= 20, TEXT("default player deck extra <= 20"));

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

		// 20-card extra deck.
		const TArray<int32> Fusions = PickFusionCards(Database, DeckLogic->GetRules(), 21);
		Report.CheckEqual(Fusions.Num(), 21, TEXT("found 21 fusion cards for the extra-deck test"));
		Inventory->ResetCollection();
		GrantCopies(Inventory, Fusions, 1);
		GrantCopies(Inventory, DefaultMain, 1);
		TArray<int32> Extra20(Fusions);
		Extra20.SetNum(20);
		const FDAEDeck ExtraDeck20 = BuildDeck(DefaultMain, Extra20);
		TArray<FDAEDeckError> ExtraErrors20;
		UDADeckLogic::ValidateDeckAgainstRules(ExtraDeck20, DeckLogic->GetRules(), Database, Inventory, true, ExtraErrors20);
		Report.CheckTrue(ExtraErrors20.Num() == 0, TEXT("20-card extra deck is legal"));
		const FDAEDeck ExtraDeck21 = BuildDeck(DefaultMain, Fusions);
		TArray<FDAEDeckError> ExtraErrors21;
		UDADeckLogic::ValidateDeckAgainstRules(ExtraDeck21, DeckLogic->GetRules(), Database, Inventory, false, ExtraErrors21);
		Report.CheckTrue(HasErrorCode(ExtraErrors21, TEXT("extra_too_large")), TEXT("21-card extra deck is rejected"));

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
	TestDecks(Report, Inventory, DeckLogic, Database);
	TestShop(Report, Inventory, Shop, DeckLogic);

	// Leave a clean, playable default state in case the caller did not exit.
	Inventory->ResetCollection();
	Shop->ResetPurchaseState();
	DeckLogic->ResetToDefaults();

	UE_LOG(LogDuelAcademyIsland, Display, TEXT("DAEconomySelfTest: %d passed, %d failed."), Report.Passed, Report.Failed);
	return Report.ToString();
}
