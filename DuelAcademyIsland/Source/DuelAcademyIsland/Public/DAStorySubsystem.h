// Duel Academy Island - story runtime for the opening and full campaign scaffold.
//
// UDAStorySubsystem owns the serializable scene queue, resolves dialogue keys
// through A09's dialogue UI, applies A02/A06 outcomes, and starts duels through
// A09's existing deck-select entry point. It never draws UI or moves actors.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Dom/JsonObject.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DAEventGraph.h"
#include "DASaveGame.h"
#include "DAStorySubsystem.generated.h"

class ADAHUD;
class UDAProfileSubsystem;
class UDACalendarSubsystem;
struct FDADialogueLine;

/** One selectable branch attached to a dialogue/choice line. */
struct FDAStoryChoice
{
	FString Id;
	FString Text;
	FString NextScene;
	FString NextKey;
	TArray<TSharedPtr<FJsonObject>> Requirements;
	TArray<TSharedPtr<FJsonObject>> Outcomes;
	TSharedPtr<FJsonObject> Raw;
};

/** One resolved dialogue line from Content/Data/Story/dialogue/opening.json. */
struct FDAStoryLine
{
	FString Key;
	FString Speaker;
	FString Portrait;
	FString Expression;
	FString Text;
	FString Next;
	TArray<FDAStoryChoice> Choices;
	TSharedPtr<FJsonObject> Input;
	TSharedPtr<FJsonObject> Raw;
};

/** One command in a serializable scene queue. */
enum class EDAStoryCommandType : uint8
{
	Dialogue,
	Choice,
	Camera,
	MoveNpc,
	Fade,
	Wait,
	Banner,
	PlaySfx,
	Music,
	Duel,
	Reward,
	SetFlag,
	End,
	Unknown
};

struct FDAStoryCommand
{
	EDAStoryCommandType Type = EDAStoryCommandType::Unknown;
	FString CommandId;
	FString Key;
	FString Speaker;
	FString Portrait;
	FString TextKey;
	FString Anchor;
	FString Npc;
	FString Title;
	FString Subtitle;
	FString Style;
	FString Sfx;
	FString Track;
	FString OpponentId;
	FString OpponentName;
	FString OpponentDeckId;
	FString Mode;
	FString ScenarioId;
	FString OnWin;
	FString OnLose;
	FString OnDraw;
	FString NextScene;
	FString RewardId;
	FString FlagName;
	int32 Dp = 0;
	int32 TurnLimit = 0;
	bool bOptional = false;
	bool bTutorial = false;
	bool bCountsAsWin = false;
	bool bAwardDP = true;
	bool bCompleteEvent = true;
	bool bEnterFreeRoam = false;
	bool bFlagValue = true;
	bool bSkippable = true;
	float Duration = 0.f;
	TSharedPtr<FJsonObject> Raw;
};

/** One scene loaded from Content/Data/Story/scenes/opening.json. */
struct FDAStoryScene
{
	FString Id;
	FString EventId;
	TArray<FDAStoryCommand> Commands;
	TSharedPtr<FJsonObject> Raw;
};

/** Pending duel state, including the counters used to infer win/loss. */
struct FDAStoryPendingDuel
{
	FString OpponentId;
	FString OpponentName;
	FString OpponentDeckId;
	FString Mode;
	FString OnWin;
	FString OnLose;
	FString OnDraw;
	bool bTutorial = false;
	bool bOpened = false;
	float Elapsed = 0.f;
	int32 PreWinsJaden = 0;
	int32 PreWinsSyrus = 0;
	int32 PreWinsTotal = 0;
	int32 PreDuels = 0;
	int32 PreDraws = 0;
};

/**
 * Story runtime for the opening slice.
 *
 * Public flow:
 *   StartOpening() / StartOpeningFresh() -> StartEvent("E01") -> PumpQueue
 *   Dialogue/Choice commands pause; A09 callbacks resume on the next tick.
 *   Advance()/Choose() are for input/automation/tests.
 *   SaveState()/LoadState() serialize the queue and applied rewards.
 */
