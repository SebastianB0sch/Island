// Duel Academy Island - canvas HUD: location banners, compass, minimap, island map + fast travel.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "DADialogueUI.h"
#include "DADeckUI.h"
#include "DADuelUI.h"
#include "DAExamUI.h"
#include "DAPDAUI.h"
#include "DAShopUI.h"
#include "DATitleScreen.h"
#include "DAHUD.generated.h"

class ADALocationVolume;
class ADAIslandManager;
class UDAIslandSubsystem;
class UFont;
class UTexture2D;

UCLASS()
class DUELACADEMYISLAND_API ADAHUD : public AHUD
{
	GENERATED_BODY()

public:
	ADAHUD();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void DrawHUD() override;

	bool IsMapOpen() const { return bMapOpen; }
	bool IsDuelOpen() const { return DuelUI.IsValid() && DuelUI->IsOpen(); }
	bool IsPDAOpen() const { return PDAUI.IsValid() && PDAUI->IsOpen(); }
	bool IsDialogueOpen() const { return DialogueUI.IsValid() && DialogueUI->IsOpen(); }
	bool IsTitleOpen() const { return TitleScreen.IsValid() && TitleScreen->IsOpen(); }
	bool IsShopOpen() const { return ShopUI.IsValid() && ShopUI->IsOpen(); }
	bool IsDeckEditorOpen() const { return DeckUI.IsValid() && DeckUI->IsOpen(); }
	bool IsExamOpen() const { return ExamUI.IsValid() && ExamUI->IsOpen(); }
	bool IsGameplayUIOpen() const { return IsShopOpen() || IsDeckEditorOpen() || IsExamOpen(); }
	bool IsModalOpen() const { return bMapOpen || bHelpOpen || IsDuelOpen() || IsPDAOpen() || IsDialogueOpen() || IsTitleOpen() || IsGameplayUIOpen(); }

	/** Opens the starter-deck picker for a duel against the given opponent. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Duel")
	void OpenDuelDeckSelect(const FString& OpponentId = TEXT("jaden"),
		const FString& OpponentName = TEXT("Jaden Yuki"), const FString& OpponentDeckId = TEXT("jaden"));

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Duel")
	void StartDuelWithDeck(const FString& DeckId);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Duel")
	void CloseDuel();

	/** Debug-only: summon the first legal monster in the player's opening hand. */
	void DebugAutoPlayOpening();

	/** Debug-only: select the first card in the player's hand. */
	void DebugSelectFirstHandCard();

	/** Debug-only: finish the current duel with a player win. */
	void DebugFinishDuelWin();

	UFont* GetSmallFont() const { return SmallFont; }
	UFont* GetBigFont() const { return BigFont; }

	void ToggleMap();
	void ToggleHelp();
	void MoveMapSelection(int32 Delta);
	ADALocationVolume* GetSelectedZone() const;
	ADALocationVolume* PickZoneUnderCursor() const { return HoveredZone.Get(); }
	ADALocationVolume* PickZoneRowUnderCursor() const;
	/** Closes the map and sends the player to Zone (or the highlighted entry). */
	void TravelToZone(ADALocationVolume* Zone = nullptr);

	// ---------------------------------------------------------------- dialogue / PDA
	/** Opens the dialogue box. A03 calls this with a resolved story command queue. */
	void BeginDialogue(const TArray<FDADialogueLine>& Lines, const FString& ConversationId = FString());

	/** Convenience for a single line (interaction barks, debug). */
	void BeginDialogueLine(const FDADialogueLine& Line);

	void CloseDialogue();

	void OpenPDA(EDAPDATab Tab = EDAPDATab::Map);

	void ClosePDA();

	void TogglePDA(EDAPDATab Tab = EDAPDATab::Map);

	// ---------------------------------------------------------------- title / new game
	void OpenTitle();
	void CloseTitle();

	// ---------------------------------------------------------------- gameplay screens
	void OpenShop();
	void CloseShop();
	void OpenDeckEditor(const FString& DeckId = FString());
	void CloseDeckEditor();
	void OpenExam(int32 MonthIndex = 0);
	void CloseExam();

	/** Test-only: seed the transient profile/decks/inventory/mail state used by -DAGameplayUITest. */
	void PrepareGameplayUITestState();

	FDADialogueUI* GetDialogueUI() const { return DialogueUI.Get(); }
	FDAPDAUI* GetPDAUI() const { return PDAUI.Get(); }
	FDATitleScreen* GetTitleScreen() const { return TitleScreen.Get(); }
	FDAShopUI* GetShopUI() const { return ShopUI.Get(); }
	FDADeckUI* GetDeckUI() const { return DeckUI.Get(); }
	FDAExamUI* GetExamUI() const { return ExamUI.Get(); }

private:
	// ---------------------------------------------------------------- UI hosting
	void UpdateInputMode();
	void ApplySettingsToUI();
	void WireEconomySystems();
	void HandlePDAAction(FName ActionId, const FString& Payload);
	void HandlePDAClosed();
	void HandleDialogueClosed(const FString& ConversationId);
	void HandleTitleNewGame();
	void HandleTitleContinue(int32 SlotIndex);
	void HandleTitleOptionsChanged();
	void HandleTitleClosed();
	void HandleShopClosed();
	void HandleDeckClosed();
	void HandleExamClosed();

private:
	// drawing helpers
	float S() const { return UIScale; }
	void Text(const FString& Str, float X, float Y, const FLinearColor& Color, float Scale, bool bCenter = false, UFont* Font = nullptr);
	FVector2D Measure(const FString& Str, float Scale, UFont* Font = nullptr) const;
	TArray<FString> Wrap(const FString& Str, float MaxWidth, float Scale, UFont* Font = nullptr) const;
	void Panel(float X, float Y, float W, float H, const FLinearColor& Accent, float Alpha = 0.72f);
	void Diamond(const FVector2D& C, float R, const FLinearColor& Color);
	void Arrow(const FVector2D& C, float R, float YawDeg, const FLinearColor& Color);
	FVector2D WorldToMapUV(const FVector& World) const;

	void DrawIntro(float Time);
	void DrawBanner(UDAIslandSubsystem* Sub, float Time);
	void DrawCompass(UDAIslandSubsystem* Sub);
	void DrawMinimap(UDAIslandSubsystem* Sub);
	void DrawClock(ADAIslandManager* M);
	void DrawPrompt();
	void DrawMessage(UDAIslandSubsystem* Sub);
	void DrawHelp();
	void DrawMap(UDAIslandSubsystem* Sub);

	UPROPERTY(Transient)
	TObjectPtr<UFont> SmallFont;

	UPROPERTY(Transient)
	TObjectPtr<UFont> BigFont;

	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> MapTexture;

	FVector2D MapMin = FVector2D(-153600.0, -153600.0);
	FVector2D MapMax = FVector2D(153600.0, 153600.0);

	bool bMapOpen = false;
	bool bHelpOpen = false;
	bool bTitleWasShown = false;
	int32 MapSelection = 0;
	float UIScale = 1.f;
	float StartTime = 0.f;
	TUniquePtr<FDADuelUI> DuelUI;
	TUniquePtr<FDADialogueUI> DialogueUI;
	TUniquePtr<FDAPDAUI> PDAUI;
	TUniquePtr<FDATitleScreen> TitleScreen;
	TUniquePtr<FDAShopUI> ShopUI;
	TUniquePtr<FDADeckUI> DeckUI;
	TUniquePtr<FDAExamUI> ExamUI;
	TWeakObjectPtr<ADALocationVolume> HoveredZone;
};
