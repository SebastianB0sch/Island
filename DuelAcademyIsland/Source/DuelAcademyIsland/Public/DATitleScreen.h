// Duel Academy Island - title / new game / continue overlay (Canvas).
//
// Presentation and navigation only. The HUD owns the actual game-flow calls:
//   OnNewGame  -> UDAStorySubsystem::StartOpeningFresh()
//   OnContinue -> UDASaveSubsystem::LoadSlot() + UDAStorySubsystem::StartOpening()
// Options are backed by UDASettings (A02) and persisted through its autosave.
//
// The title is a modal overlay above the world HUD and every other UI screen.

#pragma once

#include "CoreMinimal.h"
#include "DAUIScreen.h"

class ADAHUD;
class APlayerController;
class UCanvas;
class UDACalendarSubsystem;
class UDASaveSubsystem;
class UDASettings;
class UFont;
class UGameInstance;
class UWorld;

enum class EDATitlePanel : uint8
{
	Main,
	Continue,
	Options,
	Credits,
	ConfirmNewGame
};

/** One row in the continue list, rebuilt from UDASaveSubsystem::EnumerateSlots. */
struct FDATitleSlotView
{
	int32 SlotIndex = INDEX_NONE;
	FString SlotName;
	FString Label;
	FString PlayerName;
	FString Title;
	FString Dorm;
	FString DateLine;
	FString Playtime;
	int32 DP = 0;
	bool bExists = false;
	bool bCorrupt = false;
	bool bUsingBackup = false;
	bool bAutosave = false;
};

/** Kept as an alias so existing code and tests keep compiling. */
using FDATitleHitTarget = FDAUIHitTarget;

DECLARE_MULTICAST_DELEGATE(FDATitleNewGameSignature);
DECLARE_MULTICAST_DELEGATE_OneParam(FDATitleContinueSignature, int32 /*SlotIndex*/);
DECLARE_MULTICAST_DELEGATE(FDATitleOptionsChangedSignature);
DECLARE_MULTICAST_DELEGATE(FDATitleClosedSignature);

/**
 * Canvas title screen. ADAHUD creates one instance, opens it on a normal
 * launch (unless a story/debug harness is starting) and forwards Tick/Draw.
 */
class FDATitleScreen : public FDAUIScreen
{
public:
	explicit FDATitleScreen(ADAHUD* InOwner);
	virtual ~FDATitleScreen() override;

	// ------------------------------------------------------------------ lifecycle
	void Open();
	void Close();
	bool IsOpen() const { return bOpen; }

	EDATitlePanel GetPanel() const { return Panel; }
	void ShowPanel(EDATitlePanel InPanel);

	// ------------------------------------------------------------------ data
	void RefreshSlots();
	const TArray<FDATitleSlotView>& GetSlots() const { return Slots; }
	bool HasAnySave() const;
	bool HasUsableSave() const;
	int32 GetLatestSlotIndex() const;

	void SetStatusMessage(const FString& InMessage, bool bError = false);

	// ------------------------------------------------------------------ frame
	void Update(float DeltaSeconds);
	virtual void Draw(UCanvas* InCanvas) override;

	// ------------------------------------------------------------------ navigation (tests / HUD)
	void MoveSelection(int32 Delta);
	bool ConfirmSelection();
	int32 GetSelection() const { return Selection; }

	// ------------------------------------------------------------------ integration
	FDATitleNewGameSignature OnNewGame;
	FDATitleContinueSignature OnContinue;
	FDATitleOptionsChangedSignature OnOptionsChanged;
	FDATitleClosedSignature OnClosed;

private:
	// ---- helpers (canvas primitives, fonts, hit targets: FDAUIScreen) ----
	UDASaveSubsystem* GetSaveSubsystem() const;
	UDASettings* GetSettings() const;
	UDACalendarSubsystem* GetCalendar() const;

	void LoadOptionsFromSettings();
	void ApplyOptionsToSettings(bool bPersist);
	void AdjustSelectedOption(int32 Direction);
	void ActivateMainItem();
	void ActivateContinueSlot();
	void ActivateOptionRow();
	void BackToMain();
	void UpdateSelectionClamp();
	void MoveContinueSelection(int32 Delta);
	void HandleClickAtMouse();
	void HandleHit(const FDATitleHitTarget& Hit);

	FString FormatSlotDate(const FString& SavedAtUtc, int32 Year, int32 MonthIndex, int32 Day, int32 Period) const;
	static FString FormatPlaytime(double Seconds);
	FString GetVersionText() const;
	bool LoadCredits();
	int32 GetVisibleCreditLines() const;

	// ---- drawing ----
	void DrawBackground();
	void DrawMain();
	void DrawContinue();
	void DrawOptions();
	void DrawCredits();
	void DrawConfirmNewGame();
	void DrawFooter();
	void DrawStatus();
	void DrawMenuButton(const FString& Label, int32 Index, float X, float Y, float W, float H, bool bSelected);
	void DrawSlotCard(const FDATitleSlotView& Slot, int32 Index, float X, float Y, float W, float H, bool bSelected);
	void DrawOptionRow(const FString& Label, const FString& Value, int32 Index, float X, float Y,
		float W, float H, bool bSelected);
	void DrawBackButton(float PanelX, float PanelY, float PanelW, float PanelH);

	// ---- runtime ----
	bool bOpen = false;
	EDATitlePanel Panel = EDATitlePanel::Main;
	int32 Selection = 0;
	int32 HoveredIndex = INDEX_NONE;
	int32 CreditsScroll = 0;
	int32 ContinueScroll = 0;
	float Elapsed = 0.f;
	float StatusTime = 0.f;
	FString StatusMessage;
	bool bStatusError = false;

	TArray<FDATitleSlotView> Slots;
	TArray<FString> CreditsLines;

	// Options mirrored from UDASettings.
	int32 TextSpeedIndex = 1;
	bool bAutoAdvance = false;
	int32 BgmPercent = 80;
	int32 SfxPercent = 80;
};
