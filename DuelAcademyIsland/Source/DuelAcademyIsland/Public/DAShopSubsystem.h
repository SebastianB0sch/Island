// Duel Academy Island - Dorothy's card shop.
//
// Loads the 48-pack catalogue from Content/Data/Shop/packs.json, evaluates
// month/event/title/counter/pack-completion unlocks, and runs an atomic
// DP -> pack -> inventory purchase. A02 owns DP; the subsystem talks to it
// through the small wallet delegate bundle below.

#pragma once

#include "CoreMinimal.h"
#include "DAEconomyTypes.h"
#include "DASaveGame.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DAShopSubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAOnPackPurchased, const FDAEPurchaseResult&, Result, int32, RemainingDP);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FDAOnShopChanged);

/** Save-friendly shop state. A02 embeds this in the profile save. */
USTRUCT(BlueprintType)
struct FDAEShopSaveData
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	int32 Version = 1;

	/** Only used while the shop runs on its standalone fallback wallet. */
	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	int32 CachedDP = 3000;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	bool bInternalWallet = true;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	TMap<FString, int32> LastPurchaseDay;

	UPROPERTY(BlueprintReadOnly, Category = "Economy|Save")
	TMap<FString, int32> PurchaseCounts;
};

UCLASS()
class DUELACADEMYISLAND_API UDAShopSubsystem : public UGameInstanceSubsystem, public IDASavePayloadProvider
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	// ------------------------------------------------ A02 save interface
	virtual FString GetSaveSectionName() const override { return TEXT("shop"); }
	virtual bool WriteSaveSection(TSharedPtr<FJsonObject>& OutSection) const override;
	virtual bool ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError) override;

	// ------------------------------------------------------------ catalog

	UFUNCTION(BlueprintPure, Category = "Economy|Shop")
	int32 GetPackCount() const { return Packs.Num(); }

	UFUNCTION(BlueprintPure, Category = "Economy|Shop")
	TArray<FDAEPackDef> GetPacks() const { return Packs; }

	/** C++ accessor; use GetPacks for Blueprint. */
	const TArray<FDAEPackDef>& GetPacksRef() const { return Packs; }

	/** All 48 rows, locked or not, with the current block/status text for the shop UI. */
	UFUNCTION(BlueprintCallable, Category = "Economy|Shop")
	TArray<FDAEPackView> GetCatalogue() const;

	/** Only rows whose unlock conditions are currently satisfied. */
	UFUNCTION(BlueprintCallable, Category = "Economy|Shop")
	TArray<FDAEPackView> GetVisiblePacks() const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Shop")
	bool GetPackView(const FString& PackId, FDAEPackView& OutView) const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Shop")
	bool GetPackDef(const FString& PackId, FDAEPackDef& OutPack) const;

	/** Non-owning definition lookup for the inventory's OpenPack path. */
	const FDAEPackDef* FindPack(const FString& PackId) const;

	UFUNCTION(BlueprintPure, Category = "Economy|Shop")
	FString GetUnlockReason(const FString& PackId) const;

	UFUNCTION(BlueprintPure, Category = "Economy|Shop")
	float GetPackCompletionPercent(const FString& PackId) const;

	UFUNCTION(BlueprintPure, Category = "Economy|Shop")
	float GetCollectionPercent() const;

	UFUNCTION(BlueprintPure, Category = "Economy|Shop")
	int32 GetLastPurchaseDay(const FString& PackId) const;

	UFUNCTION(BlueprintPure, Category = "Economy|Shop")
	int32 GetNextAvailableDay(const FString& PackId) const;

	// ------------------------------------------------------------ purchase

	UFUNCTION(BlueprintCallable, Category = "Economy|Shop")
	bool CanPurchase(const FString& PackId, FString& OutReason) const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Shop")
	bool PurchasePack(const FString& PackId, int32 Seed, FDAEPurchaseResult& OutResult);

	/** Data validation used by the self-test and A10; logs and returns the problem list. */
	TArray<FString> ValidateCatalogue() const;

	// ------------------------------------------------------------ wallet / unlocks

	/** A02 integration. Passing handlers replaces the internal fallback wallet. */
	void SetWalletHandlers(
		TFunction<int32()> InGetDP,
		TFunction<bool(int32)> InSpendDP,
		TFunction<void(int32, const FString&)> InCreditDP);

	void ClearWalletHandlers();

	/** True while the standalone 3,000 DP fallback wallet is active. */
	UFUNCTION(BlueprintPure, Category = "Economy|Shop")
	bool IsUsingInternalWallet() const { return bInternalWallet; }

	UFUNCTION(BlueprintPure, Category = "Economy|Shop")
	int32 GetDP() const;

	/** Standalone/testing wallet setter. Clears any A02 handlers. */
	UFUNCTION(BlueprintCallable, Category = "Economy|Shop")
	void SetDebugDP(int32 NewDP);

	/** A02/A03 integration: push a fresh snapshot whenever calendar/flags/titles change. */
	void SetUnlockContextProvider(TFunction<FDAEUnlockContext()> InProvider);

	/** Direct snapshot setter (used by tests and simple hosts). */
	UFUNCTION(BlueprintCallable, Category = "Economy|Shop")
	void SetUnlockContext(const FDAEUnlockContext& NewContext);

	UFUNCTION(BlueprintPure, Category = "Economy|Shop")
	FDAEUnlockContext GetUnlockContextCopy() const;

	FDAEUnlockContext GetUnlockContext() const;

	/** Re-evaluates and notifies the UI after calendar/flags change. */
	UFUNCTION(BlueprintCallable, Category = "Economy|Shop")
	void RefreshUnlocks();

	// ------------------------------------------------------------ save

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	FString ExportStateJson() const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	bool ImportStateJson(const FString& Json, FString& OutError);

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	FDAEShopSaveData GetSaveData() const;

	UFUNCTION(BlueprintCallable, Category = "Economy|Save")
	bool ApplySaveData(const FDAEShopSaveData& Data, FString& OutError);

	/** Clears restock history and the fallback wallet; used by new game and tests. */
	UFUNCTION(BlueprintCallable, Category = "Economy|Shop")
	void ResetPurchaseState();

	// ------------------------------------------------------------ delegates

	UPROPERTY(BlueprintAssignable, Category = "Economy|Shop")
	FDAOnPackPurchased OnPackPurchased;

	UPROPERTY(BlueprintAssignable, Category = "Economy|Shop")
	FDAOnShopChanged OnShopChanged;

private:
	bool LoadPacks(FString& OutError);
	bool CheckPurchase(const FString& PackId, FString& OutReason, EDAEPurchaseBlock& OutBlock) const;
	bool EvaluateUnlock(const FDAEPackDef& Pack, FString& OutReason) const;
	bool IsConditionMet(const FDAEUnlockCondition& Condition, FString& OutReason) const;
	bool SpendDP(int32 Amount, const FString& Reason);
	void CreditDP(int32 Amount, const FString& Reason);
	void MarkPurchased(const FString& PackId);
	FDAEPackView MakeView(const FDAEPackDef& Pack) const;

	TArray<FDAEPackDef> Packs;
	TMap<FString, int32> PackIndexById;
	TMap<FString, int32> LastPurchaseDay;
	TMap<FString, int32> PurchaseCounts;

	FDAEUnlockContext UnlockContext;
	TFunction<FDAEUnlockContext()> UnlockContextProvider;

	TFunction<int32()> GetDPHandler;
	TFunction<bool(int32)> SpendDPHandler;
	TFunction<void(int32, const FString&)> CreditDPHandler;

	int32 CachedDP = 3000;
	bool bInternalWallet = true;
	bool bLoaded = false;
	FString LoadError;
};
