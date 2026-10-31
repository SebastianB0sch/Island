#pragma once

#include "CoreMinimal.h"
#include "DACardRecords.h"
#include "DADuelRules.h"
#include "Templates/UniquePtr.h"

class UCardDatabaseSubsystem;
class FDAEffectRuntime;

enum class EDuelPhase : uint8
{
	Main1,
	Battle,
	Main2,
	Over
};

enum class EDuelPosition : uint8
{
	Attack,
	Defense
};

enum class EDuelAction : uint8
{
	None,
	NormalSummon,
	TributeSummon,
	SetMonster,
	SpecialSummon,
	ActivateSpell,
	SetSpellTrap,
	FlipSummon,
	ChangePosition,
	ActivateEffect,
	ActivateTrap
};

struct FDuelActionInfo
{
	EDuelAction Action = EDuelAction::None;
	FString Label;
	int32 TributeCount = 0;
};

struct FDuelCard
{
	int32 Uid = 0;
	FCardRecord Data;
	EDuelOwner Owner = EDuelOwner::Player;
	EDuelOwner Controller = EDuelOwner::Player;

	bool bExtra = false;
	bool bFaceUp = true;
	EDuelPosition Position = EDuelPosition::Attack;
	bool bHasAttacked = false;
	int32 AttacksUsed = 0;
	int32 ExtraAttacks = 0;
	int32 SummonedTurn = -1;
	int32 PositionChangedTurn = -1;
	int32 SetTurn = -1;
	int32 EffectUsedTurn = -1;
	bool bSpecialSummoned = false;
	int32 EquippedToUid = 0;
	int32 TiedToUid = 0;
	int32 Counters = 0;

	bool IsValid() const { return Uid > 0; }
	bool IsMonster() const { return Data.CardType.Contains(TEXT("Monster")); }
	bool IsSpell() const { return Data.CardType == TEXT("Spell"); }
	bool IsTrap() const { return Data.CardType == TEXT("Trap"); }
	bool IsFusion() const { return Data.CardType.Contains(TEXT("Fusion")); }
	bool IsRitual() const { return Data.CardType.Contains(TEXT("Ritual")); }
};

struct FDuelSide
{
	EDuelOwner Owner = EDuelOwner::Player;
	FString Name;
	int32 LP = 8000;
	TArray<FDuelCard> Deck;
	TArray<FDuelCard> Hand;
	TArray<FDuelCard> Graveyard;
	TArray<FDuelCard> Banished;
	TArray<FDuelCard> Extra;
	TArray<FDuelCard> Monsters;
	TArray<FDuelCard> Spells;
	FDuelCard Field;
	bool bNormalSummoned = false;
	bool bBattleDamageZeroThisTurn = false;
	bool bSkipDraw = false;
};

struct FDuelLogEntry
{
	int32 Turn = 0;
	EDuelOwner Side = EDuelOwner::Player;
	FString Tone;
	FString Message;
};

/** Structured presentation events. The rules engine resolves synchronously;
 *  the HUD replays these events with card flights, impacts and portraits. */
enum class EDuelVisualEventType : uint8
{
	TurnStart,
	PhaseChange,
	Draw,
	Summon,
	SetCard,
	Spell,
	Trap,
	Attack,
	Damage,
	Heal,
	Destroy,
	Effect,
	Win,
	Discard,
	Banish,
	Search,
	Mill,
	Return,
	Position,
	Fusion,
	Ritual,
	Cost,
	Counter
};

struct FDuelVisualEvent
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
};

struct FDuelAttackTarget
{
	int32 Uid = 0;
	bool bDirect = false;
	FString Label;
};

/**
 * Deterministic, DOM-free rules engine for the first native UE5 duel pass.
 * Mirrors the Three.js reference engine's main rules while keeping the
 * presentation layer out of the simulation.  All mutations are synchronous and
 * validated so the HUD can call the engine directly from click handlers.
 */
class DUELACADEMYISLAND_API FDuelEngine
{
public:
	FDuelEngine(UCardDatabaseSubsystem* InDatabase, int32 InSeed = 20261025);
	~FDuelEngine();

