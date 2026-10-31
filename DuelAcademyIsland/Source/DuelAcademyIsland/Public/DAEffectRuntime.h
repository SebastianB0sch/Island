// Duel Academy Island - data-driven card effect runtime (A04).
//
// Consumes the A05 JSON scripts in Content/Data/Effects/scripts.  The legacy
// 137-card handlers remain the fallback; a data script is additive and only
// runs when the runtime is asked to fire the matching trigger.

#pragma once

#include "CoreMinimal.h"
#include "DADuelEngine.h"
#include "Dom/JsonObject.h"

class FJsonObject;

enum class EDEffectTrigger : uint8
{
	None,
	OnDuelStart,
	OnTurnStart,
	OnTurnEnd,
	OnActivate,
	OnNormalSummon,
	OnSpecialSummon,
	OnFlipSummon,
	OnSummon,
	OnFlip,
	OnBattleStart,
	OnAttackDeclared,
	OnAttackTarget,
	OnDamageCalculated,
	OnBattleDestroy,
	OnDestroy,
	OnSentToGraveyard,
	OnRemovedFromField,
	OnDraw,
	OnStandby,
	OnMain,
	OnEnd,
	OnChain,
	OnRitualSummon,
	OnFusionSummon,
	Continuous,
	EquipContinuous,
	FieldContinuous,
	Manual
};

struct FDEffectEvent
{
	EDEffectTrigger Trigger = EDEffectTrigger::None;
	FDuelCard SourceCard;
	FDuelCard EventCard;
	EDuelOwner SourceController = EDuelOwner::Player;
	EDuelOwner EventController = EDuelOwner::Player;
	FString SummonType;
	FString Reason;
	int32 AttackerUid = 0;
	int32 AttackTargetUid = 0;
	int32 ChainLink = 0;
	bool bFromField = false;
	bool bByBattle = false;
	FString CustomContext;
};

struct FDEffectScript
{
	int32 CardId = 0;
	FString Id;
	EDEffectTrigger Trigger = EDEffectTrigger::None;
	TSharedPtr<FJsonObject> Condition;
	TSharedPtr<FJsonObject> Target;
	TArray<TSharedPtr<FJsonObject>> Costs;
	TArray<TSharedPtr<FJsonObject>> Operations;
	FString Duration;
	bool bOptional = false;
	int32 SpellSpeed = 1;
	bool bOncePerTurn = false;
	bool bOncePerDuel = false;
	FString SourceText;

	bool IsValid() const { return CardId > 0 && !Id.IsEmpty() && Operations.Num() > 0; }
};

/**
 * Runtime state and script execution.  The engine owns one instance; A09/A10
 * can inspect it through FDuelEngine::GetEffectRuntime().
 */
class DUELACADEMYISLAND_API FDAEffectRuntime
{
public:
	explicit FDAEffectRuntime(FDuelEngine* InEngine);
	~FDAEffectRuntime();

	bool LoadDefaultScripts(FString& OutError);
	bool LoadScriptsFromDirectory(const FString& Directory, FString& OutError);
	bool LoadScriptJsonText(const FString& JsonText, FString& OutError);
	void ResetForNewDuel();

	int32 GetLoadedCardCount() const { return ScriptsByCard.Num(); }
	int32 GetLoadedScriptCount() const;
	bool HasScript(int32 CardId) const { return ScriptsByCard.Contains(CardId); }
	int32 GetScriptCount(int32 CardId) const;
	FString GetScriptId(int32 CardId, int32 ScriptIndex) const;
	EDEffectTrigger GetScriptTrigger(int32 CardId, int32 ScriptIndex) const;

