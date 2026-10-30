// Duel Academy Island - opponent roster, decks, AI profiles and duel-request state.
//
// Data-first subsystem. It never touches the duel rules engine directly; A04/A09
// consume the structs and ids exposed here. All content lives in
// Content/Data/Opponents (roster.json, decks/*.json, ai/*.json).

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DAOpponentSubsystem.generated.h"

/** One recurring schedule slot. An empty Interior means the exterior zone is enough. */
USTRUCT(BlueprintType)
struct FDAOpponentScheduleSlot
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FString> Weekdays;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FString> Periods;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Zone;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Interior;
};

/** A place this duelist can be found, used by map/PDA markers. */
USTRUCT(BlueprintType)
struct FDAOpponentLocation
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Zone;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Interior;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Name;
};

/** Access gates for a duelist. Empty fields mean "no requirement". */
USTRUCT(BlueprintType)
struct FDAOpponentAccess
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString RequiresFlag;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString RequiresTitle;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString RequiresDorm;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	bool bEventOnly = false;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 MinDay = 0;
};

USTRUCT(BlueprintType)
struct FDAOpponentEvolutionRule
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Id;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 AfterWins = 1;

	/** Counter key in the player profile, e.g. wins_chazz. Empty means wins against this opponent. */
	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Counter;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Deck;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Description;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Confidence;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Source;
};

USTRUCT(BlueprintType)
struct FDAOpponentEmailThread
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Id;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Subject;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString UnlockFlag;
};

USTRUCT(BlueprintType)
struct FDAOpponentEmail
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString UnlockFlag;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Address;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FDAOpponentEmailThread> Threads;
};

USTRUCT(BlueprintType)
struct FDAOpponentDuelRequest
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString UnlockFlag;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 MinWins = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 CooldownDays = 1;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 MaxPerDay = 1;
};

USTRUCT(BlueprintType)
struct FDAOpponentGift
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Id;

	/** "dp", "card", "pack" */
	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Type;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 Amount = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 CardId = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Event;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Confidence;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Source;
};

USTRUCT(BlueprintType)
struct FDAOpponentWalkHome
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	bool bEnabled = false;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Zone;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FString> Weekdays;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Period;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Flag;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Confidence;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Source;
};

/** A single duelist as loaded from Content/Data/Opponents/roster.json. */
USTRUCT(BlueprintType)
struct FDAOpponentDef
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Id;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FString> Aliases;

	/** ranked | staff | event | exam */
	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Role;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 Rank = 0;

	/** Slifer | Ra | Obelisk | Staff | Event | Exam */
	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Dorm;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 Year = 1;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Title;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString AIProfile;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FString> Decks;

	/** A01 canon signature cards for traceability; not a full deck list. */
	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<int32> SignatureCardIds;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FString> SignatureCards;

	/** A01 canon gift card ids, kept separate from the authored Christmas gift rules. */
	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<int32> CanonGiftCardIds;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString CanonSource;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString CanonConfidence;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString DefaultDeck;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FDAOpponentEvolutionRule> EvolutionRules;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FDAOpponentLocation> Locations;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FDAOpponentScheduleSlot> Schedule;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FDAOpponentAccess Access;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FDAOpponentEmail Email;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FDAOpponentDuelRequest DuelRequest;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FDAOpponentGift> Gifts;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<int32> Ante;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FDAOpponentWalkHome WalkHome;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Confidence;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Source;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Notes;

	/** Convenience lookup used by the schedule UI and validators. */
	bool IsEventOnly() const { return Access.bEventOnly || Role.Equals(TEXT("event"), ESearchCase::IgnoreCase); }
};

/** Opponent deck template. Main deck is Cards; Fusion/Extra is Extra. */
USTRUCT(BlueprintType)
struct FDAOpponentDeckDef
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Id;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Opponent;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Name;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Variant;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Confidence;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Source;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Notes;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<int32> Cards;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<int32> Extra;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<int32> Side;
};

/** Deck-specific AI policy loaded from Content/Data/Opponents/ai/*.json. */
USTRUCT(BlueprintType)
struct FDAIProfileDef
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Id;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Label;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Strategy;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 Difficulty = 2;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	float Aggression = 0.7f;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TMap<FString, float> Weights;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TMap<FString, float> Thresholds;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TMap<FString, bool> BoolThresholds;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FString> PreferredCardNames;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FString> AvoidCardNames;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Confidence;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Source;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString Notes;
};

USTRUCT(BlueprintType)
struct FDAOpponentEmailRuntime
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	bool bUnlocked = false;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FString> UnlockedThreads;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TArray<FString> ReadThreads;
};

/** Transient state A02 should fold into the profile/save payload. */
USTRUCT(BlueprintType)
struct FDAOpponentRuntimeState
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TMap<FString, int32> Wins;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TMap<FString, int32> Losses;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TMap<FString, int32> Draws;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TMap<FString, FDAOpponentEmailRuntime> Emails;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	TMap<FString, int32> RequestsToday;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 RequestDay = -1;
};