	void Start(const FString& PlayerDeckId, const FString& OpponentDeckId = TEXT("jaden"),
		const FString& OpponentName = TEXT("Jaden Yuki"), const FString& OpponentCharacterId = TEXT("jaden"));

	bool IsStarted() const { return bStarted; }
	bool IsOver() const { return bWinnerSet; }
	bool HasWinner() const { return bWinnerSet; }
	EDuelOwner GetWinner() const { return Winner; }
	FString GetWinnerName() const;
	EDuelOwner GetActiveSide() const { return ActiveSide; }
	EDuelPhase GetPhase() const { return Phase; }
	FString GetPhaseLabel() const;
	int32 GetTurnNumber() const { return TurnNumber; }
	bool IsPlayerTurn() const { return ActiveSide == EDuelOwner::Player && !bWinnerSet; }
	bool IsAwaitingDiscard() const { return bAwaitingDiscard; }
	bool IsAwaitingAi() const { return bAiTurnPending; }
	int32 GetDiscardCount() const;
	FString GetLastAiMessage() const { return LastAiMessage; }

	const FDuelSide& GetSide(EDuelOwner Side) const;
	FDuelSide& GetSideMutable(EDuelOwner Side);
	const TArray<FDuelLogEntry>& GetLog() const { return LogEntries; }
	const TArray<FDuelVisualEvent>& GetVisualEvents() const { return VisualEvents; }
	void ConsumeVisualEvents(TArray<FDuelVisualEvent>& OutEvents);
	const FString& GetPlayerDeckId() const { return PlayerDeckId; }
	const FString& GetOpponentDeckId() const { return OpponentDeckId; }
	const FString& GetOpponentName() const { return OpponentDisplayName; }
	const FString& GetOpponentCharacterId() const { return OpponentCharacterId; }
	FDAEffectRuntime* GetEffectRuntime() const { return EffectRuntime.Get(); }

	FDuelCard* FindCard(int32 Uid);
	const FDuelCard* FindCard(int32 Uid) const;
	FDuelCard* FindMonster(int32 Uid);
	const FDuelCard* FindMonster(int32 Uid) const;
	FDuelCard* FindSpellTrap(int32 Uid);
	const FDuelCard* FindSpellTrap(int32 Uid) const;

	int32 GetAtk(const FDuelCard& Card) const;
	int32 GetDef(const FDuelCard& Card) const;
	int32 GetBattleAtk(const FDuelCard& Card, const FDuelCard* Target) const;
	int32 GetEffectiveLevel(const FDuelCard& Card) const;
	int32 GetTributeCount(const FDuelCard& Card) const;
	bool HasUmi(EDuelOwner Side) const;

	TArray<FDuelActionInfo> GetHandActions(int32 Uid);
	TArray<FDuelActionInfo> GetMonsterActions(int32 Uid);
	TArray<FDuelActionInfo> GetSpellTrapActions(int32 Uid);
	TArray<FDuelAttackTarget> GetAttackTargets(int32 AttackerUid) const;
	bool CanNormalSummon(const FDuelCard& Card, TArray<int32>* OutTributeUids = nullptr);
	int32 GetRequiredTributes(int32 HandUid) const;

	bool NormalSummon(int32 Uid, const TArray<int32>& TributeUids, bool bSet, FString& OutError);
	bool SpecialSummon(int32 Uid, FString& OutError);
	bool ActivateSpell(int32 Uid, FString& OutError);
	bool SetSpellTrap(int32 Uid, FString& OutError);
	bool ActivateSetTrap(int32 Uid, FString& OutError);
	/** Quick-Play support: activate from hand during Main/Battle, or from a Set card. */
	bool ActivateQuickPlayFromHand(int32 Uid, FString& OutError);
	bool ActivateSetSpell(int32 Uid, FString& OutError);
	bool FlipSummon(int32 Uid, FString& OutError);
	bool ChangePosition(int32 Uid, FString& OutError);
	bool ActivateMonsterEffect(int32 Uid, FString& OutError);
	bool Attack(int32 AttackerUid, int32 TargetUid, FString& OutError);
	bool ExecuteAttack(EDuelOwner AttackerSide, int32 AttackerUid, int32 TargetUid, FString& OutError);

