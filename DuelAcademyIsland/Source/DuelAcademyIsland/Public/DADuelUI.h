// Duel Academy Island - the interactive duel board (rules + Canvas presentation).

#pragma once

#include "CoreMinimal.h"
#include "DADuelEngine.h"

class ADAHUD;
class UCanvas;
class UFont;
class UWorld;
class UGameInstance;
class UCardArtSubsystem;
class UCharacterPortraitSubsystem;
class UTexture;

enum class EDuelUiMode : uint8
{
	None,
	DeckSelect,
	Duel,
	Result
};

enum class EDuelPileType : uint8
{
	None,
	Deck,
	Extra,
	Graveyard,
	Banished
};

struct FDuelHitTarget
{
	FString Action;
	FString Payload;
	int32 Value = 0;
	float X = 0.0f;
	float Y = 0.0f;
	float W = 0.0f;
	float H = 0.0f;

	bool Contains(const FVector2D& Point) const
	{
		return Point.X >= X && Point.X <= X + W && Point.Y >= Y && Point.Y <= Y + H;
	}
};

/** One short visual beat built from a rules-engine event. */
struct FDuelFx
{
	EDuelVisualEventType Type = EDuelVisualEventType::Effect;
	EDuelOwner Side = EDuelOwner::Player;
	int32 CardUid = 0;
	int32 CardId = 0;
	int32 TargetUid = 0;
	int32 TargetCardId = 0;
	int32 Amount = 0;
	int32 Zone = INDEX_NONE;
	int32 TargetZone = INDEX_NONE;
	bool bFaceDown = false;
	bool bDirect = false;
	FString Text;
	FVector2D Source = FVector2D::ZeroVector;
	FVector2D Target = FVector2D::ZeroVector;
	float Elapsed = 0.0f;
	float Duration = 0.8f;
	float Delay = 0.0f;

	bool IsAlive() const { return Elapsed < Duration + Delay; }
	float Alpha() const
	{
		const float Local = FMath::Max(0.0f, Elapsed - Delay);
		const float FadeIn = FMath::Clamp(Local / 0.12f, 0.0f, 1.0f);
		const float FadeOut = FMath::Clamp((Duration - Local) / 0.28f, 0.0f, 1.0f);
		return FMath::Min(FadeIn, FadeOut);
	}
};

/** Terminal payload for a fixed-scenario duel (exam timed puzzles). */
struct FDAScenarioDuelResult
{
	bool bSolved = false;
	bool bTimedOut = false;
	int32 TurnsUsed = 0;
	float SecondsUsed = 0.0f;
	FString ScenarioId;
	FString EndReason;
};

/**
 * Self-contained duel session: owns the deterministic rules engine and draws
 * the full Canvas board (deck picker, hand, field, piles, log, result).
 * ADAHUD forwards Tick/Draw/input to it while it is open.
 */
class FDADuelUI
{
public:
	explicit FDADuelUI(ADAHUD* InOwner);
	~FDADuelUI();

	bool IsOpen() const { return DuelMode != EDuelUiMode::None; }
	bool IsDuelOpen() const { return DuelMode == EDuelUiMode::Duel || DuelMode == EDuelUiMode::Result; }

	// Pinned cross-workstream contract #1 (WS-02 consumes via
	// ADAHUD::GetDuelUI). True iff the most recently opened story deck-select
	// ended without a duel result being recorded (player backed out of the
	// picker, or a story-owned duel closed mid-board without a result). Story
	// treats this as re-present, not as a phantom loss. Cleared the next time
	// a duel result is recorded or a story-owned duel closes with a result.
	bool WasDeckSelectClosedWithoutResult() const;

	/**
	 * U4 layout constants and pure helpers so the headless gate test can pin
	 * the picker's pagination bounds. The single-row panel geometry fits at
	 * most 4 starter decks (the shipped decks.json count); raising the page
	 * size for a future data update must respect the hard cap 6 or the 1600x900
	 * board cannot keep the panels on-screen.
	 */
	static constexpr int32 DeckSelectPageSize = 4;
	static int32 DeckSelectPageCount(int32 NumDecks);
	static int32 DeckSelectPageFirstDeck(int32 Page);

	/**
	 * Pure decision for the no-result-close state machine (contract #1). Only
	 * a story-owned session that was actually open and finished without
	 * bStoryResultPending sets the flag; every other close clears it. Exposed
	 * static for DAA02GateTests; the production flow calls it from CloseDuel.
	 */
	static bool ComputeStoryDuelClosedWithoutResult(bool bOwnedByStoryAtOpen, bool bResultRecordedAtClose, bool bWasOpenAtClose);

