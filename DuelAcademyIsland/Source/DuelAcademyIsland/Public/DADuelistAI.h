// Duel Academy Island - data-driven duelist AI policy.
//
// This is deliberately independent of FDuelEngine. At baseline A04 has not yet
// published an AI hook, so this class is a deterministic policy/scoring stub:
//
//   FDAIDuelSnapshot + FDAIDuelistAI::ChooseAction() -> FDAAIDecision
//
// A04 integration hook (documented in Docs/Opponents_Exams_Notes.md):
//   Add a request/decision pair to the duel engine, e.g.
//     bool FDuelEngine::RequestAiDecision(const FDuelAiSnapshot&, FDuelAiDecision&);
//   and let the engine adapter translate FDuelSide/FDuelCard into the snapshot.
// Until then no engine file is modified and no behaviour changes.

#pragma once

#include "CoreMinimal.h"
#include "DACardRecords.h"
#include "DAOpponentSubsystem.h"
#include "DADuelistAI.generated.h"

class UCardDatabaseSubsystem;

UENUM(BlueprintType)
enum class EDAAIStrategy : uint8
{
	Beatdown,
	Burn,
	Stall,
	Fusion,
	Ritual,
	Control,
	Draw,
	Goblin,
	Machine,
	Fairy,
	Dragon,
	Warrior,
	Beast,
	Insect,
	Rock,
	Spellcaster,
	Aquatic,
	Cyber,
	Ojama,
	AncientGear,
	Amazoness,
	Copycat,
	Toon,
	Dinosaur,
	Shadow,
	Exodia,
	ExamStall,
	Unknown
};

/** Minimal, engine-agnostic snapshot. A04 can fill this from FDuelSide. */
USTRUCT(BlueprintType)
struct FDAAIDuelSnapshot
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	int32 TurnNumber = 0;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	int32 PlayerLp = 8000;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	int32 OpponentLp = 8000;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	TArray<int32> HandCardIds;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	TArray<int32> OwnMonsterIds;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	TArray<int32> OpponentMonsterIds;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	TArray<int32> OwnSpellTrapIds;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	bool bBattlePhase = false;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	bool bCanAttackDirectly = false;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	bool bNormalSummonUsed = false;
};

UENUM(BlueprintType)
enum class EDAAIAction : uint8
{
	None,
	NormalSummon,
	SetMonster,
	ActivateSpell,
	SetSpellTrap,
	ActivateTrap,
	ActivateEffect,
	Attack,
	DirectAttack,
	ChangePosition,
	EndTurn
};

USTRUCT(BlueprintType)
struct FDAAIDecision
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	EDAAIAction Action = EDAAIAction::None;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	int32 CardId = 0;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	int32 TargetCardId = 0;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	int32 Score = 0;

	UPROPERTY(BlueprintReadOnly, Category = "AI")
	FString Reason;
};

/**
 * Deterministic policy used by the roster's AI profiles. It scores cards and
 * picks one abstract action; the engine adapter is responsible for legality,
 * targeting prompts and actually executing the action.
 */
class DUELACADEMYISLAND_API FDAIDuelistAI
{
public:
	FDAIDuelistAI();

	void Configure(const FDAIProfileDef& InProfile, int32 InSeed = 0);
	void SetCardDatabase(const UCardDatabaseSubsystem* InDatabase) { Database = InDatabase; }

	const FDAIProfileDef& GetProfile() const { return Profile; }
	EDAAIStrategy GetStrategy() const { return Strategy; }
	bool IsConfigured() const { return bConfigured; }

	/** Card value from the profile's perspective (not a rules-engine legality check). */
	int32 ScoreCard(const FCardRecord& Card) const;

	/** One abstract decision for the supplied snapshot. Returns None/EndTurn when no play is sensible. */
	FDAAIDecision ChooseAction(const FDAAIDuelSnapshot& Snapshot) const;

	bool ShouldAttack(const FDAAIDuelSnapshot& Snapshot, int32 AttackerCardId, int32 TargetCardId, bool bDirect) const;
	bool ShouldSetTrap(const FDAAIDuelSnapshot& Snapshot) const;

	float GetWeight(const FString& Key, float Default = 0.5f) const;
	int32 GetThreshold(const FString& Key, int32 Default) const;

	static EDAAIStrategy StrategyFromString(const FString& StrategyId);

private:
	int32 ScoreCardId(int32 CardId) const;
	int32 StrategyBonus(const FCardRecord& Card) const;

	FDAIProfileDef Profile;
	EDAAIStrategy Strategy = EDAAIStrategy::Beatdown;
	const UCardDatabaseSubsystem* Database = nullptr;
	FRandomStream Random;
	bool bConfigured = false;
};