	void EnterBattlePhase();
	void EndBattlePhase();
	void EndTurn();
	bool DiscardFromHand(int32 Uid, FString& OutError);
	void RunOpponentTurn();

	int32 GetCardArtId(const FDuelCard& Card) const { return Card.Data.Id; }

	/** Debug/self-test helper: simulate a complete AI-vs-AI duel. */
	static FString RunSelfTest(UCardDatabaseSubsystem* Database, int32 Iterations);

	// -----------------------------------------------------------------------
	// Choices / targeting (additive; no pending choice means legacy auto-play)
	// -----------------------------------------------------------------------

	bool HasPendingChoice() const { return PendingChoices.Num() > 0; }
	bool HasPendingChoiceFor(EDuelOwner Side) const;
	const FDuelChoiceRequest* GetPendingChoice() const;
	const TArray<FDuelChoiceRequest>& GetPendingChoices() const { return PendingChoices; }

	/** Queue a question.  RequestId is assigned when <= 0.  Returns the id. */
	int32 RequestChoice(const FDuelChoiceRequest& Request,
		TFunction<void(const FDuelChoiceRequest&, const TArray<int32>&)> OnResolved = nullptr);
	bool AnswerChoice(int32 RequestId, const TArray<int32>& OptionIds, FString& OutError);
	bool AutoAnswerPendingChoice(FString* OutError = nullptr);
	bool CancelChoice(int32 RequestId, FString& OutError);
	void ClearPendingChoices();

	/** Convenience wrapper for "you may activate this optional effect" prompts. */
	int32 RequestOptionalTrigger(const FDuelCard& SourceCard, const FString& Prompt, bool bDefaultYes,
		TFunction<void(bool)> OnResolved = nullptr);

	/** AI-side choices are answered at RequestChoice time while this is true. */
	void SetAutoAnswerAiChoices(bool bEnable) { bAutoAnswerAiChoices = bEnable; }
	bool GetAutoAnswerAiChoices() const { return bAutoAnswerAiChoices; }
	void SetAutoAnswerAllChoices(bool bEnable) { bAutoAnswerAllChoices = bEnable; }

	// -----------------------------------------------------------------------
	// Chain stack
	// -----------------------------------------------------------------------

	bool IsChainOpen() const { return ChainLinks.Num() > 0; }
	const TArray<FDuelChainLink>& GetChainLinks() const { return ChainLinks; }
	const TArray<FDuelChainLink>& GetLastResolvedChain() const { return LastResolvedChain; }
	const TArray<int32>& GetResolvedChainOrder() const { return ResolvedChainOrder; }
	bool CanAddChainLink(EDuelSpellSpeed Speed, FString* OutReason = nullptr) const;

	/** Start a chain / add a response.  Returns the 1-based link number, 0 on failure. */
	int32 StartChain(const FDuelChainLink& Link, FString& OutError);
	int32 AddChainLink(const FDuelChainLink& Link, FString& OutError);
	bool NegateChainLink(int32 ChainLinkNumber, FString& OutError);
	int32 ResolveChain(FString& OutError);
	void ClearChain();
	EDuelSpellSpeed GetSpellSpeed(const FDuelCard& Card) const;

	/** A05 hook for EffectId != 0 links.  Card effects (EffectId == 0) use the legacy resolver. */
	void SetChainEffectResolver(TFunction<void(const FDuelChainLink&)> InResolver) { ChainEffectResolver = MoveTemp(InResolver); }
	void SetEnforceChainSpellSpeeds(bool bEnable) { bEnforceChainSpellSpeeds = bEnable; }
	bool IsEnforcingChainSpellSpeeds() const { return bEnforceChainSpellSpeeds; }

	// -----------------------------------------------------------------------
	// Activation windows / timing
	// -----------------------------------------------------------------------

