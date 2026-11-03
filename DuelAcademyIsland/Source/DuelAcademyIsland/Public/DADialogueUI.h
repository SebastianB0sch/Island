// Duel Academy Island - code-only Canvas dialogue box.
//
// Presentation only: A03's story subsystem owns the lines, choices and their
// consequences. This class renders the payload (portrait/expression, speaker,
// typewriter text, choice buttons, continue prompt, auto/skip and a basic
// history log) and reports the selected option through OnChoiceMade.
//
// The payload mirrors the story command contract in PORT_MASTERPLAN §4.3:
//   FStoryCommand { Dialogue/Choice, SpeakerId, Portrait, TextKey, Args }
// A03 resolves TextKey -> Text (localization) before calling Begin().

#pragma once

#include "CoreMinimal.h"
#include "DAUIScreen.h"

class ADAHUD;
class APlayerController;
class UCanvas;
class UFont;
class UGameInstance;
class UTexture2D;
class UWorld;
class UCharacterPortraitSubsystem;

/** One dialogue beat. */
struct FDADialogueLine
{
	/** Stable speaker id used for portrait lookup and traceability ("jaden"). */
	FString SpeakerId;

	/** Display name; falls back to SpeakerId when empty. */
	FString SpeakerName;

	/** Optional portrait id override (e.g. "jaden"); empty uses SpeakerId. */
	FString Portrait;

	/** Optional expression id: "neutral", "happy", "angry", "shocked", "sad", ... */
	FString Expression;

	/** Resolved display text. Sample/placeholder text lives in Content/Data/UI/ui.json. */
	FString Text;

	/** When true, Options is shown and the conversation waits for Choose(). */
	bool bChoice = false;

	/** When true, the dialogue shows a text-entry field instead of a normal continue prompt. */
	bool bTextInput = false;
	int32 TextMinLength = 1;
	int32 TextMaxLength = 8;
	FString TextDefault;

	/** Choice labels. */
	TArray<FString> Options;

	/** Optional trace/localization key, e.g. "E01.sheppard_01". */
	FString TextKey;

	/** Optional story node id ("E01.sheppard_01"). */
	FString NodeId;

	/** Optional small subtitle under the speaker name ("Chancellor"). */
	FString SpeakerTitle;

	/** Seconds the line lingers in auto mode before advancing. */
	float AutoAdvanceDelay = 2.2f;

	/** Name plate / choice accent. */
	FLinearColor Accent = FLinearColor(1.f, 0.78f, 0.25f);

	FString GetDisplayName() const { return SpeakerName.IsEmpty() ? SpeakerId : SpeakerName; }
	FString GetDisplayText() const
	{
		if (!Text.IsEmpty())
		{
			return Text;
		}
		return TextKey.IsEmpty() ? FString() : FString::Printf(TEXT("[%s]"), *TextKey);
	}
};

/** One clickable region registered while drawing (alias kept for existing code). */
using FDADialogueHitTarget = FDAUIHitTarget;

DECLARE_MULTICAST_DELEGATE_OneParam(FDADialogueClosedSignature, const FString& /*ConversationId*/);
DECLARE_MULTICAST_DELEGATE_TwoParams(FDADialogueChoiceSignature, const FString& /*ConversationId*/, int32 /*OptionIndex*/);
DECLARE_MULTICAST_DELEGATE_TwoParams(FDADialogueLineSignature, const FString& /*ConversationId*/, int32 /*LineIndex*/);

/**
 * Canvas dialogue widget. ADAHUD owns one instance, ticks it while open and
 * calls Draw() from DrawHUD. All input is polled through the player controller,
 * the same pattern the map and duel UI use (Enhanced Input can swallow keys in
 * GameAndUI mode).
 */
class FDADialogueUI : public FDAUIScreen
{
public:
	explicit FDADialogueUI(ADAHUD* InOwner);
	virtual ~FDADialogueUI() override;

	// ------------------------------------------------------------------ lifecycle
	void Begin(const TArray<FDADialogueLine>& InLines, const FString& InConversationId = FString());
	void BeginLine(const FDADialogueLine& InLine, const FString& InConversationId = FString());
	void Close();

