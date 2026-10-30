// Duel Academy Island - the PDA shell (Canvas).
//
// Eight tabs matching the GBA PDA: Map, Calendar, Deck, Mail, Save, Options,
// Records and Limitation. This pass provides the navigation shell, real
// fast-travel/collection data where it already exists, and clearly marked
// placeholder panes for the subsystems that are still landing:
//
//   A02 Profile/Calendar/Save/Settings  -> FDAPDAProfileView, Calendar, Save, Options
//   A03 Story/Mail                      -> FDAPDAMailView
//   A06 Inventory/Deck                  -> FDAPDADeckView
//   A07 Records/Limitation              -> FDAPDARecordRow, FDAPDALimitRow
//
// Integration contract: assign ViewModelBuilder from the owning system to fill
// the view each time the PDA opens or changes tab, and listen to OnAction for
// row activations. The UI never implements gameplay rules.

#pragma once

#include "CoreMinimal.h"

class ADAHUD;
class APlayerController;
class UCanvas;
class UFont;
class UGameInstance;
class UWorld;

enum class EDAPDATab : uint8
{
	Map = 0,
	Calendar,
	Deck,
	Mail,
	Save,
	Options,
	Records,
	Limitation,
	Count
};

inline constexpr int32 DAPDATabCount = 8;

/** Header data (A02). */
struct FDAPDAProfileView
{
	FString PlayerName = TEXT("New Student");
	FString DormName = TEXT("Slifer Red");
	FString TitleName = TEXT("Apprentice Duelist");
	FString DateLine = TEXT("Saturday, October 7  -  Year 1");
	FString Period = TEXT("AM");
	int32 DP = 3000;
	int32 Cards = 0;
	bool bPlaceholder = true;
};

/** One cell of the calendar grid (A02). */
struct FDAPDACalendarCell
{
	int32 Day = 0;
	bool bExam = false;
	bool bEvent = false;
	bool bToday = false;
	FString Note;
};

/** Month view (A02). FirstWeekday: 0 = Sunday ... 6 = Saturday (GBA week). */
struct FDAPDACalendarView
{
	FString MonthName = TEXT("October");
	int32 Year = 1;
	int32 FirstWeekday = 0;
	TArray<FDAPDACalendarCell> Days;
	bool bPlaceholder = true;
};

/** One player deck (A06). */
struct FDAPDADeckSummary
{
	FString Id;
	FString Name;
	FString Subtitle;
	int32 MainCount = 0;
	int32 ExtraCount = 0;
	bool bValid = true;
	FString Validation;
};

/** Deck tab content (A06). */
struct FDAPDADeckView
{
	TArray<FDAPDADeckSummary> Decks;
	FString Note;
	bool bPlaceholder = true;
};

/** One email (A03). */
struct FDAPDAMailView
{
	FString Id;
	FString From;
	FString Subject;
	FString Preview;
	FString Body;
	FString Date;
	bool bRead = false;
	bool bDuelRequest = false;
};

/** One save slot (A02). */
struct FDAPDASaveSlotView
{
	FString Id;
	FString Label;
	FString Date;
	FString PlayerName;
	FString Dorm;
	FString Title;
	int32 DP = 0;
	bool bOccupied = false;
	bool bAutosave = false;
	bool bCorrupt = false;
	bool bUsingBackup = false;
};

/** One option row. Activating cycles Values and emits options.changed. */
struct FDAPDAOptionRow
{
	FString Id;
	FString Label;
	TArray<FString> Values;
	int32 ValueIndex = 0;
	FString Help;
};

/** One records / stats row (A02/A07). */
struct FDAPDARecordRow
{
	FString Label;
	FString Value;
	bool bHighlight = false;
};

/** One limitation-list entry (A01/A07). */
struct FDAPDALimitRow
{
	FString CardName;
	FString Status;
	bool bBanned = false;
};

/** Everything the PDA draws. Systems override only the tabs they own. */
struct FDAPDAViewModel
{
	FDAPDAProfileView Profile;
	FDAPDACalendarView Calendar;
	FDAPDADeckView Deck;
	TArray<FDAPDAMailView> Mail;
	TArray<FDAPDASaveSlotView> SaveSlots;
	TArray<FDAPDAOptionRow> Options;
	TArray<FDAPDARecordRow> Records;
	TArray<FDAPDALimitRow> Limitations;
	FString FooterNote;
};