	// Event bus (called by the engine and by the self-test).
	void OnDuelStart();
	void OnTurnStart(EDuelOwner Side);
	void OnDraw(EDuelOwner Side, const FDuelCard& Card);
	void OnStandby(EDuelOwner Side);
	void OnMain(EDuelOwner Side);
	void OnBattleStart(EDuelOwner Side);
	void OnBattleEnd();
	void OnEnd(EDuelOwner Side);
	void OnSummon(FDuelCard& Card, bool bSpecial, bool bFlipSummon, int32 TributeCount);
	void OnFlip(FDuelCard& Card);
	void OnFusionSummon(FDuelCard& Card);
	void OnRitualSummon(FDuelCard& Card);
	void OnActivate(FDuelCard& Card);
	void OnChain(const FDuelChainLink& Link);
	void OnAttackDeclared(FDuelCard& Attacker, FDuelCard* Target);
	void OnDamageCalculated(FDuelCard& Attacker, FDuelCard* Target);
	void OnDestroyed(const FDuelCard& Card, bool bByBattle, const FString& Reason);
	void OnSentToGraveyard(const FDuelCard& Card, bool bFromField, const FString& Reason);
	void OnCardLeftField(const FDuelCard& Card);
	void RecomputeContinuous();

	/** Generic fire entry for custom triggers and the self-test. */
	int32 FireEvent(const FDEffectEvent& Event);

	/** Execute a manual / ignition script by its position in the card's script list. */
	bool ActivateManualScript(int32 CardUid, int32 ScriptIndex, FString& OutError);
	bool HasManualEffect(const FDuelCard& Card) const;
	TArray<FDuelActionInfo> GetManualActions(const FDuelCard& Card) const;

	// Queries used by the engine.
	int32 GetAtkModifier(int32 Uid) const;
	int32 GetDefModifier(int32 Uid) const;
	int32 GetSpellSpeedOverride(int32 CardId) const;
	bool IsTrapActivationLocked() const { return bTrapActivationLocked; }
	bool IsCardActivationLocked(const FDuelCard& Card) const;
	bool IsTrapEffectNegated() const { return bTrapEffectNegated; }
	bool IsFusionAllowed(const FString& FusionType) const { return AllowedFusionTypes.Contains(FusionType); }
	bool ShouldRedirectBattleDamage(int32 CardUid, EDuelOwner DamageReceiver, EDuelOwner& OutReceiver) const;
	bool ShouldPreventBattleDamage(EDuelOwner Side) const { return PreventBattleDamageSides.Contains(static_cast<uint8>(Side)); }
	bool IsBattleDamageZeroFor(int32 CardUid) const { return BattleDamageZeroUids.Contains(CardUid); }
	int32 GetCounterCount(int32 Uid, const FString& Counter) const;
	bool AddCounter(int32 Uid, const FString& Counter, int32 Amount, int32 Max);
	bool RemoveCounter(int32 Uid, const FString& Counter, int32 Amount);

	int32 GetPromptCount() const { return PromptCount; }
	int32 GetExecutedScriptCount() const { return ExecutedScripts; }
	int32 GetFailedScriptCount() const { return FailedScripts; }
	void ResetTestStats();

private:
	struct FDEffectContext
	{
		FDEffectScript Script;
		FDuelCard SourceCard;
		FDEffectEvent Event;
		EDuelOwner Chooser = EDuelOwner::Player;
		TArray<int32> TargetUids;
		TArray<int32> CostUids;
	};

	struct FDEffectModifier
	{
		int32 Uid = 0;
		int32 Atk = 0;
		int32 Def = 0;
		int32 ExpiryTurn = -1;
		FString SourceId;
		FString Duration;
	};

	FDuelEngine* Engine = nullptr;
	TMap<int32, TArray<FDEffectScript>> ScriptsByCard;
	TMap<int32, TMap<FString, int32>> Counters;
	TArray<FDEffectModifier> LingeringModifiers;
	TMap<int32, int32> ContinuousAtkModifiers;
	TMap<int32, int32> ContinuousDefModifiers;
	TSet<FString> UsedThisTurn;
	TSet<FString> UsedThisDuel;
	TSet<FString> AllowedFusionTypes;
	TSet<int32> RedirectBattleDamageUids;
	TSet<uint8> PreventBattleDamageSides;
	TSet<int32> BattleDamageZeroUids;
	bool bTrapActivationLocked = false;
	bool bTrapEffectNegated = false;
	bool bExecuting = false;
	bool bRecomputing = false;
	int32 PromptCount = 0;
	int32 ExecutedScripts = 0;
	int32 FailedScripts = 0;