	void OpenDeckSelect(const FString& OpponentId = TEXT("jaden"), const FString& OpponentName = TEXT("Jaden Yuki"),
		const FString& OpponentDeckId = TEXT("jaden"), const FString& Mode = TEXT("free"), bool bInAwardDP = true);
	void StartDuelWithDeck(const FString& DeckId);

	/**
	 * Starts a fixed authored scenario (puzzle/exam) without a deck picker and
	 * tracks the scenario turn/time limit.  The terminal result is held until
	 * ConsumeScenarioDuelResult, so the caller can close the result screen first.
	 */
	bool StartScenarioDuel(const FDuelScenario& Scenario, const FString& Mode, bool bInAwardDP, FString& OutError);
	bool IsScenarioDuelActive() const { return bDuelScenarioActive; }
	bool ConsumeScenarioDuelResult(FDAScenarioDuelResult& OutResult);
	/** Records a cancelled duel as a loss, then closes the board. */
	void AbortScenarioDuel();

	void CloseDuel();

	void Update(float DeltaSeconds);
	void Draw(UCanvas* InCanvas);
	void DebugAutoPlayOpening();
	void DebugSelectFirstHandCard();
	void DebugFinishDuelWin();
	/** Screenshot harness: a fixed board with two legal Equip targets and a pending choice. */
	void DebugOpenEquipChoice();

	/**
	 * Test-only (DAA02GateTests): seed the story-ownership marker that the
	 * production open path captures from UDAStorySubsystem::HasPendingDuel so
	 * the headless state machine of contract #1 can be driven. Production flow
	 * must not call this.
	 */
	void DebugSetStoryOwnedDuel(bool bStoryOwned);

private:
	// ---- drawing helpers ----
	UWorld* GetWorld() const;
	UGameInstance* GetGameInstance() const;
	UCardArtSubsystem* GetCardArt() const;
	UCharacterPortraitSubsystem* GetPortraitArt() const;
	UFont* GetFont(bool bLarge) const;
	void DrawRect(const FLinearColor& Color, float X, float Y, float W, float H);
	void DrawText(const FString& Text, const FLinearColor& Color, float X, float Y, UFont* Font, float Scale);
	void DrawTexture(UTexture* Texture, float X, float Y, float W, float H, float U, float V, float UW, float VH,
		const FLinearColor& Tint);
	void DrawLine(float X1, float Y1, float X2, float Y2, const FLinearColor& Color, float Thickness);
	void GetTextSize(const FString& Text, float& OutW, float& OutH, UFont* Font, float Scale) const;
	void DrawPanel(float X, float Y, float Width, float Height, const FLinearColor& Fill, const FLinearColor& Border);
	void DrawShadowText(const FString& Text, float X, float Y, UFont* Font, float Scale,
		const FLinearColor& Color, bool bCenter = false, bool bApplyDuelBoost = true);
	void DrawShadowText(const FString& Text, const FLinearColor& Color, float X, float Y, UFont* Font,
		float Scale, bool bCenter = false, bool bApplyDuelBoost = true);
	float DrawWrappedText(const FString& Text, float X, float Y, float MaxWidth, UFont* Font, float Scale,
		const FLinearColor& Color, float LineSpacing = 4.0f);
	float DuelTextScale(float Scale) const;
	FString DuelTrim(const FString& Text, int32 MaxLength) const;

	void PlaySfx(const TCHAR* SoundName, float Volume = 1.0f) const;
	void ShowToast(const FString& Text, FLinearColor Color = FLinearColor::White);
	void ShowBanner(const FString& Title, const FString& Subtitle = FString());
	void NotifyDuelFinished(bool bPlayerWon);

	// ---- duel flow ----
	void UpdateDuel(float DeltaSeconds);
	void PumpDuelVisualEvents(float DeltaSeconds);
	void UpdateDuelVisuals(float DeltaSeconds);
	bool IsDuelPresentationActive() const;
	void SpawnDuelFx(const FDuelVisualEvent& Event);
	void ResolveDuelFxPath(FDuelFx& OutFx, const FDuelVisualEvent& Event);
	void SpawnDuelFxReaction(const FDuelVisualEvent& Event);
	FVector2D DuelCardCenter(int32 Uid, EDuelOwner FallbackSide, bool bMonsterFallback) const;
	FVector2D DuelZoneCenter(EDuelOwner Side, int32 Zone, bool bMonster) const;
	bool GetDuelCardFx(int32 Uid, float& OutOffsetX, float& OutOffsetY, float& OutScale, float& OutAlpha) const;
	const FDuelFx* FindDuelFx(EDuelVisualEventType Type, int32 Uid) const;
	void DrawDuelHudBar(const FDuelSide& Side, const FString& CharacterId, float X, float Y,
		const FLinearColor& Accent, bool bRight, float LpDisplay);
	void TriggerDuelCutIn(EDuelOwner Side, const FString& Expression, const FString& Title,
		const FString& Subtitle, int32 Priority, float Duration = 2.15f);
	void BuildDuelFxDemo();