	EDuelTimingWindow GetCurrentTimingWindow() const;
	EDuelActivationMode GetActivationMode(const FDuelCard& Card) const;
	bool IsAutomaticActivation(const FDuelCard& Card) const { return GetActivationMode(Card) == EDuelActivationMode::Automatic; }
	FDuelActivationRule GetActivationRule(const FDuelCard& Card) const { return ResolveActivationRule(Card); }
	FDuelActivationRule ResolveActivationRule(const FDuelCard& Card) const;
	bool IsActivationLegal(const FDuelCard& Card, EDuelTimingWindow Window, FString* OutReason = nullptr) const;
	void SetActivationRule(int32 CardId, const FDuelActivationRule& Rule) { ActivationRules.Add(CardId, Rule); }
	void SetActivationMode(const FDuelCard& Card, EDuelActivationMode Mode)
	{
		FDuelActivationRule Rule = ResolveActivationRule(Card);
		Rule.Mode = Mode;
		ActivationRules.Add(Card.Data.Id, Rule);
	}
	void ClearActivationRules() { ActivationRules.Reset(); }
	void SetEnforceActivationTiming(bool bEnable) { bEnforceActivationTiming = bEnable; }
	bool IsEnforcingActivationTiming() const { return bEnforceActivationTiming; }

	/** Compatibility flag: true keeps the shipped automatic Trap behaviour. */
	void SetLegacyAutomaticTraps(bool bEnable) { bLegacyAutomaticTraps = bEnable; }
	bool AreLegacyAutomaticTrapsEnabled() const { return bLegacyAutomaticTraps; }

	/** Activate a Counter Trap as a chain response.  Scaffolding for A05/A09. */
	bool ActivateCounterTrapResponse(int32 TrapUid, int32 TargetChainLinkNumber, FString& OutError);

	// -----------------------------------------------------------------------
	// Deck validation / banned list
	// -----------------------------------------------------------------------

	FDuelDeckValidationResult ValidateDeck(const TArray<int32>& Main, const TArray<int32>& Extra) const;
	const FDuelBannedListRuleset& GetBannedList() const { return BannedList; }
	void SetBannedList(const FDuelBannedListRuleset& InRuleset) { BannedList = InRuleset; }
	bool LoadBannedListFromJson(const FString& JsonText, FString& OutError);
	bool LoadBannedListFromFile(const FString& FilePath, FString& OutError);
	/** Loads Content/Data/Rules/banned_limited.json (A06's provisional file). */
	bool LoadDefaultBannedList(FString& OutError);

	// -----------------------------------------------------------------------
	// Scenario / puzzle / exam setup
	// -----------------------------------------------------------------------

	bool StartScenario(const FDuelScenario& Scenario, FString& OutError);
	bool IsScenarioActive() const { return bScenarioActive; }
	const FDuelScenario& GetActiveScenario() const { return ActiveScenario; }
	int32 GetScenarioPlayerTurnsTaken() const { return ScenarioPlayerTurns; }
	int32 GetScenarioTurnsRemaining() const;
	float GetScenarioElapsedSeconds() const { return ScenarioElapsedSeconds; }
	bool CheckScenarioTimeout(float ElapsedSeconds);
	bool IsScenarioObjectiveComplete() const;
	void Surrender();

	// -----------------------------------------------------------------------
	// Ante
	// -----------------------------------------------------------------------

	void ConfigureAnte(bool bEnabled, int32 InPlayerCardId = 0, int32 InOpponentCardId = 0);
	const FDuelAnteState& GetAnteState() const { return AnteState; }
	bool SelectAnteCard(EDuelOwner Side, int32 CardId, FString& OutError);
	bool FinalizeAnteSelection(FString& OutError);
	void SetAnteResultHook(TFunction<void(const FDuelAnteState&)> InHook) { AnteResultHook = MoveTemp(InHook); }

	// -----------------------------------------------------------------------
	// Result statistics (A02 / A07 contract)
	// -----------------------------------------------------------------------

	const FDuelResultStats& GetResultStats() const { return ResultStats; }
	void ResetResultStats() { ResultStats.Reset(); }
	/** Mark story/exam/ante mode; call after Start/StartScenario. */
	void SetDuelMode(const FString& InMode) { ResultStats.Mode = InMode; }

	/** Debug helper used by the -DADuelResultWin / -DADuelResultLoss screenshots. */
	void DebugFinishDuel(bool bPlayerWins);

private:
	friend class FDAEffectRuntime;