USTRUCT(BlueprintType)
struct FDAOpponentDuelOutcome
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString OpponentId;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	bool bPlayerWon = false;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	bool bDraw = false;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 Wins = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	int32 Losses = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	FString EvolutionDeckId;

	UPROPERTY(BlueprintReadOnly, Category = "Opponent")
	bool bEvolutionUnlocked = false;
};

/**
 * Loads the full GBA roster and its deck/AI data.
 *
 * Baseline contract:
 *  - A09 asks for a duelist, a deck id and an AI profile; it does not read JSON.
 *  - A02 stores FDAOpponentRuntimeState; this subsystem does not write save files.
 *  - A04's duel request should carry FDAOpponentDef::DefaultDeck or
 *    ResolveDeckFor(). Puzzle/exam requests are owned by UDAExamSubsystem.
 */
UCLASS()
class DUELACADEMYISLAND_API UDAOpponentSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	/** Idempotent loader. Returns false on a missing/invalid roster; decks with warnings are skipped. */
	bool Reload(FString& OutError);

	const FDAOpponentDef* FindOpponent(const FString& OpponentId) const;
	const FDAOpponentDeckDef* FindDeck(const FString& DeckId) const;
	const FDAIProfileDef* FindAIProfile(const FString& ProfileId) const;

	/** Raw deck arrays for an A04/A06 adapter; false when the deck id is unknown. */
	bool GetDeckCards(const FString& DeckId, TArray<int32>& OutMain, TArray<int32>& OutExtra) const;

	const TArray<FDAOpponentDef>& GetOpponents() const { return Opponents; }
	const TArray<FDAOpponentDeckDef>& GetDecks() const { return DeckList; }
	const TArray<FDAIProfileDef>& GetAIProfiles() const { return AIProfileList; }
	TArray<FString> GetDuelistIds() const;
	TArray<FString> GetDeckIds() const;

	/** Ranked duelists sorted by rank, then event/staff/exam. */
	TArray<const FDAOpponentDef*> GetDuelistsByRank() const;

	/** Dorm/title/flag/day gate. Empty reason on success. */
	bool IsDuelistUnlocked(const FString& OpponentId, const FString& PlayerTitle, const FString& PlayerDorm,
		const TSet<FString>& Flags, int32 DayIndex, FString& OutReason) const;

	/** Whether the opponent is scheduled in this zone/interior at this weekday/period. */
	bool CanDuelAtLocation(const FString& OpponentId, const FString& Zone, const FString& Interior,
		const FString& Weekday, const FString& Period, FString& OutReason) const;

	/** Returns the default deck or the highest satisfied evolution deck. */
	FString ResolveDeckFor(const FString& OpponentId, const TMap<FString, int32>& Counters) const;

	/** Increments win/loss/draw counters and reports the evolution state after the duel. */
	FDAOpponentDuelOutcome RecordDuelResult(const FString& OpponentId, bool bPlayerWon, bool bDraw = false);

	int32 GetWins(const FString& OpponentId) const;
	int32 GetLosses(const FString& OpponentId) const;

	bool IsEmailUnlocked(const FString& OpponentId, const FString& ThreadId) const;
	bool UnlockEmail(const FString& OpponentId, const FString& ThreadId);
	bool MarkEmailRead(const FString& OpponentId, const FString& ThreadId);

	bool CanRequestDuel(const FString& OpponentId, int32 DayIndex, int32 PlayerWins, FString& OutReason) const;
	bool ConsumeDuelRequest(const FString& OpponentId, int32 DayIndex, int32 PlayerWins, FString& OutReason);
	void ResetDailyRequests(int32 DayIndex);

	const FDAOpponentRuntimeState& GetRuntimeState() const { return RuntimeState; }
	void SetRuntimeState(const FDAOpponentRuntimeState& InState) { RuntimeState = InState; }
	void ResetRuntimeState() { RuntimeState = FDAOpponentRuntimeState(); }

private:
	bool LoadRosterFile(const FString& Path, FString& OutError);
	bool LoadDeckFile(const FString& Path, FString& OutError);
	void LoadDeckDirectory(const FString& Directory, TArray<FString>& OutWarnings);
	void LoadAIProfileDirectory(const FString& Directory, TArray<FString>& OutWarnings);

	TArray<FDAOpponentDef> Opponents;
	TMap<FString, int32> OpponentIndex;

	TArray<FDAOpponentDeckDef> DeckList;
	TMap<FString, int32> DeckIndex;

	TArray<FDAIProfileDef> AIProfileList;
	TMap<FString, int32> AIProfileIndex;

	FDAOpponentRuntimeState RuntimeState;
	bool bLoaded = false;
};
