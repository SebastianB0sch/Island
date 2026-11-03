// Duel Academy Island - Dorothy's card shop screen (Canvas).
//
// All economy and pack-roll rules stay in UDAShopSubsystem / UDAInventorySubsystem.
// The UI only browses FDAEPackView rows, asks for a purchase and renders
// FDAEPurchaseResult/FDAEPackCardReveal payloads.

#pragma once

#include "CoreMinimal.h"
#include "DAEconomyTypes.h"
#include "DAUIScreen.h"

class UDAShopSubsystem;
class UCardArtSubsystem;

DECLARE_MULTICAST_DELEGATE(FDAShopUIClosedSignature);

class FDAShopUI : public FDAUIScreen
{
public:
	explicit FDAShopUI(ADAHUD* InOwner);
	virtual ~FDAShopUI() override;

	void Open();
	void Close();
	bool IsOpen() const { return bOpen; }

	void Update(float DeltaSeconds);
	virtual void Draw(UCanvas* InCanvas) override;

	const FDAEPurchaseResult& GetLastPurchase() const { return LastPurchase; }

	FDAShopUIClosedSignature OnClosed;

private:
	enum class EPanel : uint8
	{
		Browse,
		Confirm,
		Reveal
	};

	UDAShopSubsystem* GetShop() const;
	UCardArtSubsystem* GetCardArt() const;

	void RefreshCatalogue(bool bKeepSelection);
	void RebuildFiltered();
	void MoveSelection(int32 Delta);
	void ChangeCategory(int32 Delta);
	void OpenConfirm();
	void DoPurchase();
	void HandleClickAtMouse();
	void HandleHit(const FDAUIHitTarget& Hit);
	void SetStatus(const FString& Message, bool bError = false);

	const FDAEPackView* GetSelectedPack() const;
	FString GetPackStatusLine(const FDAEPackView& Pack) const;
	FString GetCategoryLine() const;

	void DrawBrowse();
	void DrawConfirm();
	void DrawReveal();
	void DrawHeader();
	void DrawFooter();
	void DrawStatus();
	void DrawPackRow(const FDAEPackView& Pack, int32 FilteredIndex, float X, float Y, float W, float H, bool bSelected);
	void DrawRevealCard(const FDAEPackCardReveal& Card, int32 Index, float X, float Y, float W, float H);
	FLinearColor RarityColor(EDAECardRarity Rarity) const;

	TArray<FDAEPackView> Catalogue;
	TArray<int32> Filtered;
	TArray<FString> Categories;

	EPanel Panel = EPanel::Browse;
	int32 CategoryIndex = 0;
	int32 Selection = 0;
	int32 ListScroll = 0;
	int32 ConfirmSelection = 0;
	int32 HoveredIndex = INDEX_NONE;
	bool bOpen = false;

	FDAEPurchaseResult LastPurchase;
	float Elapsed = 0.f;
	float StatusTime = 0.f;
	FString StatusMessage;
	bool bStatusError = false;
};