	// ---- duel UI ----
	void DrawDuel();
	void DrawDuelDeckSelect();
	void DrawDuelActive();
	void DrawDuelLog();
	void DrawDuelHand(const FDuelSide& PlayerSide);
	void DrawDuelCommandPanel(const FDuelSide& PlayerSide, const FDuelCard* Selected,
		bool bPlayerTurn, bool bAiTurn, bool bChoicePending);
	void DrawDuelResult();
	void DrawDuelPile();
	void DrawDuelChoice();
	void RefreshDuelChoiceState();
	void SubmitDuelChoice();
	void HandleDuelChoiceOption(int32 OptionId);
	void SkipDuelPresentation();
	bool IsDuelChoiceTarget(int32 Uid) const { return DuelChoiceCardUids.Contains(Uid); }
	bool IsDuelChoiceSelected(int32 Uid) const { return DuelChoiceSelected.Contains(Uid); }
	void DrawDuelCard(const FDuelCard& Card, float X, float Y, float W, float H,
		bool bFaceDown, bool bSelected = false, bool bHovered = false, bool bDefense = false,
		bool bChoiceTarget = false);
	void DrawDuelCardFace(int32 CardId, bool bFaceDown, float X, float Y, float W, float H, float Alpha = 1.0f);
	void DrawDuelPortrait(const FString& CharacterId, float X, float Y, float W, float H,
		const FLinearColor& Accent, float Alpha = 1.0f, bool bFaceCrop = true,
		const FString& Expression = FString());
	void DrawDuelCutIn();
	void DrawDuelFx();
	void DrawDuelFxFrame(const FLinearColor& Color, float X, float Y, float W, float H, float Thickness);
	void DrawDuelFxDraw(const FDuelFx& Fx, float T, float Ease, const FLinearColor& SideColor);
	void DrawDuelFxSummon(const FDuelFx& Fx, float T);
	void DrawDuelFxSpellTrap(const FDuelFx& Fx, float T);
	void DrawDuelFxAttack(const FDuelFx& Fx, float T);
	void DrawDuelFxDamage(const FDuelFx& Fx, float T);
	void DrawDuelFxDestroy(const FDuelFx& Fx, float T, float Ease);
	void DrawDuelFxTransfer(const FDuelFx& Fx, float T, float Ease, const FLinearColor& SideColor);
	void DrawDuelFxPosition(const FDuelFx& Fx, float T);
	void DrawDuelFxFusion(const FDuelFx& Fx, float T);
	void DrawDuelFxCost(const FDuelFx& Fx, float T, float Alpha);
	void DrawDuelFxCounter(const FDuelFx& Fx, float T);
	void DrawDuelFxEffect(const FDuelFx& Fx, float T, float Alpha);
	void DrawDuelEventBanner();
	void DrawDuelButton(const FString& Label, const FString& Action, int32 Value,
		float X, float Y, float W, float H, bool bEnabled = true,
		FLinearColor Accent = FLinearColor(0.58f, 0.45f, 0.20f, 0.75f));
	void AddDuelHit(const FString& Action, int32 Value, float X, float Y, float W, float H, const FString& Payload = FString());
	void HandleDuelHit(const FString& Action, int32 Value, const FString& Payload = FString());
	void HandleDuelChoiceHit(const FString& Action, int32 Value);
	bool IsDuelHoverRect(float X, float Y, float W, float H) const;
	void DuelBeginTribute(int32 HandUid, bool bSet);
	void DuelConfirmTribute();
	void DuelCancelTribute();
	void DuelShowMessage(const FString& Message, const FLinearColor& Color = FLinearColor(0.95f, 0.74f, 0.38f, 1.0f));
	FDuelCard* GetDuelSelectedCard();

	float DX(float X) const { return DuelOffsetX + X * DuelScale + DuelShakeX; }
	float DY(float Y) const { return DuelOffsetY + Y * DuelScale + DuelShakeY; }
	float DS(float Value) const { return Value * DuelScale; }

	// ---- owner / presentation ----
	TWeakObjectPtr<ADAHUD> OwnerHUD;
	APlayerController* PlayerOwner = nullptr;
	UCanvas* Canvas = nullptr;

	// Duel UI state.
	TUniquePtr<FDuelEngine> DuelEngine;
	EDuelUiMode DuelMode = EDuelUiMode::None;
	int32 DuelSelectedUid = 0;

	// Pending rules-choice presentation (targets, searches, optional triggers).
	int32 DuelChoiceRequestId = 0;
	int32 DuelChoicePage = 0;
	TSet<int32> DuelChoiceSelected;
	TSet<int32> DuelChoiceCardUids;