	// ---- shared reset / rules plumbing ----
	void ResetDuelState();
	void ResetTransientRulesState();
	void FinalizeResultStats();
	void ResolveAnteOnDuelEnd();
	bool BuildAutoChoiceAnswer(const FDuelChoiceRequest& Request, TArray<int32>& OutOptionIds) const;
	void InvokeChoiceResolver(int32 RequestId, const FDuelChoiceRequest& Request, const TArray<int32>& OptionIds);
	bool IsChoiceAnswerValid(const FDuelChoiceRequest& Request, const TArray<int32>& OptionIds, FString& OutError) const;
	bool IsAutomaticTrapTimingAllowed(const FDuelCard& Card, EDuelTimingWindow Window) const;
	void ExecuteChainLinkCard(FDuelChainLink& Link);
	void CleanupResolvedChainCard(int32 CardUid);
	bool SetupScenarioSide(EDuelOwner Side, const FDuelScenario& Scenario, FString& OutError);
	void CheckScenarioCompletion();
	bool IsCardInSideDeck(EDuelOwner Side, int32 CardId) const;

	// ---- setup and turn flow ----
	void SetupSide(EDuelOwner Side, const FString& DeckId);
	/** Release-gate helper: structural checks shared by the AI smoke test and scenario probes. */
	bool CheckDuelStateInvariants(int32 ExpectedPlayerCards, int32 ExpectedOpponentCards,
		TArray<FString>& OutErrors) const;
	FDuelCard MakeCard(int32 CardId, EDuelOwner Owner, bool bExtra);
	void ShuffleSide(FDuelSide& Side);
	void StartTurn(EDuelOwner Side);
	void Draw(EDuelOwner Side, int32 Count, bool bSilent = false);
	void FinishPlayerTurn();
	void StartOpponentTurnInternal();
	void EndOpponentTurnInternal();
	void BeginNextTurn();
	void CheckWinner();
	void EndDuel(EDuelOwner WinnerSide, const FString& Reason);

	// ---- state helpers ----
	EDuelOwner Other(EDuelOwner Side) const;
	FDuelSide& SideRef(EDuelOwner Side);
	const FDuelSide& SideRef(EDuelOwner Side) const;
	FString SideName(EDuelOwner Side) const;
	bool IsMainPhase() const;
	bool CanPlayerAct() const;
	bool RemoveFromZone(FDuelCard& OutCard, int32 Uid);
	bool PlaceMonster(EDuelOwner Side, FDuelCard Card, bool bFaceUp, EDuelPosition Position, int32 Zone = -1);
	bool PlaceSpellTrap(EDuelOwner Side, FDuelCard Card, bool bFaceUp, bool bFieldZone = false);
	void MoveToGrave(FDuelCard Card);
	void MoveToHand(FDuelCard Card);
	void MoveToBanished(FDuelCard Card);
	void MoveToDeckBottom(FDuelCard Card);
	void RemoveFromGrave(EDuelOwner Side, int32 Uid);
	void DiscardCard(FDuelCard Card, const FString& Reason = FString());
	void Mill(EDuelOwner Side, int32 Count);
	void BanishTop(EDuelOwner Side, int32 Count);
	int32 EmptyMonsterZone(EDuelOwner Side) const;
	int32 EmptySpellZone(EDuelOwner Side) const;
	int32 CountMonsters(EDuelOwner Side) const;
	int32 CountSpells(EDuelOwner Side) const;
	TArray<FDuelCard*> OwnMonsters(EDuelOwner Side);
	TArray<FDuelCard*> FaceUpMonsters(EDuelOwner Side);
	FDuelCard* ChooseMonster(EDuelOwner Side, TFunctionRef<bool(const FDuelCard&)> Predicate, bool bStrongest = true);
	FDuelCard* FindMonsterByName(EDuelOwner Side, const FString& Name);
	FDuelCard* FindMonsterInHand(EDuelOwner Side, const FString& Name);
	FDuelCard* FindCardInDeck(EDuelOwner Side, const FString& Name);
	FDuelCard* FindMonsterInDeck(EDuelOwner Side, TFunctionRef<bool(const FDuelCard&)> Predicate);
	int32 FindMonsterZone(EDuelOwner Side, int32 Uid) const;
	int32 FindSpellZone(EDuelOwner Side, int32 Uid) const;
	FString CardName(const FDuelCard& Card) const;
	bool IsName(const FDuelCard& Card, const TCHAR* Name) const;
	bool IsHarpieLady(const FDuelCard& Card) const;
	bool IsElementalHero(const FDuelCard& Card) const;
	bool IsDragon(const FDuelCard& Card) const;
	bool IsWarrior(const FDuelCard& Card) const;
	bool CanBeSpecialSummonedByEffect(const FDuelCard& Card) const;