	FString ScriptKey(int32 SourceUid, const FDEffectScript& Script) const;
	FString TriggerToString(EDEffectTrigger Trigger) const;
	EDEffectTrigger TriggerFromString(const FString& Value) const;
	FString CardName(const FDuelCard& Card) const;
	FString ZoneStringOf(const FDuelCard& Card) const;
	EDuelOwner Other(EDuelOwner Side) const;

	bool EvaluateCondition(const TSharedPtr<FJsonObject>& Condition, const FDuelCard& Subject,
		const FDuelCard& SourceCard, const FDEffectEvent& Event, bool bContinuousRegistration = false) const;
	bool EvaluateCustomCondition(const FString& Custom, const FDuelCard& Subject,
		const FDuelCard& SourceCard, const FDEffectEvent& Event) const;
	bool IsSourceAvailable(const FDEffectScript& Script, const FDuelCard& Source,
		const FDEffectEvent& Event) const;
	bool IsOncePerTurnBlocked(const FDEffectScript& Script, const FDuelCard& Source) const;
	void MarkUsed(const FDEffectScript& Script, const FDuelCard& Source);

	TArray<FDuelCard> CollectCandidates(const FString& Zone, const FDuelCard& SourceCard,
		const FDEffectEvent& Event) const;
	TArray<FDuelCard> CollectCardsInZone(const FString& Zone, EDuelOwner Side) const;
	TArray<FDuelCard> CollectAllCards() const;
	bool MatchesFilter(const FDuelCard& Candidate, const TSharedPtr<FJsonObject>& Filter,
		const FDuelCard& SourceCard, const FDEffectEvent& Event) const;

	bool ResolveScriptTarget(const FDEffectScript& Script, const FDuelCard& SourceCard,
		const FDEffectEvent& Event, TArray<int32>& OutUids, TArray<int32>& OutCandidateUids,
		bool& bOutNeedsPrompt, EDuelOwner& OutChooser, int32& OutMin, int32& OutMax, FString& OutPrompt) const;
	bool ResolveOperationTargets(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context,
		const FDuelCard& SourceCard, const FDEffectEvent& Event, TArray<int32>& OutUids) const;
	bool ResolveCostTargets(const TSharedPtr<FJsonObject>& Cost, const FDEffectContext& Context,
		TArray<int32>& OutUids) const;

	bool TryStartScript(const FDEffectScript& Script, const FDuelCard& SourceCard, const FDEffectEvent& Event);
	void ContinueAfterOptional(FDEffectContext Context, bool bActivate);
	void ContinueToTargets(FDEffectContext Context);
	void ContinueAfterTargets(FDEffectContext Context, const TArray<int32>& TargetUids);
	bool PayCosts(const FDEffectContext& Context, FString& OutError);
	bool CanPayCost(const TSharedPtr<FJsonObject>& Cost, const FDEffectContext& Context, FString& OutError) const;
	bool ExecuteOperations(const FDEffectContext& Context, FString& OutError);
	bool ExecuteOperation(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context,
		FString& OutError);

	bool ExecuteDraw(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteDiscard(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteSearch(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteMill(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteBanish(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteDestroy(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteSendToGrave(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteSummon(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, bool bSpecial, FString& OutError);
	bool ExecuteSet(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecutePosition(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteStatModifier(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, bool bAtk, FString& OutError);
	bool ExecuteDamageOrHeal(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, bool bHeal, FString& OutError);
	bool ExecuteCounter(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, bool bRemove, FString& OutError);
	bool ExecuteReturn(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteEquip(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteControl(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteFusion(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteRitual(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteReveal(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteShuffle(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);
	bool ExecuteNegate(const TSharedPtr<FJsonObject>& Operation, const FDEffectContext& Context, FString& OutError);

	void ClearCardState(int32 Uid);
	void ExpireLingering(EDuelOwner EndingSide, bool bBattlePhaseOnly);
};