UCLASS()
class DUELACADEMYISLAND_API UDAStorySubsystem : public UGameInstanceSubsystem, public IDASavePayloadProvider
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	static UDAStorySubsystem* Get(const UObject* WorldContext);

	// ---------------------------------------------------------------- data / flow
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	bool LoadOpeningData();

	/**
	 * Additive loader for the 35-event campaign scaffold. Merges events, scenes,
	 * dialogue and the email table into the opening maps. Full E01 is skipped so
	 * opening.json stays authoritative. Safe to call more than once.
	 */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	bool LoadFullCampaignData();

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	bool IsFullCampaignLoaded() const { return bFullCampaignLoaded; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	int32 GetLoadedEventCount() const { return EventGraph.GetEvents().Num(); }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	int32 GetEmailContactCount() const { return EmailContacts.Num(); }

	/** Contact ids loaded from Content/Data/Story/emails.json (sorted). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	TArray<FString> GetEmailContactIds() const;

	/** Message ids declared for a contact (data order). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	TArray<FString> GetEmailMessageIds(const FString& ContactId) const;

	/** Duel-request ids declared for a contact (data order). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	TArray<FString> GetEmailDuelRequestIds(const FString& ContactId) const;

	/** Story duel requests unlocked by events/emails (sorted). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	TArray<FString> GetUnlockedDuelIds() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	bool IsDuelUnlocked(const FString& DuelId) const;

	/** Unopened packs granted by story data until A06 exposes a pack inventory. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	TArray<FString> GetPendingPackGrants() const;

	/** Consume one pending pack grant (A06/A09 handoff). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	bool ConsumePendingPackGrant(const FString& PackId);

	/** Continue/resume the opening. Uses the current profile name if initialized. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	void StartOpening();

	/** Clean opening run: reset profile/calendar and choose the default starter deck. */
	void StartOpeningFresh();

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	void StartEvent(const FString& EventId);

	/** Whether StartEvent would accept the id (exists and has a loaded scene). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	bool CanStartEvent(const FString& EventId, FString& OutReason);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	void Advance();

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	void Choose(int32 OptionIndex);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	bool IsRunning() const { return bRunning; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	FString GetCurrentEventId() const { return CurrentEventId; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	FString GetCurrentSceneId() const { return CurrentSceneId; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	int32 GetCurrentCommandIndex() const { return CommandIndex; }

	/** Integration hook for A04/A09/A10 when the duel result is known. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	void NotifyDuelResult(bool bPlayerWon, bool bDraw);

	/** True while the current scene is blocked on a duel result. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	bool HasPendingDuel() const { return bWaitingForDuel; }

	/**
	 * Attempt to start a talk-triggered event for this NPC. This is the world
	 * interaction hook that the auto-start path deliberately skips.
	 */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	bool NotifyTalkToNPC(const FString& NpcId);

	/** Count one walk-home trip with a partner; three with the same partner sets the E31 flag. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	void NotifyWalkHome(const FString& PartnerId);

	/** Count a weekend spent in the player's room; three weekends sets the E30 flag. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	void NotifyRoomStay();

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	void SetPlayerName(const FString& NewName);

	/** New-game setup hook: record/activate one of the three starter decks. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	void SelectStarterDeck(const FString& DeckId);

	// ---------------------------------------------------------------- schedules
	/**
	 * Minimal A08 schedule query. Returns the best matching location/anchor for
	 * an NPC on a weekday/period; date overrides win by priority.
	 */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	bool GetScheduledNpcLocation(const FString& NpcId, const FString& Weekday, const FString& Period,
		FString& OutLocation, FString& OutAnchor);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	bool GetScheduledNpcLocationNow(const FString& NpcId, FString& OutLocation, FString& OutAnchor);

	// ---------------------------------------------------------------- tests
	/** Headless opening run: resets state, auto-advances, and verifies the slice. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	bool RunSelfTest();

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	FString GetLastSelfTestReport() const { return LastSelfTestReport; }

	/**
	 * Headless full-campaign audit: 35 events, unique ids, scene/dialogue/reward
	 * resolution, A07 opponent/deck validation and 12-month availability.
	 */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	bool RunFullStorySelfTest();

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	FString GetLastFullSelfTestReport() const { return LastFullSelfTestReport; }

	/**
	 * Headless in-engine playthrough: fresh profile/opening, 365 simulated days,
	 * every E02-E33 event started and driven through its real scene queue, with
	 * manual Advance/Choose and NotifyDuelResult(true, false).
	 */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Story")
	bool RunStoryPlaythroughTest();

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Story")
	FString GetLastPlaythroughReport() const { return LastPlaythroughReport; }

	/** Log the current scene/queue state to the output log. */
	void DebugLogState() const;

	// ---------------------------------------------------------------- save
	FString SaveState() const;
	bool LoadState(const FString& Json, FString& OutError);

	// IDASavePayloadProvider
	virtual FString GetSaveSectionName() const override;
	virtual bool WriteSaveSection(TSharedPtr<FJsonObject>& OutSection) const override;
	virtual bool ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError) override;

