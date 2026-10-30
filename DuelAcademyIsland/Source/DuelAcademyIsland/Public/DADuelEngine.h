#pragma once

#include "CoreMinimal.h"
#include "DACardRecords.h"

class UCardDatabaseSubsystem;

enum class EDuelOwner : uint8
{
	Player,
	Opponent
};

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

	/** Debug helper used by the -DADuelResultWin / -DADuelResultLoss screenshots. */
	void DebugFinishDuel(bool bPlayerWins);

private:
	// ---- setup and turn flow ----
	void SetupSide(EDuelOwner Side, const FString& DeckId);
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

	FString PlayerDeckId = TEXT("fire");
	FString OpponentDeckId = TEXT("jaden");
	FString OpponentDisplayName = TEXT("Jaden Yuki");
	FString OpponentCharacterId = TEXT("jaden");
	int32 UidCounter = 0;

	TArray<FDuelLogEntry> LogEntries;
	TArray<FDuelVisualEvent> VisualEvents;
};
