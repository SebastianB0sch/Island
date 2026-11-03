// Duel Academy Island - deck editor screen (Canvas).
//
// Deck rules, ownership checks, validation, sorting/filtering and mutation all
// live in UDADeckLogic / UDAInventorySubsystem. This screen is presentation and
// input only; every add/remove/swap/rename/copy/erase is an API call.

#pragma once

#include "CoreMinimal.h"
#include "DADeckLogic.h"
#include "DAUIScreen.h"

class UDADeckLogic;
class UDAInventorySubsystem;
class UCardDatabaseSubsystem;

DECLARE_MULTICAST_DELEGATE(FDADeckUIClosedSignature);

class FDADeckUI : public FDAUIScreen
{
public:
	explicit FDADeckUI(ADAHUD* InOwner);
	virtual ~FDADeckUI() override;

	void Open(const FString& DeckId = FString());
	void Close();
	bool IsOpen() const { return bOpen; }

	void Update(float DeltaSeconds);
	virtual void Draw(UCanvas* InCanvas) override;

	FDADeckUIClosedSignature OnClosed;

private:
	enum class EDAFocus : uint8
	{
		Decks,
		Collection,
		DeckCards
	};

	UDADeckLogic* GetDeckLogic() const;
	UDAInventorySubsystem* GetInventory() const;
	UCardDatabaseSubsystem* GetCardDatabase() const;

	void RefreshAll(bool bSelectDeckId = false);
	void RefreshDeckCards();
	void RefreshCollection();
	void MoveSelection(int32 Delta);
	void MoveFocus(int32 Delta);
	void AddOrSwapSelectedCard();
	void RemoveSelectedDeckCard();
	void BeginSwap();
	void CommitNameEdit();
	void BeginRename();
	void CreateNewDeck();
	void CopyCurrentDeck();
	void EraseCurrentDeck();
	void SetCurrentDeckActive();
	void CycleFilter();
	void CycleSort();
	void ToggleExtraMode();
	void UpdateNameEditor();
	void HandleClickAtMouse();
	void HandleHit(const FDAUIHitTarget& Hit);
	void SetStatus(const FString& Message, bool bError = false);

	const FDAEDeck* GetCurrentDeck() const;
	FString GetCurrentDeckId() const;
	const FCardRecord* FindCard(int32 CardId) const;
	FString GetCardName(int32 CardId) const;
	bool IsExtraDeckCard(int32 CardId) const;
	FString GetFilterLabel() const;
	FString GetSortLabel() const;

	void DrawHeader();
	void DrawDeckSlots();
	void DrawCollectionPanel();
	void DrawDeckPanel();
	void DrawRecipesOverlay();
	void DrawNameEditor();
	void DrawEraseConfirm();
	void DrawFooter();
	void DrawStatus();
	void DrawCardRow(int32 CardId, int32 Index, float X, float Y, float W, float H, bool bSelected, bool bDeckRow);

	TArray<FDAEDeck> Decks;
	TArray<int32> Collection;
	TArray<int32> DeckMain;
	TArray<int32> DeckExtra;
	TArray<FFusionRecipeDef> Recipes;

	EDAFocus Focus = EDAFocus::Decks;
	int32 DeckIndex = 0;
	int32 CollectionSelection = 0;
	int32 DeckCardSelection = 0;
	int32 CollectionScroll = 0;
	int32 DeckScroll = 0;
	int32 DeckCardScroll = 0;
	int32 RecipeScroll = 0;
	int32 FilterMode = 0;
	int32 SortMode = 0;
	int32 HoveredIndex = INDEX_NONE;
	int32 PendingSwapCardId = 0;
	bool bPendingSwapExtra = false;
	bool bDeckExtraSelection = false;
	bool bExtraMode = false;
	bool bShowRecipes = false;
	bool bEditingName = false;
	bool bRenameMode = false;
	bool bConfirmErase = false;
	bool bOpen = false;

	FString CurrentDeckId;
	FString NameBuffer;
	FString EditDeckId;
	FString EraseDeckId;
	FString StatusMessage;
	float StatusTime = 0.f;
	bool bStatusError = false;
	float Elapsed = 0.f;
};