/** Clickable region registered while drawing. */
struct FDAPDAHitTarget
{
	FString Action;
	FString Payload;
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

DECLARE_MULTICAST_DELEGATE_OneParam(FDAPDATabChangedSignature, EDAPDATab /*NewTab*/);
DECLARE_MULTICAST_DELEGATE_TwoParams(FDAPDAActionSignature, FName /*ActionId*/, const FString& /*Payload*/);
DECLARE_MULTICAST_DELEGATE(FDAPDAClosedSignature);

/**
 * Canvas PDA widget. ADAHUD owns one instance, ticks it while open and draws
 * it after the world HUD. All input is polled (keyboard, gamepad and mouse),
 * matching the existing map/duel UI pattern.
 */
class FDAPDAUI
{
public:
	explicit FDAPDAUI(ADAHUD* InOwner);
	~FDAPDAUI();

	// ------------------------------------------------------------------ lifecycle
	void Open(EDAPDATab Tab = EDAPDATab::Map);
	void Close();
	void Toggle(EDAPDATab Tab = EDAPDATab::Map);
	bool IsOpen() const { return bOpen; }

	void SetTab(EDAPDATab Tab);
	void NextTab(int32 Delta);
	EDAPDATab GetTab() const { return ActiveTab; }

	static const TCHAR* TabFallback(EDAPDATab Tab);
	static const TCHAR* TabSlug(EDAPDATab Tab);
	static FString TabLabel(EDAPDATab Tab);

	// ------------------------------------------------------------------ frame
	void Update(float DeltaSeconds);
	void Draw(UCanvas* InCanvas);

	// ------------------------------------------------------------------ data / integration
	/** Calls ViewModelBuilder (when bound) and rebuilds the placeholder data. */
	void RefreshViewModel();

	FDAPDAViewModel& GetViewModel() { return ViewModel; }
	const FDAPDAViewModel& GetViewModel() const { return ViewModel; }
	void SetViewModel(const FDAPDAViewModel& InViewModel) { ViewModel = InViewModel; }

	/** A02/A03/A06/A07 assign this to fill their tabs from live subsystems. */
	TFunction<void(FDAPDAUI&)> ViewModelBuilder;

	/** Row activations the owning HUD (or a later screen) should handle. */
	FDAPDAActionSignature OnAction;
	FDAPDATabChangedSignature OnTabChanged;
	FDAPDAClosedSignature OnClosed;

	// ------------------------------------------------------------------ navigation (tests / HUD)
	void MoveSelection(int32 Delta);
	bool ActivateSelection();
	int32 GetSelection() const { return Selection; }
	void SetSelection(int32 InSelection);

private:
	// ---- helpers ----
	UWorld* GetWorld() const;
	UGameInstance* GetGameInstance() const;
	UFont* GetFont(bool bLarge) const;

	void BuildPlaceholderViewModel();
	void NormalizeViewModel();

	void DrawRect(const FLinearColor& Color, float X, float Y, float W, float H);
	void DrawText(const FString& Str, float X, float Y, const FLinearColor& Color, float InScale,
		bool bCenter = false, UFont* Font = nullptr);
	void DrawPanel(float X, float Y, float W, float H, const FLinearColor& Fill, const FLinearColor& Accent);
	void Diamond(const FVector2D& C, float R, const FLinearColor& Color);
	FVector2D Measure(const FString& Str, float InScale, UFont* Font = nullptr) const;
	TArray<FString> WrapText(const FString& Str, float MaxWidth, float InScale, UFont* Font = nullptr) const;
	void AddHit(const FString& Action, int32 Index, float X, float Y, float W, float H,
		const FString& Payload = FString());
	void HandleClickAtMouse();
	void HandleHit(const FDAPDAHitTarget& Hit);
	void ActivateRow(int32 Index);
	void PlaySfx(const TCHAR* SoundName, float Volume = 1.f) const;

	int32 RowCountForTab(EDAPDATab Tab) const;
	void EnsureSelectionVisible(int32 VisibleRows);
	void RefreshRows();

	FString RowLabel(int32 Index, FString& OutSubtitle, FLinearColor& OutAccent, bool& bOutDisabled) const;
	FString RowDetailTitle(int32 Index) const;
	FString RowDetailBody(int32 Index) const;

	// ---- drawing ----
	void DrawHeader();
	void DrawTabBar();
	void DrawContent();
	void DrawListPanel(float X, float Y, float W, float H);
	void DrawDetailPanel(float X, float Y, float W, float H);
	void DrawCalendarGrid(float X, float Y, float W, float H);
	void DrawFooter();

	// ---- runtime ----
	TWeakObjectPtr<ADAHUD> OwnerHUD;
	APlayerController* PlayerOwner = nullptr;
	UCanvas* Canvas = nullptr;

	EDAPDATab ActiveTab = EDAPDATab::Map;
	int32 Selection = 0;
	int32 ListScroll = 0;
	int32 HoveredTab = INDEX_NONE;
	int32 HoveredRow = INDEX_NONE;
	float UIScale = 1.f;
	float Elapsed = 0.f;
	bool bOpen = false;

	FDAPDAViewModel ViewModel;
	TArray<FDAPDAHitTarget> HitTargets;
};