	// ---- stats and continuous effects ----
	int32 EquipAtkBonus(const FDuelCard& Card) const;
	int32 EquipDefBonus(const FDuelCard& Card) const;
	bool HasField(EDuelOwner Side, const TCHAR* Name) const;
	bool IsContinuousTrap(const FString& Name) const;

	// ---- summoning ----
	bool CanSpecialSummon(const FDuelCard& Card);
	FString SpecialSummonLabel(const FDuelCard& Card) const;
	bool PerformSpecialSummon(FDuelCard& Card, EDuelOwner Side);
	void OnSummon(FDuelCard& Card, bool bSpecial, int32 TributeCount = 0, bool bFlipSummon = false);
	void TriggerEndPhaseEffects(EDuelOwner Side);
	void TriggerSummonTraps(FDuelCard& Summoned, bool bNormalSummon);
	void SpecialSummonAttributeFromDeck(EDuelOwner Side, const FString& Attribute, int32 MaxAtk);
	void AddFromDeckToHand(EDuelOwner Side, const FString& Name, int32 Limit = 1);
	void SpecialSummonElementalHero(EDuelOwner Side);
	void SpecialSummonHarpieSisters(EDuelOwner Side);

	// ---- battle ----
	bool CanAttack(const FDuelCard& Card) const;
	void ResolveBattle(FDuelCard& Attacker, FDuelCard* Target);
	void AfterAttack(FDuelCard& Attacker);
	FDuelCard* PickAttackTrap(EDuelOwner Defender, FDuelCard& Attacker, FDuelCard* Target);
	bool ResolveAttackTrap(FDuelCard& Trap, EDuelOwner Defender, FDuelCard& Attacker, FDuelCard*& Target, EDuelOwner AttackerSide);
	FDuelCard* PickSummonTrap(EDuelOwner Defender, FDuelCard& Summoned, bool bNormalSummon);
	void TriggerFlipEffect(FDuelCard& Card, EDuelOwner Side);
	void DestroyMonster(FDuelCard& Card, bool bByBattle, FDuelCard* Attacker, bool bWasFaceDown, const FString& Reason);
	void DestroySpellTrap(FDuelCard& Card, bool bByEffect);
	void DestroyAllMonsters(const FString& Reason);
	void DestroyAllSpellTraps(bool bByEffect);
	void ReturnSpellTrapToHand(FDuelCard& Spell);
	void ReturnAllSpellTrapsToHand();
	void AttachEquip(FDuelCard& Equip, FDuelCard& Target);
	void CleanupEquips(FDuelCard& Card);
	void ReturnControl(FDuelCard& Card);
	void InflictDamage(EDuelOwner Side, int32 Amount, const FString& Reason);
	void InflictBattleDamage(EDuelOwner Side, int32 Amount, const FString& Reason);
	void GainLp(EDuelOwner Side, int32 Amount, const FString& Reason);
	void PayLp(EDuelOwner Side, int32 Amount, const FString& Reason);

