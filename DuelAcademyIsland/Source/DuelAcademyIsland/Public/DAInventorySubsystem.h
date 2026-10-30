// Duel Academy Island - card trunk / inventory subsystem.
//
// Owns the player's card counts (1-1200), the data-driven ownership copy cap,
// collection statistics and filters, ante hooks, and deterministic pack
// opening. Pack definitions come from UDAShopSubsystem (Content/Data/Shop).

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "DAEconomyTypes.h"
#include "DAProfileSubsystem.h"
#include "DASaveGame.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DAInventorySubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAOnCollectionChanged, int32, CardId, int32, NewCount);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FDAOnInventoryReset);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FDAOnAnteChanged, int32, PendingAnteCount);

UCLASS()
class DUELACADEMYISLAND_API UDAInventorySubsystem : public UGameInstanceSubsystem, public IDASavePayloadProvider, public IDAProfileInventoryInterface
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	// ------------------------------------------------ A02 save/profile interfaces
	virtual FString GetSaveSectionName() const override;
	virtual bool WriteSaveSection(TSharedPtr<FJsonObject>& OutSection) const override;
	virtual bool ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError) override;
	virtual int32 GetOwnedCardCount(int32 CardId) const override { return GetCount(CardId); }
	virtual int32 GetDistinctCardsOwned() const override { return Counts.Num(); }

	// ------------------------------------------------------------ collection

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	int32 GetCount(int32 CardId) const;

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	bool HasCard(int32 CardId, int32 MinCount = 1) const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Inventory")
	int32 AddCard(int32 CardId, int32 Count = 1);

	UFUNCTION(BlueprintCallable, Category = "Economy|Inventory")
	int32 RemoveCard(int32 CardId, int32 Count = 1);

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	bool CanAddCard(int32 CardId, int32 Count = 1) const;

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	bool IsKnownCard(int32 CardId) const;

	/** Adds a starter/event bundle, respecting the ownership cap. Returns the number added. */
	UFUNCTION(BlueprintCallable, Category = "Economy|Inventory")
	int32 GrantStarterCollection(const TArray<int32>& CardIds);

	UFUNCTION(BlueprintCallable, Category = "Economy|Inventory")
	void ResetCollection();

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	TArray<int32> GetCollectionCards() const;

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	TMap<int32, int32> GetCollectionCopy() const { return Counts; }

	/** C++ accessor; use GetCollectionCopy for Blueprint. */
	const TMap<int32, int32>& GetCollection() const { return Counts; }

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	int32 GetCollectionSize() const;

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	int32 GetCatalogSize() const;

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	FDAECollectionStats GetCollectionStats() const;

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	EDAECardRarity GetCardRarity(int32 CardId) const;

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	FString GetCardRarityName(int32 CardId) const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Inventory")
	TArray<int32> FilterCollection(const FDAECardFilter& Filter) const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Inventory")
	TArray<int32> SortCards(const TArray<int32>& CardIds, EDAECardSortKey SortKey, bool bDescending = false) const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Inventory")
	void SetMaxOwnedCopies(int32 NewMax);

	UFUNCTION(BlueprintPure, Category = "Economy|Inventory")
	int32 GetMaxOwnedCopies() const { return MaxOwnedCopies; }

	// ------------------------------------------------------------ pack opening

	/** Open a pack through the shop catalogue. Same non-zero seed = same reveal. */
	UFUNCTION(BlueprintCallable, Category = "Economy|Pack")
	FDAEPackOpenResult OpenPack(const FString& PackId, int32 Seed);

	/** Open a pack definition directly (used by the shop and tests). */
	FDAEPackOpenResult OpenPackDefinition(const FDAEPackDef& Pack, int32 Seed, bool bAddToCollection = true);

	/** Roll a pack without changing the collection; useful for reveal previews. */
	UFUNCTION(BlueprintCallable, Category = "Economy|Pack")
	FDAEPackOpenResult PreviewPack(const FString& PackId, int32 Seed);

	// ------------------------------------------------------------ ante

	/** Remove one copy from the trunk and hold it as an ante stake. */
	UFUNCTION(BlueprintCallable, Category = "Economy|Ante")
	bool RemoveCardForAnte(int32 CardId, const FString& DuelId, const FString& Source);

	/** Return the ante card for this duel to the trunk (win/draw path). */
	UFUNCTION(BlueprintCallable, Category = "Economy|Ante")
	bool ReturnAnteCard(const FString& DuelId);

	/** Permanently lose the ante card for this duel (loss path). */
	UFUNCTION(BlueprintCallable, Category = "Economy|Ante")
	bool CommitAnteLoss(const FString& DuelId);

	UFUNCTION(BlueprintCallable, Category = "Economy|Ante")
	int32 ReturnAllAnte();

	UFUNCTION(BlueprintPure, Category = "Economy|Ante")
	TArray<FDAEAnteRecord> GetPendingAnte() const { return PendingAnte; }

	// ------------------------------------------------------------ save

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	FString ExportStateJson() const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	bool ImportStateJson(const FString& Json, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	FDAEInventorySaveData GetSaveData() const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	bool ApplySaveData(const FDAEInventorySaveData& Data, FString& OutError);

	// ------------------------------------------------------------ delegates

	UPROPERTY(BlueprintAssignable, Category = "Economy|Inventory")
	FDAOnCollectionChanged OnCollectionChanged;

	UPROPERTY(BlueprintAssignable, Category = "Economy|Inventory")
	FDAOnInventoryReset OnInventoryReset;

	UPROPERTY(BlueprintAssignable, Category = "Economy|Ante")
	FDAOnAnteChanged OnAnteChanged;

	// ------------------------------------------------------------ self-test

	/** Runs the full -DAEconomySelfTest suite and returns a human-readable report. */
	FString RunSelfTest();

private:
	void LoadOwnershipLimit();
	void LoadRarityMap();
	void ScheduleSelfTest();
	bool TickSelfTest(float DeltaSeconds);
	static int32 ResolveSeed(int32 Seed);

	UPROPERTY()
	TMap<int32, int32> Counts;

	UPROPERTY()
	TMap<int32, EDAECardRarity> RarityById;

	UPROPERTY()
	TArray<FDAEAnteRecord> PendingAnte;

	UPROPERTY()
	int32 MaxOwnedCopies = 3;

	FTSTicker::FDelegateHandle SelfTestTicker;
	int32 SelfTestAttempts = 0;
};
