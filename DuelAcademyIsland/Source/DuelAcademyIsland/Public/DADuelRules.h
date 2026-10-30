// Duel Academy Island - shared duel-rules data model.
//
// Plain C++ value types used by FDuelEngine and (eventually) by the UI, the
// effect runtime and the puzzle/exam loaders.  Nothing in this header depends
// on UObject, Slate or the world; it is safe to include from tests and from
// data loaders.
//
// Compatibility note: these types are additive.  The legacy 137-card engine
// keeps its automatic targeting unless a choice is explicitly queued, and the
// legacy automatic Trap flow stays enabled through
// FDuelEngine::SetLegacyAutomaticTraps(true) (the default).

#pragma once

#include "CoreMinimal.h"

/** The two sides of a duel.  Kept here so the rules data model has no engine.h dependency. */
enum class EDuelOwner : uint8
{
	Player,
	Opponent
};

/** Where a card currently lives.  INDEX_NONE / 0 are used when unknown. */
enum class EDuelZone : uint8
{
	None,
	Deck,
	Hand,
	Monster,
	SpellTrap,
	Field,
	Graveyard,
	Banished,
	Extra
};

/** The kind of answer the rules engine needs from a player or the AI. */
enum class EDuelChoiceType : uint8
{
	None,
	SelectCard,
	SelectCards,
	SelectZone,
	YesNo,
	ChainResponse,
	ActivationOrder,
	Ante,
	Generic
};

/** What a chain link represents. */
enum class EDuelChainLinkType : uint8
{
	Spell,
	Trap,
	MonsterEffect,
	Other
};

/** 2006-era spell speeds: 1 normal, 2 quick-play/trap, 3 counter trap. */
enum class EDuelSpellSpeed : uint8
{
	Speed1 = 1,
	Speed2 = 2,
	Speed3 = 3
};

/** Per-card activation policy.  Automatic is the legacy behaviour. */
enum class EDuelActivationMode : uint8
{
	Automatic,
	Manual
};

/** Timing windows used by activation checks. */
enum class EDuelTimingWindow : uint8
{
	None,
	Main1,
	Main2,
	Battle,
	DamageStep,
	EndPhase,
	StandbyPhase,
	ResponseToActivation,
	ResponseToTrap,
	ResponseToSummon,
	ResponseToAttack,
	Any
};

/** A single selectable answer in a pending choice. */
struct FDuelChoiceOption
{
	int32 Id = 0;
	FString Label;
	int32 CardUid = 0;
	int32 CardId = 0;
	EDuelZone Zone = EDuelZone::None;
	int32 ZoneIndex = INDEX_NONE;
	bool bEnabled = true;
	FString DisabledReason;

	bool IsEnabled() const { return bEnabled; }
};

/**
 * A pending rules question.  The legacy engine never creates one unless a
 * caller uses FDuelEngine::RequestChoice; therefore existing HUD code that
 * never checks for choices behaves exactly as before.
 */
struct FDuelChoiceRequest
{
	int32 RequestId = 0;
	EDuelChoiceType Type = EDuelChoiceType::None;
	FString Prompt;
	TArray<FDuelChoiceOption> Options;
	int32 MinSelections = 1;
	int32 MaxSelections = 1;
	int32 SourceCardUid = 0;
	int32 SourceCardId = 0;
	EDuelOwner Side = EDuelOwner::Player;
	EDuelZone TargetZone = EDuelZone::None;
	TArray<int32> DefaultOptionIds;
	bool bCancellable = false;
	FString Context;

	bool IsValid() const { return RequestId > 0 && Options.Num() > 0; }
};

/**
 * One link on the chain stack.  LinkIndex is 1-based and assigned by the
 * engine.  EffectId is owned by A05's effect runtime; 0 means "resolve the
 * card's printed effect through the legacy ResolveSpell/ResolveTrap path".
 */
struct FDuelChainLink
{
	int32 LinkIndex = 0;
	int32 CardUid = 0;
	int32 CardId = 0;
	EDuelOwner Controller = EDuelOwner::Player;
	EDuelSpellSpeed Speed = EDuelSpellSpeed::Speed1;
	int32 EffectId = 0;
	EDuelChainLinkType LinkType = EDuelChainLinkType::Other;
	FString Label;
	TArray<int32> TargetUids;
	bool bNegated = false;
	bool bResolved = false;
	bool bCardEffect = true;
};

/** Card-level activation override.  Empty AllowedWindows means "infer". */
struct FDuelActivationRule
{
	EDuelActivationMode Mode = EDuelActivationMode::Automatic;
	bool bAllowFromHand = true;
	bool bAllowFromSet = true;
	bool bQuickEffect = false;
	bool bCounterTrap = false;
	int32 SpellSpeedOverride = 0;
	TArray<EDuelTimingWindow> AllowedWindows;
};

/** One banned/limited-list row. Limit: 0 banned, 1 limited, 2 semi, 3 free. */
struct FDuelLimitEntry
{
	int32 CardId = 0;
	int32 Limit = 3;
	FString Reason;
};

/**
 * Injected or file-loaded banned/limited ruleset.  The default is intentionally
 * empty until A01 delivers the canonical GBA list.
 */