	// ---- spells, traps, effects ----
	bool CanActivateSpellCard(const FDuelCard& Card);
	void ResolveSpell(FDuelCard& Card);
	bool ActivateTrapInternal(FDuelCard& Trap, EDuelOwner Side, bool bAutomatic);
	void ResolveTrap(FDuelCard& Trap);
	bool TryCounterSpell(EDuelOwner Caster, EDuelOwner Defender);
	bool TryCounterTrap(EDuelOwner Caster, EDuelOwner Defender);
	bool ActivateRitual();
	bool PerformFusion(const FString& FusionType);
	bool FindFusionOption(EDuelOwner Side, const FString& FusionType, int32* OutResult, TArray<int32>* OutMaterialUids) const;
	bool HasEquipTarget(EDuelOwner Side, const FString& Name) const;
	FDuelCard* ChooseEquipTarget(EDuelOwner Side, const FString& Name);
	TArray<FDuelActionInfo> GetMonsterEffectActionsFor(const FDuelCard& Card);
	bool CanActivateMonsterEffect(const FDuelCard& Card);
	bool IsNormalSummonLocked(const FDuelCard& Card) const;

	// ---- AI ----
	void AiPlayMainPhase();
	void AiPlayBattlePhase();
	void AiNormalSummon();
	void AiSetTraps();
	void AiActivateSpells();
	void AiActivateSpellCard(FDuelCard& Card);
	void AiActivateMonsterEffects();
	void AiActivateManualTraps();
	void AiDiscardToLimit();
	bool AiAttackWith(FDuelCard& Attacker);
	int32 AiCardValue(const FDuelCard& Card) const;

	void OnSpellActivated();
	FDuelVisualEvent& EmitVisual(EDuelVisualEventType Type, EDuelOwner Side, const FDuelCard* Card = nullptr,
		int32 Amount = 0, const FString& Text = FString(), bool bFaceDown = false);
	void Log(const FString& Message, const FString& Tone = TEXT("normal"));
	FString Verb(EDuelOwner Side, const TCHAR* ThirdPerson, const TCHAR* SecondPerson) const;

	UCardDatabaseSubsystem* Database = nullptr;
	FRandomStream Random;
	int32 Seed = 0;

	FDuelSide Player;
	FDuelSide Opponent;
	EDuelOwner ActiveSide = EDuelOwner::Player;
	EDuelPhase Phase = EDuelPhase::Main1;
	int32 TurnNumber = 0;
	bool bStarted = false;
	bool bWinnerSet = false;
	EDuelOwner Winner = EDuelOwner::Player;
	bool bAwaitingDiscard = false;
	bool bAiTurnPending = false;
	bool bAiRunning = false;
	FString LastAiMessage;

	// ---- rules architecture (additive, A04) ----
	TArray<FDuelChoiceRequest> PendingChoices;
	TMap<int32, TFunction<void(const FDuelChoiceRequest&, const TArray<int32>&)>> ChoiceResolvers;
	int32 NextChoiceRequestId = 1;
	bool bAutoAnswerAiChoices = true;
	bool bAutoAnswerAllChoices = false;

	TArray<FDuelChainLink> ChainLinks;
	TArray<FDuelChainLink> LastResolvedChain;
	TArray<int32> ResolvedChainOrder;
	TFunction<void(const FDuelChainLink&)> ChainEffectResolver;
	bool bEnforceChainSpellSpeeds = true;

	TMap<int32, FDuelActivationRule> ActivationRules;
	bool bEnforceActivationTiming = false;
	bool bLegacyAutomaticTraps = true;

	FDuelBannedListRuleset BannedList;

	bool bScenarioActive = false;
	FDuelScenario ActiveScenario;
	int32 ScenarioPlayerTurns = 0;
	float ScenarioElapsedSeconds = 0.f;
	bool bScenarioObjectiveComplete = false;

	FDuelAnteState AnteState;
	TFunction<void(const FDuelAnteState&)> AnteResultHook;

	FDuelResultStats ResultStats;
	bool bApplyingBattleDamage = false;

	/** Data-script runtime; owns the loaded Content/Data/Effects scripts. */
	TUniquePtr<FDAEffectRuntime> EffectRuntime;

	FString PlayerDeckId = TEXT("fire");
	FString OpponentDeckId = TEXT("jaden");
	FString OpponentDisplayName = TEXT("Jaden Yuki");
	FString OpponentCharacterId = TEXT("jaden");
	int32 UidCounter = 0;

	TArray<FDuelLogEntry> LogEntries;
	TArray<FDuelVisualEvent> VisualEvents;
};
