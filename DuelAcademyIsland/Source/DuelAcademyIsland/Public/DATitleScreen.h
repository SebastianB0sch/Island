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

struct FDATitleHitTarget
{
	FString Action;
	int32 Index = INDEX_NONE;
	float X = 0.f;
	float Y = 0.f;
	float W = 0.f;
	float H = 0.f;

	bool Contains(const FVector2D& Point) const
	{
		return Point.X >= X && Point.X <= X + W && Point.Y >= Y && Point.Y <= Y + H;
	}
};

DECLARE_MULTICAST_DELEGATE(FDATitleNewGameSignature);
DECLARE_MULTICAST_DELEGATE_OneParam(FDATitleContinueSignature, int32 /*SlotIndex*/);
DECLARE_MULTICAST_DELEGATE(FDATitleOptionsChangedSignature);
DECLARE_MULTICAST_DELEGATE(FDATitleClosedSignature);

/**
 * Canvas title screen. ADAHUD creates one instance, opens it on a normal
 * launch (unless a story/debug harness is starting) and forwards Tick/Draw.
 */
class FDATitleScreen
{
public:
	explicit FDATitleScreen(ADAHUD* InOwner);
	~FDATitleScreen();

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
	void Draw(UCanvas* InCanvas);

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
	// ---- helpers ----
	UWorld* GetWorld() const;
	UGameInstance* GetGameInstance() const;
	APlayerController* GetPlayerController() const;
	UDASaveSubsystem* GetSaveSubsystem() const;
	UDASettings* GetSettings() const;
	UDACalendarSubsystem* GetCalendar() const;
	UFont* GetFont(bool bLarge) const;

	void LoadOptionsFromSettings();
	void ApplyOptionsToSettings(bool bPersist);
	void AdjustSelectedOption(int32 Direction);
	void ActivateMainItem();
	void ActivateContinueSlot();
	void ActivateOptionRow();
	void BackToMain();
	void UpdateSelectionClamp();
	void HandleClickAtMouse();
	void HandleHit(const FDATitleHitTarget& Hit);
	void AddHit(const FString& Action, int32 Index, float X, float Y, float W, float H);
	void PlaySfx(const TCHAR* SoundName, float Volume = 1.f) const;

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
	void DrawPanel(float X, float Y, float W, float H, const FLinearColor& Fill, const FLinearColor& Accent);
	void DrawRect(const FLinearColor& Color, float X, float Y, float W, float H);
	void DrawText(const FString& Str, float X, float Y, const FLinearColor& Color, float InScale,
		bool bCenter = false, UFont* Font = nullptr);
	void Diamond(const FVector2D& C, float R, const FLinearColor& Color);
	FVector2D Measure(const FString& Str, float InScale, UFont* Font = nullptr) const;
	TArray<FString> WrapText(const FString& Str, float MaxWidth, float InScale, UFont* Font = nullptr) const;
	void DrawMenuButton(const FString& Label, int32 Index, float X, float Y, float W, float H, bool bSelected);
	void DrawSlotCard(const FDATitleSlotView& Slot, int32 Index, float X, float Y, float W, float H, bool bSelected);
	void DrawOptionRow(const FString& Label, const FString& Value, int32 Index, float X, float Y,
		float W, float H, bool bSelected);
	void DrawBackButton(float PanelX, float PanelY, float PanelW, float PanelH);

	// ---- runtime ----
	TWeakObjectPtr<ADAHUD> OwnerHUD;
	APlayerController* PlayerOwner = nullptr;
	UCanvas* Canvas = nullptr;

	bool bOpen = false;
	EDATitlePanel Panel = EDATitlePanel::Main;
	int32 Selection = 0;
	int32 HoveredIndex = INDEX_NONE;
	int32 CreditsScroll = 0;
	float Elapsed = 0.f;
	float UIScale = 1.f;
	float StatusTime = 0.f;
	FString StatusMessage;
	bool bStatusError = false;

	TArray<FDATitleSlotView> Slots;
	TArray<FString> CreditsLines;
	TArray<FDATitleHitTarget> HitTargets;

	// Options mirrored from UDASettings.
	int32 TextSpeedIndex = 1;
	bool bAutoAdvance = false;
	int32 BgmPercent = 80;
	int32 SfxPercent = 80;
};