	bool IsOpen() const { return bOpen; }
	bool IsTyping() const { return bTyping; }
	bool IsWaitingForChoice() const;
	bool IsHistoryOpen() const { return bHistoryOpen; }
	bool IsTextEntry() const { return bTextEntry; }
	const FString& GetTextEntryValue() const { return TextEntryBuffer; }
	void ClearTextEntry() { TextEntryBuffer.Reset(); bTextEntry = false; }

	const FString& GetConversationId() const { return ConversationId; }
	int32 GetLineIndex() const { return LineIndex; }
	const TArray<FDADialogueLine>& GetLines() const { return Lines; }
	const TArray<FString>& GetHistory() const { return History; }

	/** Critical story scenes can refuse Escape-close (call after Begin) and require a choice. */
	void SetAllowEscapeClose(bool bAllowed) { bEscapeClose = bAllowed; }
	bool AllowsEscapeClose() const { return bEscapeClose; }

	// ------------------------------------------------------------------ story API
	/** Reveals the current line, advances to the next line, or closes at the end. */
	bool Advance();

	/** Commits a choice on a bChoice line (also advances). */
	bool Choose(int32 OptionIndex);

	/** Immediately closes the conversation (skip button / debug). */
	void SkipConversation();

	void SetAutoAdvance(bool bEnabled, bool bPlaySound = true);
	void ToggleAutoAdvance();
	bool IsAutoAdvance() const { return bAuto; }

	void ToggleHistory();
	void ScrollHistory(int32 Delta);

	void SetTextSpeed(float InCharsPerSecond);
	float GetTextSpeed() const { return CharsPerSecond; }

	// ------------------------------------------------------------------ frame
	void Update(float DeltaSeconds);
	virtual void Draw(UCanvas* InCanvas) override;

	// ------------------------------------------------------------------ integration
	FDADialogueClosedSignature OnDialogueClosed;
	FDADialogueChoiceSignature OnChoiceMade;
	FDADialogueLineSignature OnLineShown;

private:
	// ---- helpers (canvas primitives, fonts, hit targets: FDAUIScreen) ----
	UCharacterPortraitSubsystem* GetPortraitArt() const;

	void DrawTexture(UTexture2D* Texture, float X, float Y, float W, float H, const FLinearColor& Tint);
	/** Dialogue-styled panel (5px accent bar); intentionally hides FDAUIScreen::DrawPanel. */
	void DrawPanel(float X, float Y, float W, float H, const FLinearColor& Fill, const FLinearColor& Accent);

	void DrawPortrait(float X, float Y, float Size, const FDADialogueLine& Line, float Alpha);
	void DrawHistoryOverlay();
	void HandleClickAtMouse();
	void HandleHit(const FDADialogueHitTarget& Hit);
	void UpdateTextEntry();
	void GoToLine(int32 NewIndex);
	void PushLineToHistory();

	// ---- runtime (owner, canvas, scale and hit targets live in FDAUIScreen) ----
	TArray<FDADialogueLine> Lines;
	FString ConversationId;
	int32 LineIndex = 0;
	int32 LastShownLine = INDEX_NONE;

	float Revealed = 0.f;
	float CharsPerSecond = 48.f;
	float AutoTimer = 0.f;
	float SkipTimer = 0.f;
	float Elapsed = 0.f;

	bool bOpen = false;
	bool bTyping = false;
	bool bAuto = false;
	bool bHistoryOpen = false;
	bool bEscapeClose = true;
	bool bTextEntry = false;
	FString TextEntryBuffer;
	int32 TextEntryMinLength = 1;
	int32 TextEntryMaxLength = 8;
	int32 ChoiceSelection = 0;
	int32 HistoryScroll = 0;

	TArray<FString> History;
};

/**
 * Small cached reader for Content/Data/UI/ui.json. Labels and the sample
 * dialogue are data, so no story text is compiled into C++. If the JSON is
 * missing the callers fall back to their own UI-label defaults.
 */
namespace DAUIData
{
	FString Label(const FString& Key, const FString& Fallback);
	bool LoadDialogueSample(const FString& SampleId, TArray<FDADialogueLine>& OutLines);
	bool LoadCredits(TArray<FString>& OutLines);
}