struct FDuelBannedListRuleset
{
	FString RulesetId = TEXT("default_2006_empty");
	TMap<int32, int32> CardLimits;
	TMap<int32, FString> Reasons;
	int32 MinMain = 40;
	int32 MaxMain = 60;
	int32 MaxExtra = 20;
	int32 MaxCopies = 3;

	static FDuelBannedListRuleset MakeDefault() { return FDuelBannedListRuleset(); }

	int32 GetLimit(int32 CardId) const
	{
		if (const int32* Found = CardLimits.Find(CardId))
		{
			return FMath::Clamp(*Found, 0, 3);
		}
		return 3;
	}

	bool IsBanned(int32 CardId) const { return GetLimit(CardId) == 0; }
	bool IsLimited(int32 CardId) const { return GetLimit(CardId) == 1; }
	bool IsSemiLimited(int32 CardId) const { return GetLimit(CardId) == 2; }
	bool IsRestricted(int32 CardId) const { return GetLimit(CardId) < 3; }

	void SetLimit(int32 CardId, int32 Limit, const FString& Reason = FString())
	{
		CardLimits.Add(CardId, FMath::Clamp(Limit, 0, 3));
		if (!Reason.IsEmpty())
		{
			Reasons.Add(CardId, Reason);
		}
		else
		{
			Reasons.Remove(CardId);
		}
	}

	FString GetReason(int32 CardId) const
	{
		const FString* Found = Reasons.Find(CardId);
		return Found ? *Found : FString();
	}

	int32 NumRestricted() const
	{
		int32 Count = 0;
		for (const TPair<int32, int32>& Pair : CardLimits)
		{
			if (Pair.Value < 3)
			{
				++Count;
			}
		}
		return Count;
	}
};

/** Result of FDuelEngine::ValidateDeck. */
struct FDuelDeckValidationResult
{
	bool bValid = true;
	int32 MainCount = 0;
	int32 ExtraCount = 0;
	TArray<FString> Errors;
	TArray<FString> Warnings;

	void AddError(const FString& Message)
	{
		Errors.Add(Message);
		bValid = false;
	}

	void AddWarning(const FString& Message)
	{
		Warnings.Add(Message);
	}
};

/** A fixed card placed in a scenario setup.  Position/face-down are explicit. */
struct FDuelScenarioCard
{
	int32 CardId = 0;
	EDuelZone Zone = EDuelZone::Hand;
	int32 ZoneIndex = INDEX_NONE;
	bool bFaceDown = false;
	bool bDefense = false;
};

/**
 * Fixed duel setup for puzzles and exams.  A07 owns the data; A04 only loads
 * and enforces it.  Deck order is "index 0 is the top card" so a scripted
 * solution is reproducible.
 */
struct FDuelScenario
{
	FString Id;
	FString Name;
	FString Objective;
	FString Mode = TEXT("puzzle");

	int32 PlayerLp = 8000;
	int32 OpponentLp = 8000;
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

	int32 TurnLimit = 0;
	float TimeLimitSeconds = 0.f;
	bool bPlayerGoesFirst = true;
	bool bDrawOnFirstTurn = false;
	int32 Seed = 0;

	// Practical-exam objective counters (0 = not required).
	int32 RequiredBattleDamage = 0;
	int32 RequiredMonstersDestroyed = 0;
	int32 RequiredFusionSummons = 0;
	int32 RequiredRitualSummons = 0;
	int32 RequiredSpecialSummons = 0;
	int32 RequiredSpellsActivated = 0;
	int32 RequiredTrapsActivated = 0;

	bool HasObjective() const
	{
		return RequiredBattleDamage > 0 || RequiredMonstersDestroyed > 0
			|| RequiredFusionSummons > 0 || RequiredRitualSummons > 0
			|| RequiredSpecialSummons > 0 || RequiredSpellsActivated > 0
			|| RequiredTrapsActivated > 0;
	}
};

/** Ante selection and transfer state.  Inventory changes are A06's job. */
struct FDuelAnteState
{
	bool bEnabled = false;
	bool bPlayerSelected = false;
	bool bOpponentSelected = false;
	int32 PlayerCardId = 0;
	int32 OpponentCardId = 0;
	int32 PlayerCardUid = 0;
	int32 OpponentCardUid = 0;
	bool bTransferred = false;
	bool bPlayerWon = false;
	int32 WinnerCardId = 0;
	int32 LoserCardId = 0;
	FString Note;
};

/** Per-duel result counters consumed by A02 (DP/titles) and A07 (exams). */
struct FDuelResultStats
{
	bool bPlayerWon = false;
	bool bDraw = false;
	FString OpponentId;
	FString Mode = TEXT("free");
	FString EndReason;
	bool bWentSecond = false;
	int32 Turns = 0;
	int32 PlayerLp = 0;
	int32 OpponentLp = 0;
	int32 BattleDamageDealt = 0;
	int32 BattleDamageTaken = 0;
	int32 EffectDamageDealt = 0;
	int32 MonstersDestroyedByBattle = 0;
	int32 MonstersLostByBattle = 0;
	int32 FusionSummons = 0;
	int32 RitualSummons = 0;
	int32 SpecialSummons = 0;
	int32 SpellsActivated = 0;
	int32 TrapsActivated = 0;
	int32 CardsDrawn = 0;
	int32 CardsDiscarded = 0;

	void Reset()
	{
		*this = FDuelResultStats();
	}
};