private:
	bool Tick(float DeltaSeconds);

	ADAHUD* ResolveHUD() const;
	UDAProfileSubsystem* ResolveProfile() const;
	UDACalendarSubsystem* ResolveCalendar() const;

	bool LoadJsonObject(const FString& RelativePath, TSharedPtr<FJsonObject>& Out, FString& OutError) const;
	bool LoadContentJsonObject(const FString& RelativeToContentData, TSharedPtr<FJsonObject>& Out, FString& OutError) const;
	void ParseEvents(const TSharedPtr<FJsonObject>& Root);
	void ParseScenes(const TSharedPtr<FJsonObject>& Root, bool bMerge = false);
	void ParseDialogue(const TSharedPtr<FJsonObject>& Root, bool bMerge = false);
	void ParseSchedules(const TSharedPtr<FJsonObject>& Root);
	void ParseRewards(const TSharedPtr<FJsonObject>& Root, bool bMerge = false);
	void ParseEmails(const TSharedPtr<FJsonObject>& Root);

	void BindDialogueDelegates(ADAHUD* HUD);
	void HandleDialogueClosed(const FString& ConversationId);
	void HandleChoiceMade(const FString& ConversationId, int32 OptionIndex);

	bool PumpQueue();
	bool ExecuteCommand(const FDAStoryCommand& Command, bool& bOutBlocked);
	void StartScene(const FString& SceneId, int32 StartIndex = 0);
	int32 FindCommandIndexForKey(const FString& Key) const;
	int32 FindCommandIndexForKey(const FString& SceneId, const FString& Key) const;
	void FinishScene();
	void FinishEvent(bool bComplete, bool bEnterFreeRoam);
	void TryStartNextAvailableEvent();

	void ApplyEventOutcomes(const FString& EventId);
	void ApplyOutcomes(const TArray<TSharedPtr<FJsonObject>>& Outcomes);
	void ApplyRewardById(const FString& RewardId);
	void ApplyRewardCommand(const FDAStoryCommand& Command);
	void ApplySetFlag(const FString& Flag, bool bValue);
	void ApplyDeckGrant(const FString& DeckId);
	bool EnsureStarterDeck(const FString& PreferredDeck = TEXT("fire"));

	bool EvaluateConditions(const TArray<TSharedPtr<FJsonObject>>& Conditions) const;
	void ApplyChoiceInternal(int32 OptionIndex);

	FDAStoryLine* FindLine(const FString& Key);
	const FDAStoryLine* FindLine(const FString& Key) const;
	FString ResolveText(const FString& Text) const;
	FString GetPlayerNameForDisplay() const;
	FString GetPlayerNameSpelled() const;
	void BuildDialogueLine(const FDAStoryLine& Line, bool bChoice, FDADialogueLine& OutLine) const;

	void RequestContinue();
	void ResolvePendingDuel(bool bWon, bool bDraw);
	void SimulateDuelResult(bool bWon, bool bDraw);
	void CapturePendingDuel(const FDAStoryCommand& Command);

	void SetCalendarFromJson(const TSharedPtr<FJsonObject>& Object);
	void SetObjective(const FString& Id, const FString& Text);
	void CompleteEvent(const FString& EventId);
	bool IsEventCompleteRuntime(const FString& EventId) const;
	void ApplyTemporaryTitle(const FString& Title);
	void RestorePreviousTitle();
	void UnlockDuel(const FString& DuelId);

	void ResetRuntimeState();
	void LogState(const FString& Prefix) const;
	void TryRegisterSaveProvider();

	bool EvaluateScheduleConditions(const TSharedPtr<FJsonObject>& Conditions) const;
	bool MatchScheduleDate(const TSharedPtr<FJsonObject>& DateObject) const;
	bool MatchSchedulePeriod(const TSharedPtr<FJsonObject>& Object, const FString& Period) const;
	bool MatchScheduleWeekday(const TSharedPtr<FJsonObject>& Object, const FString& Weekday) const;

	/** Recursively gathers flag ids / counters from event conditions for the audit. */
	void CollectConditionState(const TSharedPtr<FJsonObject>& Condition, TSet<FString>& OutFlags,
		TSet<FString>& OutCounters, TSet<FString>& OutEvents) const;
	void CollectEventState(const FDAEventDefinition& Event, TSet<FString>& OutFlags,
		TSet<FString>& OutCounters, TSet<FString>& OutEvents) const;

