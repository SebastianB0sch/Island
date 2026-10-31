// Duel Academy Island - puzzle data loader and deterministic in-engine replay.
//
// A07 owns the JSON in Content/Data/Puzzles.  This file is the small adapter
// between that JSON and A04's FDuelScenario/FDuelEngine APIs.  It deliberately
// contains no puzzle-specific hard-coded logic: the authored solution steps are
// the only script that is executed.

#pragma once

#include "CoreMinimal.h"
#include "DADuelRules.h"

class FDuelEngine;
class UCardDatabaseSubsystem;

/** One authored solution step.  Unsupported actions are errors, never skips. */
struct FDAPuzzleSolutionStep
{
	FString Action;
	int32 CardId = 0;
	TArray<int32> TributeCardIds;
	int32 AttackerCardId = 0;
	int32 TargetCardId = 0;
	bool bTargetDirect = false;
	FString Position;
};

/** Parsed P001..P100 record, including the fixed board and the authored line. */
struct FDAPuzzleDefinition
{
	FString Id;
	FString Title;
	FString Objective;
	FString Opponent;
	FString Template;
	int32 Level = 0;
	int32 PlayerLp = 0;
	int32 OpponentLp = 0;
	int32 Seed = 0;
	int32 TurnLimit = 0;
	int32 TimeLimitSeconds = 0;
	int32 RewardDp = 0;
	bool bEngineReady = false;

	TArray<int32> PlayerHand;
	TArray<int32> PlayerDeck;
	TArray<int32> PlayerGraveyard;
	TArray<int32> PlayerExtra;
	TArray<int32> OpponentHand;
	TArray<int32> OpponentDeck;
	TArray<int32> OpponentGraveyard;
	TArray<int32> OpponentExtra;

	TArray<FDuelScenarioCard> PlayerField;
	TArray<FDuelScenarioCard> OpponentField;
	TArray<FDAPuzzleSolutionStep> Solution;
};

/** Result of replaying one authored puzzle through the real duel engine. */
struct FDAPuzzleReplayResult
{
	bool bStarted = false;
	bool bWon = false;
	int32 StepsExecuted = 0;
	int32 PlayerLp = 0;
	int32 OpponentLp = 0;
	int32 PlayerTurns = 0;
	FString Error;
	TArray<FString> StepLog;
};

class DUELACADEMYISLAND_API FDAPuzzleRuntime
{
public:
	/** Loads one puzzle file.  Returns false with a detailed OutError on bad JSON. */
	static bool LoadPuzzleFile(const FString& Path, FDAPuzzleDefinition& OutPuzzle, FString& OutError);

	/** Loads every P*.json in Directory in deterministic filename order. */
	static bool LoadPuzzleDirectory(const FString& Directory, TArray<FDAPuzzleDefinition>& OutPuzzles, FString& OutError);

	/** Builds the fixed board consumed by FDuelEngine::StartScenario. */
	static bool BuildScenario(const FDAPuzzleDefinition& Puzzle, FDuelScenario& OutScenario, FString& OutError);

	/**
	 * Starts the authored scenario and executes every solution step through the
	 * engine.  A puzzle passes only when the player wins on the final step.
	 */
	static bool Replay(UCardDatabaseSubsystem* Database, const FDAPuzzleDefinition& Puzzle,
		FDAPuzzleReplayResult& OutResult, FString& OutError);

	/** Convenience wrapper used by the exam suite for the authored timed puzzle. */
	static bool ReplayById(UCardDatabaseSubsystem* Database, const FString& PuzzleId,
		FDAPuzzleReplayResult& OutResult, FString& OutError);
};