	int32 DuelTributeHandUid = 0;
	bool bDuelTributeSet = false;
	TSet<int32> DuelTributeUids;
	EDuelPileType DuelPileType = EDuelPileType::None;
	EDuelOwner DuelPileOwner = EDuelOwner::Player;
	float DuelAiTimer = 0.0f;
	float DuelMessageTimer = 0.0f;
	float DuelResultEnterTime = 0.0f;
	FString DuelMessage;
	FLinearColor DuelMessageColor = FLinearColor(0.95f, 0.74f, 0.38f, 1.0f);
	bool bDuelResultWon = false;
	bool bDuelResultNotified = false;
	float DuelScale = 1.0f;
	float DuelOffsetX = 0.0f;
	float DuelOffsetY = 0.0f;
	FVector2D DuelMousePosition = FVector2D::ZeroVector;
	FString DuelHoverAction;
	int32 DuelHoverValue = 0;
	float DuelHoverCooldown = 0.0f;
	TArray<FDuelHitTarget> DuelHitTargets;

	FString DuelOpponentId = TEXT("jaden");
	FString DuelOpponentName = TEXT("Jaden Yuki");
	FString DuelOpponentDeckId = TEXT("jaden");
	FString DuelModeString = TEXT("free");
	bool bDuelAwardDP = true;
	int32 DuelResultDpEarned = 0;

	// Pinned contract #1 state. bDuelOpenedForStory is captured once at
	// OpenDeckSelect (a story command was waiting for a duel) and survives
	// StartDuelWithDeck so an Escape-on-the-live-board still counts as a story
	// close without a result; CloseDuel folds both flags into the public one.
	bool bDeckSelectClosedWithoutResult = false;
	bool bDuelOpenedForStory = false;

	// U4: deck picker page for decks beyond the single row's page size.
	int32 DeckSelectPage = 0;

	/** One unique token per duel; guards profile rewards against duplicate notification. */
	FString DuelResultToken;

	// Fixed-scenario (timed puzzle) completion state.  It deliberately survives
	// CloseDuel so the examining screen can consume the terminal result.
	bool bDuelScenarioActive = false;
	bool bScenarioResultValid = false;
	float DuelScenarioElapsed = 0.0f;
	FDAScenarioDuelResult ScenarioDuelResult;

	/** True when the result screen should tell the story subsystem on close. */
	bool bStoryResultPending = false;
	bool bStoryResultWon = false;
	bool bStoryResultDraw = false;

	/** Built on the result screen, shown after the player returns to the island. */
	FString DuelResultTitle;
	FString DuelResultMessage;
	FLinearColor DuelResultColor = FLinearColor::White;
	bool bDuelResultDraw = false;

	// Animation / presentation beat state.
	TArray<FDuelVisualEvent> DuelIncomingEvents;
	TArray<FDuelFx> DuelFx;
	float DuelEventPumpTimer = 0.0f;
	float DuelEventGap = 0.22f;
	float DuelPlayerLpDisplay = 8000.0f;
	float DuelOpponentLpDisplay = 8000.0f;
	float DuelPlayerLpHit = 0.0f;
	float DuelOpponentLpHit = 0.0f;
	float DuelShakeTime = 0.0f;
	float DuelShakeStrength = 0.0f;
	float DuelShakeX = 0.0f;
	float DuelShakeY = 0.0f;
	float DuelFlashTime = 0.0f;
	FLinearColor DuelFlashColor = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);
	float DuelEventBannerTime = 0.0f;
	float DuelEventBannerDuration = 1.0f;
	FString DuelEventBannerTitle;
	FString DuelEventBannerSubtitle;
	FLinearColor DuelEventBannerColor = FLinearColor::White;
	float DuelIntroTime = 0.0f;
	float DuelOpponentPortraitPulse = 0.0f;
	float DuelPlayerPortraitPulse = 0.0f;
	bool bDuelEventsPrimed = false;
	bool bDuelAutoEndTurnDone = false;

	// Key-event character cut-in.
	FString DuelCutInCharacter;
	FString DuelCutInExpression;
	FString DuelCutInTitle;
	FString DuelCutInSubtitle;
	FLinearColor DuelCutInAccent = FLinearColor::White;
	EDuelOwner DuelCutInSide = EDuelOwner::Player;
	float DuelCutInTime = 0.0f;
	float DuelCutInDuration = 2.15f;
	float DuelCutInAge = 0.0f;
	int32 DuelCutInPriority = 0;

	// Let the final attack / win event breathe before the result card appears.
	float DuelResultDelay = 0.0f;
	bool bDuelResultPending = false;
	bool bDuelPlayerLowLpWarned = false;
	bool bDuelOpponentLowLpWarned = false;
};