private:
	FDAEventGraph EventGraph;
	TMap<FString, FDAStoryScene> Scenes;
	TMap<FString, FDAStoryLine> Lines;
	TMap<FString, FString> SpeakerNames;
	TMap<FString, FLinearColor> SpeakerColors;
	TMap<FString, TSharedPtr<FJsonObject>> Rewards;
	TMap<FString, TSharedPtr<FJsonObject>> ScheduledNpcs;
	TMap<FString, TSharedPtr<FJsonObject>> EmailContacts;
	TMap<FString, TSharedPtr<FJsonObject>> FullCampaignEventDocs;
	TMap<FString, FString> Objectives;
	TMap<FString, int32> PendingPackGrants;

	TSet<FString> CompletedEvents;
	TSet<FString> AppliedRewardIds;
	TSet<FString> FullCampaignEventIds;
	TSet<FString> UnlockedDuels;

	FString CurrentEventId;
	FString CurrentSceneId;
	TArray<FDAStoryCommand> CurrentCommands;
	int32 CommandIndex = 0;

	bool bLoaded = false;
	bool bFullCampaignLoaded = false;
	bool bRunning = false;
	bool bHeadless = false;
	bool bFastForward = false;
	bool bFreeRoam = false;
	bool bOpeningStarted = false;
	bool bWaitingForDialogue = false;
	bool bWaitingForChoice = false;
	bool bWaitingForDuel = false;
	bool bWaitingForTimer = false;
	bool bPendingContinue = false;
	bool bPendingTextInput = false;
	bool bDialogueDelegatesBound = false;
	bool bSaveProviderRegistered = false;
	bool bAutoOpeningRequested = false;
	bool bAutoOpeningStarted = false;
	bool bAutoSelfTestRequested = false;
	bool bAutoSelfTestStarted = false;
	bool bAutoFullSelfTestRequested = false;
	bool bAutoFullSelfTestStarted = false;
	bool bSuppressAutoStart = false;
	bool bManualAudience = false;

	// Diagnostics reset by the playthrough harness before each event.
	int32 PlaythroughMissingDialogue = 0;
	int32 PlaythroughMissingScene = 0;
	int32 PlaythroughUnknownCommand = 0;
	int32 PlaythroughUnknownOutcome = 0;
	int32 PlaythroughDialogueCommands = 0;
	int32 PlaythroughChoiceCommands = 0;
	int32 PlaythroughDuelCommands = 0;
	int32 PlaythroughDuelResolved = 0;
	int32 PlaythroughRewardCommands = 0;
	int32 PlaythroughFlagCommands = 0;
	int32 PlaythroughOutcomesApplied = 0;

	FString PendingTextInputKey;
	TArray<FDAStoryChoice> ActiveChoices;
	FString ActiveChoiceConversationId;
	FString ActiveChoiceLineKey;
	FDAStoryPendingDuel PendingDuel;
	FString SelectedStarterDeck;
	FString LastSelfTestReport;
	FString LastFullSelfTestReport;
	FString LastPlaythroughReport;
	FString PreviousTitle;

	float WaitRemaining = 0.f;
	float AutoStartDelay = 2.f;
	/** Throttles the free-roam availability poll so date/flag events start without a scene transition. */
	float FreeRoamPollTimer = 0.f;
	TWeakObjectPtr<ADAHUD> BoundHUD;
	FTSTicker::FDelegateHandle TickerHandle;
};
