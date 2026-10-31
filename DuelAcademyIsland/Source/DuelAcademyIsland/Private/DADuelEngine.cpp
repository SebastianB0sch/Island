#include "DADuelEngine.h"

#include "DAEffectRuntime.h"
#include "DuelAcademyIsland.h"
#include "DACardRecords.h"

#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Engine/World.h"
#include "Engine/GameInstance.h"
#include "Math/RandomStream.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	constexpr int32 StartingLP = 8000;
	constexpr int32 HandLimit = 6;

	const TSet<FString>& NormalSummonLockedNames()
	{
		static const TSet<FString> Names = {
			TEXT("Winged Kuriboh LV10"),
			TEXT("Ocean Dragon Lord - Neo-Daedalus"),
			TEXT("Spirit of Flames"),
			TEXT("Inferno"),
			TEXT("Aqua Spirit"),
			TEXT("Fenrir"),
			TEXT("Garuda the Wind Spirit"),
			TEXT("Silpheed"),
			TEXT("Harpie Lady Sisters"),
			TEXT("F.G.D."),
		};
		return Names;
	}

	bool IsFieldSpellName(const FString& Name)
	{
		return Name == TEXT("Umi")
			|| Name == TEXT("A Legendary Ocean")
			|| Name == TEXT("Umiiruka")
			|| Name == TEXT("Rising Air Current")
			|| Name == TEXT("Harpies' Hunting Ground")
			|| Name == TEXT("Skyscraper");
	}

	bool IsEquipName(const FString& Name)
	{
		return Name == TEXT("Black Pendant")
			|| Name == TEXT("Burning Spear")
			|| Name == TEXT("Salamandra")
			|| Name == TEXT("Gust Fan")
			|| Name == TEXT("Steel Shell")
			|| Name == TEXT("Power of Kaishin")
			|| Name == TEXT("Cyber Shield")
			|| Name == TEXT("United We Stand")
			|| Name == TEXT("Mage Power")
			|| Name == TEXT("Fusion Weapon")
			|| Name == TEXT("Snatch Steal")
			|| Name == TEXT("Premature Burial")
			|| Name == TEXT("Autonomous Action Unit");
	}

	bool IsContinuousTrapName(const FString& Name)
	{
		return Name == TEXT("Call of the Haunted") || Name == TEXT("Backfire");
	}

	bool IsManualTrapName(const FString& Name)
	{
		return Name == TEXT("Call of the Haunted")
			|| Name == TEXT("Backfire")
			|| Name == TEXT("Spiritual Fire Art - Kurenai")
			|| Name == TEXT("Spiritual Water Art - Aoi")
			|| Name == TEXT("Spiritual Wind Art - Miyabi");
	}

}

FDuelEngine::FDuelEngine(UCardDatabaseSubsystem* InDatabase, int32 InSeed)
	: Database(InDatabase)
	, Random(InSeed)
	, Seed(InSeed)
{
	Player.Owner = EDuelOwner::Player;
	Player.Name = TEXT("You");
	Opponent.Owner = EDuelOwner::Opponent;
	Opponent.Name = TEXT("Jaden Yuki");

	EffectRuntime = MakeUnique<FDAEffectRuntime>(this);
	FString EffectError;
	if (!EffectRuntime->LoadDefaultScripts(EffectError))
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Effect runtime could not load default scripts: %s"), *EffectError);
	}
}

FDuelEngine::~FDuelEngine() = default;

// ---------------------------------------------------------------------------
// Rules state reset
// ---------------------------------------------------------------------------

void FDuelEngine::ResetTransientRulesState()
{
	PendingChoices.Reset();
	ChoiceResolvers.Reset();
	NextChoiceRequestId = 1;

	ChainLinks.Reset();
	LastResolvedChain.Reset();
	ResolvedChainOrder.Reset();
	ChainEffectResolver.Reset();

	ResultStats.Reset();
	bScenarioObjectiveComplete = false;
}

void FDuelEngine::ResetDuelState()
{
	Player = FDuelSide();
	Player.Owner = EDuelOwner::Player;
	Player.Name = TEXT("You");
	Player.LP = StartingLP;
	Player.Monsters.SetNum(5);
	Player.Spells.SetNum(5);

	Opponent = FDuelSide();
	Opponent.Owner = EDuelOwner::Opponent;
	Opponent.Name = OpponentDisplayName;
	Opponent.LP = StartingLP;
	Opponent.Monsters.SetNum(5);
	Opponent.Spells.SetNum(5);

	ActiveSide = EDuelOwner::Player;
	Phase = EDuelPhase::Main1;
	TurnNumber = 0;
	bStarted = false;
	bWinnerSet = false;
	Winner = EDuelOwner::Player;
	bAwaitingDiscard = false;
	bAiTurnPending = false;
	bAiRunning = false;
	LastAiMessage.Reset();
	UidCounter = 0;

	LogEntries.Reset();
	VisualEvents.Reset();
	ResetTransientRulesState();
	bApplyingBattleDamage = false;

	bScenarioActive = false;
	ActiveScenario = FDuelScenario();
	ScenarioPlayerTurns = 0;
	ScenarioElapsedSeconds = 0.f;

	AnteState.bTransferred = false;
	AnteState.bPlayerWon = false;
	AnteState.WinnerCardId = 0;
	AnteState.LoserCardId = 0;
	AnteState.PlayerCardUid = 0;
	AnteState.OpponentCardUid = 0;
	AnteState.Note.Reset();
	if (EffectRuntime)
	{
		EffectRuntime->ResetForNewDuel();
	}
}

// ---------------------------------------------------------------------------
// Setup and turn flow
// ---------------------------------------------------------------------------

FDuelCard FDuelEngine::MakeCard(int32 CardId, EDuelOwner Owner, bool bExtra)
{
	FDuelCard Card;
	Card.Uid = ++UidCounter;
	Card.Owner = Owner;
	Card.Controller = Owner;
	Card.bExtra = bExtra;
	if (Database)
	{
		if (const FCardRecord* Record = Database->FindCard(CardId))
		{
			Card.Data = *Record;
		}
	}
	if (Card.Data.Id == 0)
	{
		Card.Data.Id = CardId;
		Card.Data.Name = FString::Printf(TEXT("Unknown Card %d"), CardId);
	}
	return Card;
}

void FDuelEngine::SetupSide(EDuelOwner Side, const FString& DeckId)
{
	FDuelSide& State = SideRef(Side);
	State = FDuelSide();
	State.Owner = Side;
	State.Name = Side == EDuelOwner::Player ? TEXT("You") : OpponentDisplayName;
	State.LP = StartingLP;
	State.Monsters.SetNum(5);
	State.Spells.SetNum(5);

	if (!Database)
	{
		Log(TEXT("Card database is not available."), TEXT("error"));
		return;
	}

	const FStarterDeckDef* Deck = Database->FindDeck(DeckId);
	if (!Deck)
	{
		Log(FString::Printf(TEXT("Deck '%s' was not found."), *DeckId), TEXT("error"));
		return;
	}

	for (int32 CardId : Deck->Cards)
	{
		State.Deck.Add(MakeCard(CardId, Side, false));
	}
	for (int32 CardId : Deck->Extra)
	{
		State.Extra.Add(MakeCard(CardId, Side, true));
	}
	State.Extra.Sort([](const FDuelCard& A, const FDuelCard& B)
	{
		return A.Data.Atk > B.Data.Atk;
	});
}

void FDuelEngine::ShuffleSide(FDuelSide& Side)
{
	for (int32 I = Side.Deck.Num() - 1; I > 0; --I)
	{
		const int32 J = Random.RandRange(0, I);
		Side.Deck.Swap(I, J);
	}
}

void FDuelEngine::Start(const FString& InPlayerDeckId, const FString& InOpponentDeckId,
	const FString& InOpponentName, const FString& InOpponentCharacterId)
{
	if (bStarted)
	{
		return;
	}
	ResetDuelState();
	bStarted = true;
	PlayerDeckId = InPlayerDeckId.IsEmpty() ? TEXT("fire") : InPlayerDeckId;
	OpponentDeckId = InOpponentDeckId.IsEmpty() ? TEXT("jaden") : InOpponentDeckId;
	OpponentDisplayName = InOpponentName.IsEmpty() ? TEXT("Jaden Yuki") : InOpponentName;
	OpponentCharacterId = InOpponentCharacterId.IsEmpty() ? TEXT("jaden") : InOpponentCharacterId;
	Opponent.Name = OpponentDisplayName;

	Log(TEXT("Duel start. Both duelists draw five cards."), TEXT("turn"));
	SetupSide(EDuelOwner::Player, PlayerDeckId);
	SetupSide(EDuelOwner::Opponent, OpponentDeckId);

	// Resolve any ante selections made before the decks were built.
	if (AnteState.bEnabled)
	{
		auto FindAnteUid = [this](EDuelOwner Side, int32 CardId) -> int32
		{
			if (CardId <= 0) return 0;
			for (const FDuelCard& Card : SideRef(Side).Deck)
			{
				if (Card.Data.Id == CardId) return Card.Uid;
			}
			return 0;
		};
		AnteState.PlayerCardUid = FindAnteUid(EDuelOwner::Player, AnteState.PlayerCardId);
		AnteState.OpponentCardUid = FindAnteUid(EDuelOwner::Opponent, AnteState.OpponentCardId);
	}

	if (Player.Deck.Num() == 0 || Opponent.Deck.Num() == 0)
	{
		EndDuel(EDuelOwner::Opponent, TEXT("A deck could not be loaded."));
		return;
	}

	ShuffleSide(Player);
	ShuffleSide(Opponent);
	Draw(EDuelOwner::Player, 5, true);
	Draw(EDuelOwner::Opponent, 5, true);
	if (EffectRuntime && !bWinnerSet)
	{
		EffectRuntime->OnDuelStart();
	}
	StartTurn(EDuelOwner::Player);
}

void FDuelEngine::StartTurn(EDuelOwner Side)
{
	if (bWinnerSet)
	{
		return;
	}

	ActiveSide = Side;
	++TurnNumber;
	Phase = EDuelPhase::Main1;

	// Puzzle/exam turn limits count player turns only, which is how the GBA
	// timed duels describe their limit.
	if (bScenarioActive && Side == EDuelOwner::Player)
	{
		++ScenarioPlayerTurns;
		if (ActiveScenario.TurnLimit > 0 && ScenarioPlayerTurns > ActiveScenario.TurnLimit)
		{
			EndDuel(EDuelOwner::Opponent, TEXT("The turn limit was reached."));
			return;
		}
	}
	if (EffectRuntime)
	{
		EffectRuntime->OnTurnStart(Side);
	}
	// Turn-scoped flags expire when the next turn begins, even if the card that
	// created them belonged to the side that just finished.
	Player.bBattleDamageZeroThisTurn = false;
	Opponent.bBattleDamageZeroThisTurn = false;
	SideRef(Side).bNormalSummoned = false;

	for (FDuelCard& Monster : SideRef(Side).Monsters)
	{
		if (Monster.IsValid())
		{
			Monster.bHasAttacked = false;
			Monster.AttacksUsed = 0;
			Monster.ExtraAttacks = 0;
			Monster.EffectUsedTurn = -1;
		}
	}

	Log(FString::Printf(TEXT("%s %s turn %d."),
		*SideRef(Side).Name,
		Side == EDuelOwner::Player ? TEXT("begin") : TEXT("begins"),
		TurnNumber), TEXT("turn"));
	EmitVisual(EDuelVisualEventType::TurnStart, Side, nullptr, TurnNumber, SideRef(Side).Name);

	if (SideRef(Side).bSkipDraw)
	{
		SideRef(Side).bSkipDraw = false;
		Log(FString::Printf(TEXT("%s %s the Draw Phase."),
			*SideRef(Side).Name,
			Side == EDuelOwner::Player ? TEXT("skip") : TEXT("skips")), TEXT("effect"));
	}
	else
	{
		Draw(Side, 1);
		if (bWinnerSet)
		{
			return;
		}
	}

	// Standby Phase triggers.
	FDuelSide& State = SideRef(Side);
	for (const FDuelCard& Monster : State.Monsters)
	{
		if (!Monster.IsValid() || !Monster.bFaceUp)
		{
			continue;
		}
		if (IsName(Monster, TEXT("Spirit of the Breeze")) && Monster.Position == EDuelPosition::Attack)
		{
			GainLp(Side, 1000, TEXT("Spirit of the Breeze"));
		}
		else if (IsName(Monster, TEXT("Dancing Fairy")) && Monster.Position == EDuelPosition::Defense)
		{
			GainLp(Side, 1000, TEXT("Dancing Fairy"));
		}
	}

	// Sinister Serpent returns itself from the Graveyard during any Standby
	// Phase; it does not need to be face-up on the field.
	for (int32 I = 0; I < State.Graveyard.Num(); ++I)
	{
		if (IsName(State.Graveyard[I], TEXT("Sinister Serpent")))
		{
			FDuelCard Serpent = State.Graveyard[I];
			State.Graveyard.RemoveAt(I);
			State.Hand.Add(Serpent);
			Log(FString::Printf(TEXT("%s returns Sinister Serpent from the Graveyard to the hand."), *State.Name), TEXT("effect"));
			break;
		}
	}

	// Snatch Steal gives the stolen monster's owner 1000 LP in their Standby Phase.
	for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		for (FDuelCard& Spell : SideRef(Owner).Spells)
		{
			if (Spell.IsValid() && Spell.bFaceUp && IsName(Spell, TEXT("Snatch Steal")))
			{
				const FDuelCard* Target = FindMonster(Spell.EquippedToUid);
				if (Target && Target->Owner == Side)
				{
					GainLp(Side, 1000, TEXT("Snatch Steal"));
				}
			}
		}
	}

	// Aqua Spirit changes one opponent monster during that opponent's Standby.
	for (EDuelOwner ControllerSide : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		if (ControllerSide == Side)
		{
			continue;
		}
		FDuelCard* Aqua = FindMonsterByName(ControllerSide, TEXT("Aqua Spirit"));
		if (Aqua && Aqua->bFaceUp)
		{
			FDuelCard* Target = ChooseMonster(Side, [](const FDuelCard& Card)
			{
				return Card.bFaceUp && Card.Position == EDuelPosition::Attack;
			}, true);
			if (!Target)
			{
				Target = ChooseMonster(Side, [](const FDuelCard& Card) { return Card.bFaceUp; }, true);
			}
			if (Target)
			{
				Target->Position = Target->Position == EDuelPosition::Attack ? EDuelPosition::Defense : EDuelPosition::Attack;
				Target->PositionChangedTurn = TurnNumber;
				Log(FString::Printf(TEXT("Aqua Spirit changes %s to %s Position."), *CardName(*Target),
					Target->Position == EDuelPosition::Attack ? TEXT("Attack") : TEXT("Defense")), TEXT("effect"));
				EmitVisual(EDuelVisualEventType::Position, ControllerSide, Target, 0,
					Target->Position == EDuelPosition::Attack ? TEXT("ATTACK") : TEXT("DEFENSE"));
			}
		}
	}

	if (EffectRuntime)
	{
		EffectRuntime->OnStandby(Side);
	}

	Phase = EDuelPhase::Main1;
	if (EffectRuntime)
	{
		EffectRuntime->OnMain(Side);
		EffectRuntime->RecomputeContinuous();
	}
}

void FDuelEngine::Draw(EDuelOwner Side, int32 Count, bool bSilent)
{
	FDuelSide& State = SideRef(Side);
	for (int32 I = 0; I < Count; ++I)
	{
		if (State.Deck.Num() == 0)
		{
			EndDuel(Other(Side), FString::Printf(TEXT("%s cannot draw."), *State.Name));
			return;
		}
		FDuelCard Card = State.Deck.Pop();
		State.Hand.Add(Card);
		if (Side == EDuelOwner::Player)
		{
			++ResultStats.CardsDrawn;
		}
		if (!bSilent)
		{
			Log(FString::Printf(TEXT("%s %s %s."),
				*State.Name,
				Side == EDuelOwner::Player ? TEXT("draw") : TEXT("draws"),
				*CardName(Card)), TEXT("draw"));
		}
		EmitVisual(EDuelVisualEventType::Draw, Side, &Card, 0, CardName(Card), Side == EDuelOwner::Opponent);
		if (!bSilent && EffectRuntime)
		{
			EffectRuntime->OnDraw(Side, Card);
		}
	}
}

void FDuelEngine::EndTurn()
{
	if (bWinnerSet || !IsPlayerTurn() || bAwaitingDiscard || HasPendingChoice())
	{
		return;
	}
	if (!IsMainPhase() && Phase != EDuelPhase::Battle)
	{
		return;
	}
	if (Player.Hand.Num() > HandLimit)
	{
		bAwaitingDiscard = true;
		Log(FString::Printf(TEXT("Discard %d card(s) to the 6-card hand limit."), Player.Hand.Num() - HandLimit), TEXT("phase"));
		return;
	}
	FinishPlayerTurn();
}

void FDuelEngine::FinishPlayerTurn()
{
	if (bWinnerSet)
	{
		return;
	}
	Phase = EDuelPhase::Main2;
	TriggerEndPhaseEffects(EDuelOwner::Player);
	if (EffectRuntime)
	{
		EffectRuntime->OnEnd(EDuelOwner::Player);
	}
	Log(TEXT("Your turn ends."), TEXT("phase"));
	EmitVisual(EDuelVisualEventType::PhaseChange, EDuelOwner::Player, nullptr, 0, TEXT("END PHASE"));
	bAiTurnPending = true;
	LastAiMessage = FString::Printf(TEXT("%s is taking their turn."), *OpponentDisplayName);
}

bool FDuelEngine::DiscardFromHand(int32 Uid, FString& OutError)
{
	if (!bAwaitingDiscard)
	{
		OutError = TEXT("No discard is pending.");
		return false;
	}
	for (int32 I = 0; I < Player.Hand.Num(); ++I)
	{
		if (Player.Hand[I].Uid == Uid)
		{
			FDuelCard Card = Player.Hand[I];
			Player.Hand.RemoveAt(I);
			DiscardCard(Card, TEXT("hand limit"));
			Log(FString::Printf(TEXT("You discard %s to the 6-card hand limit."), *CardName(Card)), TEXT("phase"));
			if (Player.Hand.Num() <= HandLimit)
			{
				bAwaitingDiscard = false;
				TriggerEndPhaseEffects(EDuelOwner::Player);
				if (EffectRuntime)
				{
					EffectRuntime->OnEnd(EDuelOwner::Player);
				}
				bAiTurnPending = true;
				LastAiMessage = FString::Printf(TEXT("%s is taking their turn."), *OpponentDisplayName);
				Log(TEXT("Your turn ends."), TEXT("phase"));
			}
			return true;
		}
	}
	OutError = TEXT("That card is not in your hand.");
	return false;
}

int32 FDuelEngine::GetDiscardCount() const
{
	return bAwaitingDiscard ? FMath::Max(0, Player.Hand.Num() - HandLimit) : 0;
}

void FDuelEngine::RunOpponentTurn()
{
	if (!bAiTurnPending || bWinnerSet || bAiRunning)
	{
		return;
	}
	bAiTurnPending = false;
	bAiRunning = true;
	const bool bTurnAlreadyStarted = ActiveSide == EDuelOwner::Opponent
		&& Phase == EDuelPhase::Main1 && TurnNumber > 0;
	if (!bTurnAlreadyStarted)
	{
		StartTurn(EDuelOwner::Opponent);
	}
	if (!bWinnerSet)
	{
		AiPlayMainPhase();
	}
	if (!bWinnerSet)
	{
		Phase = EDuelPhase::Battle;
		Log(FString::Printf(TEXT("%s enters the Battle Phase."), *OpponentDisplayName), TEXT("phase"));
		EmitVisual(EDuelVisualEventType::PhaseChange, EDuelOwner::Opponent, nullptr, 0, TEXT("BATTLE PHASE"));
		if (EffectRuntime)
		{
			EffectRuntime->OnBattleStart(EDuelOwner::Opponent);
		}
		AiPlayBattlePhase();
	}
	if (!bWinnerSet)
	{
		AiDiscardToLimit();
		EmitVisual(EDuelVisualEventType::PhaseChange, EDuelOwner::Opponent, nullptr, 0, TEXT("END PHASE"));
		TriggerEndPhaseEffects(EDuelOwner::Opponent);
		if (EffectRuntime)
		{
			EffectRuntime->OnEnd(EDuelOwner::Opponent);
		}
		Log(FString::Printf(TEXT("%s ends their turn."), *OpponentDisplayName), TEXT("phase"));
		StartTurn(EDuelOwner::Player);
	}
	while (!bWinnerSet && HasPendingChoiceFor(EDuelOwner::Opponent))
	{
		const FDuelChoiceRequest* HeadChoice = GetPendingChoice();
		if (!HeadChoice || HeadChoice->Side != EDuelOwner::Opponent)
		{
			break;
		}
		FString ChoiceError;
		if (!AutoAnswerPendingChoice(&ChoiceError))
		{
			break;
		}
	}
	bAiRunning = false;
	if (!bWinnerSet)
	{
		LastAiMessage = TEXT("Your turn.");
	}
}

void FDuelEngine::BeginNextTurn()
{
	StartTurn(Other(ActiveSide));
}

void FDuelEngine::EndDuel(EDuelOwner WinnerSide, const FString& Reason)
{
	if (bWinnerSet)
	{
		return;
	}
	bWinnerSet = true;
	Winner = WinnerSide;
	Phase = EDuelPhase::Over;
	Log(FString::Printf(TEXT("%s %s! %s"), *SideRef(WinnerSide).Name,
		WinnerSide == EDuelOwner::Player ? TEXT("win") : TEXT("wins"), *Reason), TEXT("win"));
	EmitVisual(EDuelVisualEventType::Win, WinnerSide, nullptr, 0, Reason);
	LastAiMessage = FString::Printf(TEXT("%s %s."), *SideRef(WinnerSide).Name,
		WinnerSide == EDuelOwner::Player ? TEXT("win") : TEXT("wins"));
	ResultStats.EndReason = Reason;
	FinalizeResultStats();
	ResolveAnteOnDuelEnd();
	ClearPendingChoices();
}

void FDuelEngine::CheckWinner()
{
	if (bWinnerSet)
	{
		return;
	}
	if (bScenarioActive)
	{
		CheckScenarioCompletion();
		if (bWinnerSet)
		{
			return;
		}
	}
	if (Player.LP <= 0 && Opponent.LP <= 0)
	{
		EndDuel(EDuelOwner::Opponent, TEXT("Both duelists reached 0 Life Points."));
	}
	else if (Player.LP <= 0)
	{
		EndDuel(EDuelOwner::Opponent, TEXT("Your Life Points reached 0."));
	}
	else if (Opponent.LP <= 0)
	{
		EndDuel(EDuelOwner::Player, FString::Printf(TEXT("%s's Life Points reached 0."), *OpponentDisplayName));
	}
}

// ---------------------------------------------------------------------------
// State helpers
// ---------------------------------------------------------------------------

const FDuelSide& FDuelEngine::GetSide(EDuelOwner Side) const
{
	return Side == EDuelOwner::Player ? Player : Opponent;
}

FDuelSide& FDuelEngine::GetSideMutable(EDuelOwner Side)
{
	return SideRef(Side);
}

FDuelSide& FDuelEngine::SideRef(EDuelOwner Side)
{
	return Side == EDuelOwner::Player ? Player : Opponent;
}

const FDuelSide& FDuelEngine::SideRef(EDuelOwner Side) const
{
	return Side == EDuelOwner::Player ? Player : Opponent;
}

EDuelOwner FDuelEngine::Other(EDuelOwner Side) const
{
	return Side == EDuelOwner::Player ? EDuelOwner::Opponent : EDuelOwner::Player;
}

FString FDuelEngine::SideName(EDuelOwner Side) const
{
	return Side == EDuelOwner::Player ? TEXT("You") : OpponentDisplayName;
}

FString FDuelEngine::Verb(EDuelOwner Side, const TCHAR* ThirdPerson, const TCHAR* SecondPerson) const
{
	return Side == EDuelOwner::Player ? SecondPerson : ThirdPerson;
}

bool FDuelEngine::IsMainPhase() const
{
	return Phase == EDuelPhase::Main1 || Phase == EDuelPhase::Main2;
}

bool FDuelEngine::CanPlayerAct() const
{
	return !bWinnerSet && ActiveSide == EDuelOwner::Player && !bAwaitingDiscard && !bAiTurnPending
		&& !HasPendingChoice();
}

FString FDuelEngine::GetWinnerName() const
{
	return bWinnerSet ? SideRef(Winner).Name : FString();
}

FString FDuelEngine::GetPhaseLabel() const
{
	switch (Phase)
	{
	case EDuelPhase::Main1: return TEXT("MAIN PHASE 1");
	case EDuelPhase::Battle: return TEXT("BATTLE PHASE");
	case EDuelPhase::Main2: return TEXT("MAIN PHASE 2");
	case EDuelPhase::Over: return TEXT("DUEL OVER");
	default: return FString();
	}
}

bool FDuelEngine::RemoveFromZone(FDuelCard& OutCard, int32 Uid)
{
	if (Uid <= 0)
	{
		return false;
	}

	auto RemoveFromArray = [Uid, &OutCard](TArray<FDuelCard>& Array) -> bool
	{
		for (int32 I = 0; I < Array.Num(); ++I)
		{
			if (Array[I].Uid == Uid)
			{
				OutCard = Array[I];
				Array.RemoveAt(I);
				return true;
			}
		}
		return false;
	};

	auto RemoveFromSlots = [Uid, &OutCard](TArray<FDuelCard>& Slots) -> bool
	{
		for (FDuelCard& Slot : Slots)
		{
			if (Slot.Uid == Uid)
			{
				OutCard = Slot;
				Slot = FDuelCard();
				return true;
			}
		}
		return false;
	};

	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		FDuelSide& State = SideRef(Side);
		if (RemoveFromSlots(State.Monsters)) return true;
		if (RemoveFromSlots(State.Spells)) return true;
		if (State.Field.Uid == Uid)
		{
			OutCard = State.Field;
			State.Field = FDuelCard();
			return true;
		}
		if (RemoveFromArray(State.Hand)) return true;
		if (RemoveFromArray(State.Deck)) return true;
		if (RemoveFromArray(State.Graveyard)) return true;
		if (RemoveFromArray(State.Banished)) return true;
		if (RemoveFromArray(State.Extra)) return true;
	}
	return false;
}

bool FDuelEngine::PlaceMonster(EDuelOwner Side, FDuelCard Card, bool bFaceUp, EDuelPosition Position, int32 Zone)
{
	FDuelSide& State = SideRef(Side);
	int32 Index = Zone;
	if (Index < 0 || Index >= State.Monsters.Num() || State.Monsters[Index].IsValid())
	{
		Index = EmptyMonsterZone(Side);
	}
	if (Index == INDEX_NONE)
	{
		return false;
	}
	Card.Controller = Side;
	Card.bFaceUp = bFaceUp;
	Card.Position = Position;
	Card.SummonedTurn = TurnNumber;
	Card.SetTurn = bFaceUp ? -1 : TurnNumber;
	Card.bHasAttacked = false;
	Card.AttacksUsed = 0;
	State.Monsters[Index] = Card;
	if (EffectRuntime)
	{
		EffectRuntime->RecomputeContinuous();
	}
	return true;
}

bool FDuelEngine::PlaceSpellTrap(EDuelOwner Side, FDuelCard Card, bool bFaceUp, bool bFieldZone)
{
	FDuelSide& State = SideRef(Side);
	Card.Controller = Side;
	Card.bFaceUp = bFaceUp;
	Card.Position = EDuelPosition::Attack;
	Card.SetTurn = bFaceUp ? -1 : TurnNumber;

	if (bFieldZone)
	{
		// Only one Field Spell can be active. Replacing it sends the old card to
		// the Graveyard regardless of which side played it.
		for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
		{
			FDuelSide& OwnerSide = SideRef(Owner);
			if (OwnerSide.Field.IsValid())
			{
				FDuelCard OldField = OwnerSide.Field;
				OwnerSide.Field = FDuelCard();
				MoveToGrave(OldField);
			}
		}
		State.Field = Card;
		if (EffectRuntime)
		{
			EffectRuntime->RecomputeContinuous();
		}
		return true;
	}

	const int32 Index = EmptySpellZone(Side);
	if (Index == INDEX_NONE)
	{
		return false;
	}
	State.Spells[Index] = Card;
	if (EffectRuntime)
	{
		EffectRuntime->RecomputeContinuous();
	}
	return true;
}

void FDuelEngine::MoveToGrave(FDuelCard Card)
{
	Card.Controller = Card.Owner;
	Card.bFaceUp = true;
	Card.Position = EDuelPosition::Attack;
	Card.EquippedToUid = 0;
	Card.TiedToUid = 0;
	Card.Counters = 0;
	SideRef(Card.Owner).Graveyard.Add(Card);
	if (EffectRuntime)
	{
		EffectRuntime->RecomputeContinuous();
	}
}

void FDuelEngine::MoveToHand(FDuelCard Card)
{
	if (EffectRuntime)
	{
		EffectRuntime->OnCardLeftField(Card);
	}
	Card.Controller = Card.Owner;
	Card.bFaceUp = true;
	Card.Position = EDuelPosition::Attack;
	Card.EquippedToUid = 0;
	Card.TiedToUid = 0;
	Card.Counters = 0;
	Card.bSpecialSummoned = false;
	EmitVisual(EDuelVisualEventType::Return, Card.Owner, &Card, 0, CardName(Card));
	SideRef(Card.Owner).Hand.Add(Card);
}

void FDuelEngine::MoveToBanished(FDuelCard Card)
{
	if (EffectRuntime)
	{
		EffectRuntime->OnCardLeftField(Card);
	}
	Card.Controller = Card.Owner;
	Card.bFaceUp = true;
	Card.Position = EDuelPosition::Attack;
	Card.EquippedToUid = 0;
	Card.TiedToUid = 0;
	Card.Counters = 0;
	EmitVisual(EDuelVisualEventType::Banish, Card.Owner, &Card, 0, CardName(Card));
	SideRef(Card.Owner).Banished.Add(Card);
}

void FDuelEngine::MoveToDeckBottom(FDuelCard Card)
{
	if (EffectRuntime)
	{
		EffectRuntime->OnCardLeftField(Card);
	}
	Card.Controller = Card.Owner;
	Card.bFaceUp = false;
	Card.Position = EDuelPosition::Attack;
	Card.EquippedToUid = 0;
	Card.TiedToUid = 0;
	Card.Counters = 0;
	if (Card.bExtra || Card.IsFusion())
	{
		// Fusion/Extra Deck monsters never enter the Main Deck.
		Card.bExtra = true;
		EmitVisual(EDuelVisualEventType::Return, Card.Owner, &Card, 0, TEXT("EXTRA DECK"));
		SideRef(Card.Owner).Extra.Add(Card);
		return;
	}
	EmitVisual(EDuelVisualEventType::Return, Card.Owner, &Card, 0, TEXT("DECK BOTTOM"));
	SideRef(Card.Owner).Deck.Insert(Card, 0);
}

void FDuelEngine::MoveToDeckTop(FDuelCard Card)
{
	if (EffectRuntime)
	{
		EffectRuntime->OnCardLeftField(Card);
	}
	Card.Controller = Card.Owner;
	Card.bFaceUp = false;
	Card.Position = EDuelPosition::Attack;
	Card.EquippedToUid = 0;
	Card.TiedToUid = 0;
	Card.Counters = 0;
	if (Card.bExtra || Card.IsFusion())
	{
		Card.bExtra = true;
		EmitVisual(EDuelVisualEventType::Return, Card.Owner, &Card, 0, TEXT("EXTRA DECK"));
		SideRef(Card.Owner).Extra.Add(Card);
		return;
	}
	EmitVisual(EDuelVisualEventType::Return, Card.Owner, &Card, 0, TEXT("DECK TOP"));
	// Draw() uses Pop(), so the last array element is the top of the Deck.
	SideRef(Card.Owner).Deck.Add(Card);
}

void FDuelEngine::RemoveFromGrave(EDuelOwner Side, int32 Uid)
{
	FDuelSide& State = SideRef(Side);
	for (int32 I = 0; I < State.Graveyard.Num(); ++I)
	{
		if (State.Graveyard[I].Uid == Uid)
		{
			State.Graveyard.RemoveAt(I);
			return;
		}
	}
}

void FDuelEngine::DiscardCard(FDuelCard Card, const FString& Reason)
{
	if (Card.Owner == EDuelOwner::Player)
	{
		++ResultStats.CardsDiscarded;
	}
	FDuelCard* Found = FindCard(Card.Uid);
	FDuelCard Discarded = Found ? *Found : Card;
	EmitVisual(EDuelVisualEventType::Discard, Discarded.Owner, &Discarded, 0,
		Reason.IsEmpty() ? CardName(Discarded) : Reason);
	if (Found)
	{
		FDuelCard Copy;
		if (RemoveFromZone(Copy, Card.Uid))
		{
			MoveToGrave(Copy);
		}
	}
	else
	{
		MoveToGrave(Card);
	}
	if (EffectRuntime)
	{
		EffectRuntime->OnSentToGraveyard(Card, false, Reason.IsEmpty() ? TEXT("discard") : Reason);
	}
	if (!Reason.IsEmpty())
	{
		Log(FString::Printf(TEXT("%s is discarded (%s)."), *CardName(Card), *Reason), TEXT("discard"));
	}
}

void FDuelEngine::Mill(EDuelOwner Side, int32 Count)
{
	FDuelSide& State = SideRef(Side);
	for (int32 I = 0; I < Count && State.Deck.Num() > 0; ++I)
	{
		FDuelCard Card = State.Deck.Pop();
		EmitVisual(EDuelVisualEventType::Mill, Side, &Card, 0, CardName(Card));
		MoveToGrave(Card);
		if (EffectRuntime)
		{
			EffectRuntime->OnSentToGraveyard(Card, false, TEXT("mill"));
		}
	}
}

void FDuelEngine::BanishTop(EDuelOwner Side, int32 Count)
{
	FDuelSide& State = SideRef(Side);
	for (int32 I = 0; I < Count && State.Deck.Num() > 0; ++I)
	{
		MoveToBanished(State.Deck.Pop());
	}
}

int32 FDuelEngine::EmptyMonsterZone(EDuelOwner Side) const
{
	const FDuelSide& State = SideRef(Side);
	for (int32 I = 0; I < State.Monsters.Num(); ++I)
	{
		if (!State.Monsters[I].IsValid())
		{
			return I;
		}
	}
	return INDEX_NONE;
}

int32 FDuelEngine::EmptySpellZone(EDuelOwner Side) const
{
	const FDuelSide& State = SideRef(Side);
	for (int32 I = 0; I < State.Spells.Num(); ++I)
	{
		if (!State.Spells[I].IsValid())
		{
			return I;
		}
	}
	return INDEX_NONE;
}

int32 FDuelEngine::CountMonsters(EDuelOwner Side) const
{
	int32 Count = 0;
	for (const FDuelCard& Card : SideRef(Side).Monsters)
	{
		if (Card.IsValid())
		{
			++Count;
		}
	}
	return Count;
}

int32 FDuelEngine::CountSpells(EDuelOwner Side) const
{
	int32 Count = 0;
	for (const FDuelCard& Card : SideRef(Side).Spells)
	{
		if (Card.IsValid())
		{
			++Count;
		}
	}
	if (SideRef(Side).Field.IsValid())
	{
		++Count;
	}
	return Count;
}

TArray<FDuelCard*> FDuelEngine::OwnMonsters(EDuelOwner Side)
{
	TArray<FDuelCard*> Result;
	for (FDuelCard& Card : SideRef(Side).Monsters)
	{
		if (Card.IsValid())
		{
			Result.Add(&Card);
		}
	}
	return Result;
}

TArray<FDuelCard*> FDuelEngine::FaceUpMonsters(EDuelOwner Side)
{
	TArray<FDuelCard*> Result;
	for (FDuelCard& Card : SideRef(Side).Monsters)
	{
		if (Card.IsValid() && Card.bFaceUp)
		{
			Result.Add(&Card);
		}
	}
	return Result;
}

FDuelCard* FDuelEngine::ChooseMonster(EDuelOwner Side, TFunctionRef<bool(const FDuelCard&)> Predicate, bool bStrongest)
{
	FDuelCard* Best = nullptr;
	int32 BestAtk = bStrongest ? TNumericLimits<int32>::Lowest() : TNumericLimits<int32>::Max();
	for (FDuelCard& Card : SideRef(Side).Monsters)
	{
		if (!Card.IsValid() || !Predicate(Card))
		{
			continue;
		}
		const int32 Value = GetAtk(Card);
		if ((bStrongest && Value > BestAtk) || (!bStrongest && Value < BestAtk))
		{
			Best = &Card;
			BestAtk = Value;
		}
	}
	return Best;
}

FDuelCard* FDuelEngine::FindCard(int32 Uid)
{
	if (Uid <= 0)
	{
		return nullptr;
	}
	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		FDuelSide& State = SideRef(Side);
		for (FDuelCard& Card : State.Monsters) if (Card.Uid == Uid) return &Card;
		for (FDuelCard& Card : State.Spells) if (Card.Uid == Uid) return &Card;
		if (State.Field.Uid == Uid) return &State.Field;
		for (FDuelCard& Card : State.Hand) if (Card.Uid == Uid) return &Card;
		for (FDuelCard& Card : State.Deck) if (Card.Uid == Uid) return &Card;
		for (FDuelCard& Card : State.Graveyard) if (Card.Uid == Uid) return &Card;
		for (FDuelCard& Card : State.Banished) if (Card.Uid == Uid) return &Card;
		for (FDuelCard& Card : State.Extra) if (Card.Uid == Uid) return &Card;
	}
	return nullptr;
}

const FDuelCard* FDuelEngine::FindCard(int32 Uid) const
{
	return const_cast<FDuelEngine*>(this)->FindCard(Uid);
}

FDuelCard* FDuelEngine::FindMonster(int32 Uid)
{
	if (Uid <= 0)
	{
		return nullptr;
	}
	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		for (FDuelCard& Card : SideRef(Side).Monsters)
		{
			if (Card.Uid == Uid)
			{
				return &Card;
			}
		}
	}
	return nullptr;
}

const FDuelCard* FDuelEngine::FindMonster(int32 Uid) const
{
	return const_cast<FDuelEngine*>(this)->FindMonster(Uid);
}

int32 FDuelEngine::FindMonsterZone(EDuelOwner Side, int32 Uid) const
{
	if (Uid <= 0)
	{
		return INDEX_NONE;
	}
	const FDuelSide& State = SideRef(Side);
	for (int32 I = 0; I < State.Monsters.Num(); ++I)
	{
		if (State.Monsters[I].IsValid() && State.Monsters[I].Uid == Uid)
		{
			return I;
		}
	}
	return INDEX_NONE;
}

int32 FDuelEngine::FindSpellZone(EDuelOwner Side, int32 Uid) const
{
	if (Uid <= 0)
	{
		return INDEX_NONE;
	}
	const FDuelSide& State = SideRef(Side);
	for (int32 I = 0; I < State.Spells.Num(); ++I)
	{
		if (State.Spells[I].IsValid() && State.Spells[I].Uid == Uid)
		{
			return I;
		}
	}
	return INDEX_NONE;
}

FDuelCard* FDuelEngine::FindSpellTrap(int32 Uid)
{
	if (Uid <= 0)
	{
		return nullptr;
	}
	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		FDuelSide& State = SideRef(Side);
		for (FDuelCard& Card : State.Spells)
		{
			if (Card.Uid == Uid)
			{
				return &Card;
			}
		}
		if (State.Field.Uid == Uid)
		{
			return &State.Field;
		}
	}
	return nullptr;
}

const FDuelCard* FDuelEngine::FindSpellTrap(int32 Uid) const
{
	return const_cast<FDuelEngine*>(this)->FindSpellTrap(Uid);
}

FDuelCard* FDuelEngine::FindMonsterByName(EDuelOwner Side, const FString& Name)
{
	for (FDuelCard& Card : SideRef(Side).Monsters)
	{
		if (Card.IsValid() && Card.Data.Name == Name)
		{
			return &Card;
		}
	}
	return nullptr;
}

FDuelCard* FDuelEngine::FindMonsterInHand(EDuelOwner Side, const FString& Name)
{
	for (FDuelCard& Card : SideRef(Side).Hand)
	{
		if (Card.IsMonster() && Card.Data.Name == Name)
		{
			return &Card;
		}
	}
	return nullptr;
}

FDuelCard* FDuelEngine::FindCardInDeck(EDuelOwner Side, const FString& Name)
{
	for (FDuelCard& Card : SideRef(Side).Deck)
	{
		if (Card.Data.Name == Name)
		{
			return &Card;
		}
	}
	return nullptr;
}

FDuelCard* FDuelEngine::FindMonsterInDeck(EDuelOwner Side, TFunctionRef<bool(const FDuelCard&)> Predicate)
{
	for (FDuelCard& Card : SideRef(Side).Deck)
	{
		if (Card.IsMonster() && Predicate(Card))
		{
			return &Card;
		}
	}
	return nullptr;
}

FString FDuelEngine::CardName(const FDuelCard& Card) const
{
	return Card.Data.Name;
}

bool FDuelEngine::IsName(const FDuelCard& Card, const TCHAR* Name) const
{
	return Card.Data.Name.Equals(Name, ESearchCase::IgnoreCase);
}

bool FDuelEngine::IsHarpieLady(const FDuelCard& Card) const
{
	return IsName(Card, TEXT("Harpie Lady")) || IsName(Card, TEXT("Cyber Harpie Lady"));
}

bool FDuelEngine::IsElementalHero(const FDuelCard& Card) const
{
	return Card.Data.Name.Contains(TEXT("Elemental Hero"));
}

bool FDuelEngine::IsDragon(const FDuelCard& Card) const
{
	return Card.Data.MonsterType.Equals(TEXT("Dragon"), ESearchCase::IgnoreCase);
}

bool FDuelEngine::IsWarrior(const FDuelCard& Card) const
{
	return Card.Data.MonsterType.Equals(TEXT("Warrior"), ESearchCase::IgnoreCase);
}

bool FDuelEngine::CanBeSpecialSummonedByEffect(const FDuelCard& Card) const
{
	if (EffectRuntime && EffectRuntime->IsSummonLocked(Card.Controller, true))
	{
		return false;
	}
	// These cards name the exact Summon that may bring them out and cannot be
	// revived or cheated onto the field by generic effects such as Premature
	// Burial, Call of the Haunted or A Hero Emerges. Their dedicated summon
	// paths call PlaceMonster/OnSummon directly.
	return !Card.IsRitual() && !NormalSummonLockedNames().Contains(Card.Data.Name);
}

FDuelVisualEvent& FDuelEngine::EmitVisual(EDuelVisualEventType Type, EDuelOwner Side, const FDuelCard* Card,
	int32 Amount, const FString& Text, bool bFaceDown)
{
	FDuelVisualEvent Event;
	Event.Type = Type;
	Event.Side = Side;
	Event.Amount = Amount;
	Event.Text = Text;
	Event.bFaceDown = bFaceDown;
	if (Card)
	{
		Event.CardUid = Card->Uid;
		Event.CardId = Card->Data.Id;
	}
	VisualEvents.Add(Event);
	if (VisualEvents.Num() > 180)
	{
		VisualEvents.RemoveAt(0, VisualEvents.Num() - 180);
	}
	return VisualEvents.Last();
}

void FDuelEngine::ConsumeVisualEvents(TArray<FDuelVisualEvent>& OutEvents)
{
	OutEvents.Append(VisualEvents);
	VisualEvents.Reset();
}

void FDuelEngine::OnSpellActivated()
{
	for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		for (FDuelCard& Monster : SideRef(Owner).Monsters)
		{
			if (Monster.IsValid() && Monster.bFaceUp && IsName(Monster, TEXT("Legendary Flame Lord")))
			{
				++Monster.Counters;
				Log(FString::Printf(TEXT("Legendary Flame Lord gains a Spell Counter (%d)."), Monster.Counters), TEXT("effect"));
				EmitVisual(EDuelVisualEventType::Counter, Owner, &Monster, Monster.Counters, TEXT("SPELL COUNTER"));
			}
		}
	}
}

void FDuelEngine::Log(const FString& Message, const FString& Tone)
{
	FDuelLogEntry Entry;
	Entry.Turn = TurnNumber;
	Entry.Side = ActiveSide;
	Entry.Tone = Tone;
	Entry.Message = Message;
	LogEntries.Add(Entry);
	if (LogEntries.Num() > 160)
	{
		LogEntries.RemoveAt(0, LogEntries.Num() - 160);
	}
	if (bAiRunning)
	{
		LastAiMessage = Message;
	}
}

// ---------------------------------------------------------------------------
// Stats and continuous effects
// ---------------------------------------------------------------------------

bool FDuelEngine::HasField(EDuelOwner Side, const TCHAR* Name) const
{
	const FDuelSide& State = SideRef(Side);
	return State.Field.IsValid() && State.Field.bFaceUp && State.Field.Data.Name.Equals(Name, ESearchCase::IgnoreCase);
}

bool FDuelEngine::HasUmi(EDuelOwner Side) const
{
	bool bAnyField = false;
	for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		const FDuelSide& State = SideRef(Owner);
		if (State.Field.IsValid() && State.Field.bFaceUp)
		{
			bAnyField = true;
			if (State.Field.Data.Name == TEXT("Umi") || State.Field.Data.Name == TEXT("A Legendary Ocean"))
			{
				return true;
			}
		}
	}
	if (bAnyField)
	{
		return false;
	}
	// Maiden of the Aqua treats the field as Umi while no Field Spell is active.
	for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		for (const FDuelCard& Card : SideRef(Owner).Monsters)
		{
			if (Card.IsValid() && Card.bFaceUp && IsName(Card, TEXT("Maiden of the Aqua")))
			{
				return true;
			}
		}
	}
	return false;
}

int32 FDuelEngine::EquipAtkBonus(const FDuelCard& Card) const
{
	int32 Bonus = 0;
	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		const FDuelSide& State = SideRef(Side);
		for (const FDuelCard& Spell : State.Spells)
		{
			if (!Spell.IsValid() || !Spell.bFaceUp || Spell.EquippedToUid != Card.Uid)
			{
				continue;
			}
			if (EffectRuntime && EffectRuntime->HasEquipStatScript(Spell.Data.Id))
			{
				continue;
			}
			if (IsName(Spell, TEXT("Black Pendant"))) Bonus += 500;
			else if (IsName(Spell, TEXT("Burning Spear")) && Card.Data.Attribute == TEXT("FIRE")) Bonus += 400;
			else if (IsName(Spell, TEXT("Salamandra")) && Card.Data.Attribute == TEXT("FIRE")) Bonus += 700;
			else if (IsName(Spell, TEXT("Gust Fan")) && Card.Data.Attribute == TEXT("WIND")) Bonus += 400;
			else if (IsName(Spell, TEXT("Steel Shell")) && Card.Data.Attribute == TEXT("WATER")) Bonus += 400;
			else if (IsName(Spell, TEXT("Power of Kaishin")) && Card.Data.MonsterType == TEXT("Aqua")) Bonus += 300;
			else if (IsName(Spell, TEXT("Cyber Shield")) && (IsHarpieLady(Card) || IsName(Card, TEXT("Harpie Lady Sisters")))) Bonus += 500;
			else if (IsName(Spell, TEXT("United We Stand")))
			{
				int32 Count = 0;
				for (const FDuelCard& Own : SideRef(Spell.Controller).Monsters)
				{
					if (Own.IsValid() && Own.bFaceUp) ++Count;
				}
				Bonus += Count * 800;
			}
			else if (IsName(Spell, TEXT("Mage Power")))
			{
				Bonus += CountSpells(Spell.Controller) * 500;
			}
			else if (IsName(Spell, TEXT("Fusion Weapon")) && Card.IsFusion() && Card.Data.Level <= 6) Bonus += 1500;
		}
	}
	return Bonus;
}

int32 FDuelEngine::EquipDefBonus(const FDuelCard& Card) const
{
	int32 Bonus = 0;
	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		const FDuelSide& State = SideRef(Side);
		for (const FDuelCard& Spell : State.Spells)
		{
			if (!Spell.IsValid() || !Spell.bFaceUp || Spell.EquippedToUid != Card.Uid)
			{
				continue;
			}
			if (EffectRuntime && EffectRuntime->HasEquipStatScript(Spell.Data.Id))
			{
				continue;
			}
			if (IsName(Spell, TEXT("Burning Spear")) && Card.Data.Attribute == TEXT("FIRE")) Bonus -= 200;
			else if (IsName(Spell, TEXT("Gust Fan")) && Card.Data.Attribute == TEXT("WIND")) Bonus -= 200;
			else if (IsName(Spell, TEXT("Steel Shell")) && Card.Data.Attribute == TEXT("WATER")) Bonus -= 200;
			else if (IsName(Spell, TEXT("Power of Kaishin")) && Card.Data.MonsterType == TEXT("Aqua")) Bonus += 300;
			else if (IsName(Spell, TEXT("United We Stand")))
			{
				int32 Count = 0;
				for (const FDuelCard& Own : SideRef(Spell.Controller).Monsters)
				{
					if (Own.IsValid() && Own.bFaceUp) ++Count;
				}
				Bonus += Count * 800;
			}
			else if (IsName(Spell, TEXT("Mage Power")))
			{
				Bonus += CountSpells(Spell.Controller) * 500;
			}
			else if (IsName(Spell, TEXT("Fusion Weapon")) && Card.IsFusion() && Card.Data.Level <= 6) Bonus += 1500;
		}
	}
	return Bonus;
}

int32 FDuelEngine::GetAtk(const FDuelCard& Card) const
{
	if (!Card.IsMonster())
	{
		return 0;
	}

	int32 Value = Card.Data.Atk + EquipAtkBonus(Card);

	// The active Field Spell affects every monster on the field.
	const FDuelCard* Field = nullptr;
	if (Player.Field.IsValid() && Player.Field.bFaceUp) Field = &Player.Field;
	else if (Opponent.Field.IsValid() && Opponent.Field.bFaceUp) Field = &Opponent.Field;
	if (Field)
	{
		const FString& FieldName = Field->Data.Name;
		const FString& Attribute = Card.Data.Attribute;
		const FString& Type = Card.Data.MonsterType;
		const bool bLegacyFieldStats = !EffectRuntime || !EffectRuntime->HasFieldStatScript(Field->Data.Id);
		if (bLegacyFieldStats && FieldName == TEXT("Umi"))
		{
			if (Type == TEXT("Fish") || Type == TEXT("Sea Serpent") || Type == TEXT("Thunder") || Type == TEXT("Aqua")) Value += 200;
			if (Type == TEXT("Machine") || Type == TEXT("Pyro")) Value -= 200;
		}
		else if (bLegacyFieldStats && FieldName == TEXT("A Legendary Ocean") && Attribute == TEXT("WATER")) Value += 200;
		else if (bLegacyFieldStats && FieldName == TEXT("Umiiruka") && Attribute == TEXT("WATER")) Value += 500;
		else if (bLegacyFieldStats && FieldName == TEXT("Rising Air Current") && Attribute == TEXT("WIND")) Value += 500;
		else if (bLegacyFieldStats && FieldName == TEXT("Harpies' Hunting Ground") && Type == TEXT("Winged Beast")) Value += 200;
	}

	// Continuous monster effects are global while their source is face-up.
	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		for (const FDuelCard& Source : SideRef(Side).Monsters)
		{
			if (!Source.IsValid() || !Source.bFaceUp) continue;
			if (IsName(Source, TEXT("Star Boy")))
			{
				if (Card.Data.Attribute == TEXT("WATER")) Value += 500;
				else if (Card.Data.Attribute == TEXT("FIRE")) Value -= 400;
			}
			else if (IsName(Source, TEXT("Bladefly")))
			{
				if (Card.Data.Attribute == TEXT("WIND")) Value += 500;
				else if (Card.Data.Attribute == TEXT("EARTH")) Value -= 400;
			}
			else if (IsName(Source, TEXT("Little Chimera")))
			{
				if (Card.Data.Attribute == TEXT("FIRE")) Value += 500;
				else if (Card.Data.Attribute == TEXT("WATER")) Value -= 400;
			}
			else if (IsName(Source, TEXT("Harpie's Pet Dragon")) && Source.Uid == Card.Uid)
			{
				int32 Harpies = 0;
				for (EDuelOwner HarpieSide : { EDuelOwner::Player, EDuelOwner::Opponent })
				{
					for (const FDuelCard& Harpie : SideRef(HarpieSide).Monsters)
					{
						if (Harpie.IsValid() && Harpie.bFaceUp && IsHarpieLady(Harpie)) ++Harpies;
					}
				}
				Value += Harpies * 300;
			}
			else if (IsName(Source, TEXT("Ultimate Baseball Kid")) && Source.Uid == Card.Uid)
			{
				int32 Fires = 0;
				for (EDuelOwner FireSide : { EDuelOwner::Player, EDuelOwner::Opponent })
				{
					for (const FDuelCard& OtherMonster : SideRef(FireSide).Monsters)
					{
						if (OtherMonster.IsValid() && OtherMonster.bFaceUp && OtherMonster.Uid != Source.Uid
							&& OtherMonster.Data.Attribute == TEXT("FIRE"))
						{
							++Fires;
						}
					}
				}
				Value += Fires * 1000;
			}
		}
	}

	if (IsName(Card, TEXT("Spirit of Flames")) && Phase == EDuelPhase::Battle && Card.Controller == ActiveSide)
	{
		Value += 300;
	}
	if (IsName(Card, TEXT("Elemental Hero Shining Flare Wingman")))
	{
		for (const FDuelCard& GraveCard : SideRef(Card.Controller).Graveyard)
		{
			if (GraveCard.Data.Name.Contains(TEXT("Elemental Hero"))) Value += 300;
		}
	}
	if (EffectRuntime)
	{
		Value += EffectRuntime->GetAtkModifier(Card.Uid);
	}
	return FMath::Max(0, Value);
}

int32 FDuelEngine::GetDef(const FDuelCard& Card) const
{
	if (!Card.IsMonster())
	{
		return 0;
	}

	int32 Value = Card.Data.Def + EquipDefBonus(Card);

	const FDuelCard* Field = nullptr;
	if (Player.Field.IsValid() && Player.Field.bFaceUp) Field = &Player.Field;
	else if (Opponent.Field.IsValid() && Opponent.Field.bFaceUp) Field = &Opponent.Field;
	if (Field)
	{
		const FString& FieldName = Field->Data.Name;
		const FString& Attribute = Card.Data.Attribute;
		const FString& Type = Card.Data.MonsterType;
		const bool bLegacyFieldStats = !EffectRuntime || !EffectRuntime->HasFieldStatScript(Field->Data.Id);
		if (bLegacyFieldStats && FieldName == TEXT("Umi"))
		{
			if (Type == TEXT("Fish") || Type == TEXT("Sea Serpent") || Type == TEXT("Thunder") || Type == TEXT("Aqua")) Value += 200;
			if (Type == TEXT("Machine") || Type == TEXT("Pyro")) Value -= 200;
		}
		else if (bLegacyFieldStats && FieldName == TEXT("A Legendary Ocean") && Attribute == TEXT("WATER")) Value += 200;
		else if (bLegacyFieldStats && FieldName == TEXT("Umiiruka") && Attribute == TEXT("WATER")) Value -= 400;
		else if (bLegacyFieldStats && FieldName == TEXT("Rising Air Current") && Attribute == TEXT("WIND")) Value -= 400;
		else if (bLegacyFieldStats && FieldName == TEXT("Harpies' Hunting Ground") && Type == TEXT("Winged Beast")) Value += 200;
	}

	if (IsName(Card, TEXT("Harpie's Pet Dragon")))
	{
		int32 Harpies = 0;
		for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
		{
			for (const FDuelCard& Harpie : SideRef(Side).Monsters)
			{
				if (Harpie.IsValid() && Harpie.bFaceUp && IsHarpieLady(Harpie)) ++Harpies;
			}
		}
		Value += Harpies * 300;
	}
	if (EffectRuntime)
	{
		Value += EffectRuntime->GetDefModifier(Card.Uid);
	}
	return FMath::Max(0, Value);
}

int32 FDuelEngine::GetBattleAtk(const FDuelCard& Card, const FDuelCard* Target) const
{
	int32 Value = GetAtk(Card);
	if (Card.bFaceUp && IsElementalHero(Card) && Target && Target->bFaceUp)
	{
		const FDuelCard* Field = Player.Field.IsValid() ? &Player.Field : (Opponent.Field.IsValid() ? &Opponent.Field : nullptr);
		if (Field && Field->bFaceUp && Field->Data.Name == TEXT("Skyscraper"))
		{
			const int32 TargetAtk = GetAtk(*Target);
			if (Value < TargetAtk)
			{
				Value += 1000;
			}
		}
	}
	return Value;
}

int32 FDuelEngine::GetEffectiveLevel(const FDuelCard& Card) const
{
	int32 Level = Card.Data.Level;
	const FDuelCard* Field = Player.Field.IsValid() ? &Player.Field : (Opponent.Field.IsValid() ? &Opponent.Field : nullptr);
	if (Field && Field->bFaceUp && Field->Data.Name == TEXT("A Legendary Ocean") && Card.Data.Attribute == TEXT("WATER"))
	{
		Level = FMath::Max(1, Level - 1);
	}
	return Level;
}

int32 FDuelEngine::GetTributeCount(const FDuelCard& Card) const
{
	const int32 Level = GetEffectiveLevel(Card);
	if (Level >= 7) return 2;
	if (Level >= 5) return 1;
	return 0;
}

bool FDuelEngine::IsNormalSummonLocked(const FDuelCard& Card) const
{
	if (Card.IsFusion() || Card.IsRitual() || NormalSummonLockedNames().Contains(Card.Data.Name))
	{
		return true;
	}
	// Cave Dragon cannot be Normal Summoned while its controller already has a
	// monster on the field. The AI check uses the active side, so evaluate both
	// virtual hands safely: a card in hand is owned by the side being tested.
	if (IsName(Card, TEXT("Cave Dragon")) && CountMonsters(Card.Owner) > 0)
	{
		return true;
	}
	return false;
}

// ---------------------------------------------------------------------------
// Derived actions for the HUD
// ---------------------------------------------------------------------------

TArray<FDuelActionInfo> FDuelEngine::GetHandActions(int32 Uid)
{
	TArray<FDuelActionInfo> Actions;
	if (!CanPlayerAct() || !IsMainPhase())
	{
		return Actions;
	}

	const FDuelCard* Card = nullptr;
	for (const FDuelCard& HandCard : Player.Hand)
	{
		if (HandCard.Uid == Uid)
		{
			Card = &HandCard;
			break;
		}
	}
	if (!Card)
	{
		return Actions;
	}

	if (Card->IsMonster())
	{
		if (!IsNormalSummonLocked(*Card) && !Player.bNormalSummoned)
		{
			const int32 Required = GetTributeCount(*Card);
			const int32 Available = CountMonsters(EDuelOwner::Player);
			const int32 Empty = EmptyMonsterZone(EDuelOwner::Player);
			const bool bCanPlace = Empty != INDEX_NONE || (Required > 0 && Available >= Required);
			if (bCanPlace && Available >= Required)
			{
				FDuelActionInfo Summon;
				Summon.Action = Required > 0 ? EDuelAction::TributeSummon : EDuelAction::NormalSummon;
				Summon.Label = Required > 0
					? FString::Printf(TEXT("Tribute Summon (%d)"), Required)
					: TEXT("Normal Summon");
				Summon.TributeCount = Required;
				Actions.Add(Summon);

				FDuelActionInfo Set;
				Set.Action = EDuelAction::SetMonster;
				Set.Label = Required > 0
					? FString::Printf(TEXT("Set Monster (%d tribute)"), Required)
					: TEXT("Set Monster");
				Set.TributeCount = Required;
				Actions.Add(Set);
			}
		}
		if (CanSpecialSummon(*Card) && EmptyMonsterZone(EDuelOwner::Player) != INDEX_NONE)
		{
			FDuelActionInfo Special;
			Special.Action = EDuelAction::SpecialSummon;
			Special.Label = SpecialSummonLabel(*Card);
			Actions.Add(Special);
		}
		else if (EffectRuntime && EffectRuntime->HasInherentSummon(*Card)
			&& EmptyMonsterZone(EDuelOwner::Player) != INDEX_NONE)
		{
			FDuelActionInfo Special;
			Special.Action = EDuelAction::SpecialSummon;
			Special.Label = TEXT("Special Summon");
			Actions.Add(Special);
		}
	}
	else if (Card->IsSpell())
	{
		if (CanActivateSpellCard(*Card))
		{
			FDuelActionInfo Activate;
			Activate.Action = EDuelAction::ActivateSpell;
			Activate.Label = IsFieldSpellCard(*Card) ? TEXT("Activate Field Spell") : TEXT("Activate");
			Actions.Add(Activate);
		}
		if (Card->Data.Subtype == TEXT("Quick-Play") && EmptySpellZone(EDuelOwner::Player) != INDEX_NONE)
		{
			FDuelActionInfo Set;
			Set.Action = EDuelAction::SetSpellTrap;
			Set.Label = TEXT("Set Quick-Play");
			Actions.Add(Set);
		}
	}
	else if (Card->IsTrap())
	{
		if (EmptySpellZone(EDuelOwner::Player) != INDEX_NONE)
		{
			FDuelActionInfo Set;
			Set.Action = EDuelAction::SetSpellTrap;
			Set.Label = TEXT("Set Trap");
			Actions.Add(Set);
		}
	}
	return Actions;
}

TArray<FDuelActionInfo> FDuelEngine::GetMonsterActions(int32 Uid)
{
	TArray<FDuelActionInfo> Actions;
	if (!CanPlayerAct())
	{
		return Actions;
	}
	const FDuelCard* Card = FindMonster(Uid);
	if (!Card || Card->Controller != EDuelOwner::Player)
	{
		return Actions;
	}

	if (IsMainPhase())
	{
		if (!Card->bFaceUp)
		{
			if (Card->SetTurn < TurnNumber)
			{
				FDuelActionInfo Flip;
				Flip.Action = EDuelAction::FlipSummon;
				Flip.Label = TEXT("Flip Summon");
				Actions.Add(Flip);
			}
		}
		else
		{
			if (Card->PositionChangedTurn != TurnNumber && Card->SummonedTurn != TurnNumber)
			{
				FDuelActionInfo Change;
				Change.Action = EDuelAction::ChangePosition;
				Change.Label = Card->Position == EDuelPosition::Attack ? TEXT("Change to Defense") : TEXT("Change to Attack");
				Actions.Add(Change);
			}
			Actions.Append(GetMonsterEffectActionsFor(*Card));
		}
	}
	if (Phase == EDuelPhase::Battle && CanAttack(*Card))
	{
		FDuelActionInfo AttackAction;
		AttackAction.Action = EDuelAction::None;
		AttackAction.Label = TEXT("Attack");
		Actions.Add(AttackAction);
	}
	return Actions;
}

TArray<FDuelActionInfo> FDuelEngine::GetSpellTrapActions(int32 Uid)
{
	TArray<FDuelActionInfo> Actions;
	if (!CanPlayerAct() || !IsMainPhase())
	{
		return Actions;
	}
	const FDuelCard* Card = FindSpellTrap(Uid);
	if (!Card || Card->Controller != EDuelOwner::Player || Card->bFaceUp || Card->SetTurn >= TurnNumber)
	{
		return Actions;
	}
	if (EffectRuntime && EffectRuntime->IsCardActivationLocked(*Card))
	{
		return Actions;
	}
	if (Card->IsSpell())
	{
		if (Card->Data.Subtype == TEXT("Quick-Play"))
		{
			FDuelActionInfo Action;
			Action.Action = EDuelAction::ActivateSpell;
			Action.Label = TEXT("Activate Quick-Play");
			Actions.Add(Action);
		}
		return Actions;
	}
	if (!IsManualTrapCard(*Card))
	{
		return Actions;
	}

	bool bLegal = true;
	if (IsName(*Card, TEXT("Call of the Haunted")))
	{
		bLegal = EmptyMonsterZone(EDuelOwner::Player) != INDEX_NONE;
		if (bLegal)
		{
			bLegal = Player.Graveyard.ContainsByPredicate([this](const FDuelCard& C)
			{
				return C.IsMonster() && CanBeSpecialSummonedByEffect(C);
			});
		}
	}
	else if (IsName(*Card, TEXT("Spiritual Fire Art - Kurenai")))
	{
		bLegal = OwnMonsters(EDuelOwner::Player).ContainsByPredicate([](const FDuelCard* C) { return C->Data.Attribute == TEXT("FIRE"); });
	}
	else if (IsName(*Card, TEXT("Spiritual Water Art - Aoi")))
	{
		bLegal = OwnMonsters(EDuelOwner::Player).ContainsByPredicate([](const FDuelCard* C) { return C->Data.Attribute == TEXT("WATER"); });
	}
	else if (IsName(*Card, TEXT("Spiritual Wind Art - Miyabi")))
	{
		bLegal = OwnMonsters(EDuelOwner::Player).ContainsByPredicate([](const FDuelCard* C) { return C->Data.Attribute == TEXT("WIND"); });
	}
	if (bLegal)
	{
		FDuelActionInfo Action;
		Action.Action = EDuelAction::ActivateTrap;
		Action.Label = TEXT("Activate Trap");
		Actions.Add(Action);
	}
	return Actions;
}

TArray<FDuelAttackTarget> FDuelEngine::GetAttackTargets(int32 AttackerUid) const
{
	TArray<FDuelAttackTarget> Targets;
	if (HasPendingChoice())
	{
		return Targets;
	}
	const FDuelCard* Attacker = FindMonster(AttackerUid);
	if (!Attacker || Attacker->Controller != EDuelOwner::Player || !CanAttack(*Attacker))
	{
		return Targets;
	}
	const bool bDirect = CountMonsters(EDuelOwner::Opponent) == 0
		|| (IsName(*Attacker, TEXT("Amphibious Bugroth MK-3")) && HasUmi(EDuelOwner::Player));
	if (bDirect)
	{
		Targets.Add({ 0, true, TEXT("Direct Attack") });
		return Targets;
	}
	for (const FDuelCard& Monster : Opponent.Monsters)
	{
		if (!Monster.IsValid())
		{
			continue;
		}
		FDuelAttackTarget Target;
		Target.Uid = Monster.Uid;
		Target.bDirect = false;
		Target.Label = Monster.bFaceUp
			? FString::Printf(TEXT("%s (%d/%d)"), *CardName(Monster), GetAtk(Monster), GetDef(Monster))
			: TEXT("Set Monster");
		Targets.Add(Target);
	}
	return Targets;
}

int32 FDuelEngine::GetRequiredTributes(int32 HandUid) const
{
	for (const FDuelCard& Card : Player.Hand)
	{
		if (Card.Uid == HandUid && Card.IsMonster() && !IsNormalSummonLocked(Card))
		{
			return GetTributeCount(Card);
		}
	}
	return 0;
}

bool FDuelEngine::CanNormalSummon(const FDuelCard& Card, TArray<int32>* OutTributeUids)
{
	if (EffectRuntime && EffectRuntime->IsSummonLocked(EDuelOwner::Player, false))
	{
		return false;
	}
	if (!IsMainPhase() || !CanPlayerAct() || Player.bNormalSummoned || !Card.IsMonster() || IsNormalSummonLocked(Card))
	{
		return false;
	}
	const int32 Required = GetTributeCount(Card);
	const int32 Available = CountMonsters(EDuelOwner::Player);
	const int32 Empty = EmptyMonsterZone(EDuelOwner::Player);
	if (Required == 0)
	{
		return Empty != INDEX_NONE;
	}
	if (Available < Required)
	{
		return false;
	}
	if (Empty == INDEX_NONE && Available == Required)
	{
		return false;
	}
	if (OutTributeUids)
	{
		OutTributeUids->Reset();
		TArray<FDuelCard*> Candidates = OwnMonsters(EDuelOwner::Player);
		Candidates.Sort([](const FDuelCard& A, const FDuelCard& B)
		{
			return A.Data.Atk < B.Data.Atk;
		});
		for (int32 I = 0; I < Required && I < Candidates.Num(); ++I)
		{
			OutTributeUids->Add(Candidates[I]->Uid);
		}
	}
	return true;
}

// ---------------------------------------------------------------------------
// Summoning
// ---------------------------------------------------------------------------

bool FDuelEngine::CanSpecialSummon(const FDuelCard& Card)
{
	if (EffectRuntime && EffectRuntime->IsSummonLocked(EDuelOwner::Player, true))
	{
		return false;
	}
	if (!IsMainPhase() || !CanPlayerAct())
	{
		return false;
	}
	if (EmptyMonsterZone(EDuelOwner::Player) == INDEX_NONE)
	{
		return false;
	}
	if (IsName(Card, TEXT("Elemental Hero Bubbleman")))
	{
		return Player.Hand.Num() == 1;
	}
	if (IsName(Card, TEXT("Ocean Dragon Lord - Neo-Daedalus")))
	{
		return FindMonsterByName(EDuelOwner::Player, TEXT("Levia-Dragon - Daedalus")) != nullptr;
	}
	if (IsName(Card, TEXT("Spirit of Flames")) || IsName(Card, TEXT("Inferno")))
	{
		return Player.Graveyard.ContainsByPredicate([](const FDuelCard& C) { return C.IsMonster() && C.Data.Attribute == TEXT("FIRE"); });
	}
	if (IsName(Card, TEXT("Aqua Spirit")))
	{
		return Player.Graveyard.ContainsByPredicate([](const FDuelCard& C) { return C.IsMonster() && C.Data.Attribute == TEXT("WATER"); });
	}
	if (IsName(Card, TEXT("Fenrir")))
	{
		int32 Count = 0;
		for (const FDuelCard& C : Player.Graveyard)
		{
			if (C.IsMonster() && C.Data.Attribute == TEXT("WATER")) ++Count;
		}
		return Count >= 2;
	}
	if (IsName(Card, TEXT("Garuda the Wind Spirit")) || IsName(Card, TEXT("Silpheed")))
	{
		return Player.Graveyard.ContainsByPredicate([](const FDuelCard& C) { return C.IsMonster() && C.Data.Attribute == TEXT("WIND"); });
	}
	return false;
}

FString FDuelEngine::SpecialSummonLabel(const FDuelCard& Card) const
{
	if (IsName(Card, TEXT("Fenrir"))) return TEXT("Special Summon (banish 2 WATER)");
	if (IsName(Card, TEXT("Ocean Dragon Lord - Neo-Daedalus"))) return TEXT("Special Summon (tribute Levia)");
	if (IsName(Card, TEXT("Elemental Hero Bubbleman"))) return TEXT("Special Summon");
	return TEXT("Special Summon (banish 1)");
}

bool FDuelEngine::PerformSpecialSummon(FDuelCard& Card, EDuelOwner Side)
{
	const FString Name = Card.Data.Name;
	const int32 Uid = Card.Uid;
	if (EffectRuntime && EffectRuntime->IsSummonLocked(Side, true))
	{
		return false;
	}

	if (IsName(Card, TEXT("Ocean Dragon Lord - Neo-Daedalus")))
	{
		FDuelCard* Levia = FindMonsterByName(Side, TEXT("Levia-Dragon - Daedalus"));
		if (!Levia)
		{
			return false;
		}
		const int32 LeviaUid = Levia->Uid;
		FDuelCard LeviaCopy;
		if (RemoveFromZone(LeviaCopy, LeviaUid))
		{
			CleanupEquips(LeviaCopy);
			MoveToGrave(LeviaCopy);
			Log(TEXT("Levia-Dragon - Daedalus is tributed."), TEXT("summon"));
		}
	}
	else if (IsName(Card, TEXT("Spirit of Flames")) || IsName(Card, TEXT("Inferno")))
	{
		FDuelCard* Banish = nullptr;
		for (FDuelCard& GraveCard : SideRef(Side).Graveyard)
		{
			if (GraveCard.IsMonster() && GraveCard.Data.Attribute == TEXT("FIRE"))
			{
				Banish = &GraveCard;
				break;
			}
		}
		if (!Banish) return false;
		const int32 BanishUid = Banish->Uid;
		FDuelCard Copy;
		RemoveFromZone(Copy, BanishUid);
		MoveToBanished(Copy);
		Log(FString::Printf(TEXT("%s is banished for %s."), *CardName(Copy), *Name), TEXT("effect"));
	}
	else if (IsName(Card, TEXT("Aqua Spirit")))
	{
		FDuelCard* Banish = nullptr;
		for (FDuelCard& GraveCard : SideRef(Side).Graveyard)
		{
			if (GraveCard.IsMonster() && GraveCard.Data.Attribute == TEXT("WATER"))
			{
				Banish = &GraveCard;
				break;
			}
		}
		if (!Banish) return false;
		const int32 BanishUid = Banish->Uid;
		FDuelCard Copy;
		RemoveFromZone(Copy, BanishUid);
		MoveToBanished(Copy);
		Log(FString::Printf(TEXT("%s is banished for %s."), *CardName(Copy), *Name), TEXT("effect"));
	}
	else if (IsName(Card, TEXT("Fenrir")))
	{
		int32 Remaining = 2;
		while (Remaining > 0)
		{
			FDuelCard* Banish = nullptr;
			for (FDuelCard& GraveCard : SideRef(Side).Graveyard)
			{
				if (GraveCard.IsMonster() && GraveCard.Data.Attribute == TEXT("WATER"))
				{
					Banish = &GraveCard;
					break;
				}
			}
			if (!Banish) return false;
			const int32 BanishUid = Banish->Uid;
			FDuelCard Copy;
			RemoveFromZone(Copy, BanishUid);
			MoveToBanished(Copy);
			--Remaining;
		}
		Log(TEXT("Two WATER monsters are banished for Fenrir."), TEXT("effect"));
	}
	else if (IsName(Card, TEXT("Garuda the Wind Spirit")) || IsName(Card, TEXT("Silpheed")))
	{
		FDuelCard* Banish = nullptr;
		for (FDuelCard& GraveCard : SideRef(Side).Graveyard)
		{
			if (GraveCard.IsMonster() && GraveCard.Data.Attribute == TEXT("WIND"))
			{
				Banish = &GraveCard;
				break;
			}
		}
		if (!Banish) return false;
		const int32 BanishUid = Banish->Uid;
		FDuelCard Copy;
		RemoveFromZone(Copy, BanishUid);
		MoveToBanished(Copy);
		Log(FString::Printf(TEXT("%s is banished for %s."), *CardName(Copy), *Name), TEXT("effect"));
	}

	FDuelCard Self;
	if (!RemoveFromZone(Self, Uid) || Self.Uid != Uid)
	{
		return false;
	}
	if (!PlaceMonster(Side, Self, true, EDuelPosition::Attack))
	{
		MoveToGrave(Self);
		return false;
	}
	Self = *FindMonster(Uid);
	Self.bSpecialSummoned = true;
	return true;
}

bool FDuelEngine::SpecialSummon(int32 Uid, FString& OutError)
{
	if (!CanPlayerAct() || !IsMainPhase())
	{
		OutError = TEXT("You cannot Special Summon right now.");
		return false;
	}
	FDuelCard* HandCard = nullptr;
	for (FDuelCard& Card : Player.Hand)
	{
		if (Card.Uid == Uid)
		{
			HandCard = &Card;
			break;
		}
	}
	if (!HandCard || !CanSpecialSummon(*HandCard))
	{
		if (EffectRuntime && EffectRuntime->IsSummonLocked(EDuelOwner::Player, true))
		{
			OutError = TEXT("Special Summons are currently locked.");
			return false;
		}
		if (HandCard && EffectRuntime && EffectRuntime->HasInherentSummon(*HandCard))
		{
			return EffectRuntime->ActivateInherentSummon(Uid, OutError);
		}
		OutError = TEXT("That monster cannot be Special Summoned right now.");
		return false;
	}
	const FString Name = HandCard->Data.Name;
	if (!PerformSpecialSummon(*HandCard, EDuelOwner::Player))
	{
		OutError = TEXT("The Special Summon could not be completed.");
		return false;
	}
	FDuelCard* Summoned = FindMonster(Uid);
	if (!Summoned)
	{
		return true;
	}
	Summoned->bSpecialSummoned = true;
	Log(FString::Printf(TEXT("You Special Summon %s."), *Name), TEXT("summon"));
	OnSummon(*Summoned, true);
	if (bWinnerSet) return true;
	if (FDuelCard* Live = FindMonster(Uid))
	{
		TriggerSummonTraps(*Live, false);
	}
	if (bWinnerSet) return true;
	CheckWinner();
	return true;
}

void FDuelEngine::OnSummon(FDuelCard& Card, bool bSpecial, int32 TributeCount, bool bFlipSummon)
{
	EDuelOwner Side = Card.Controller;
	FDuelSide& State = SideRef(Side);
	if (bSpecial && Side == EDuelOwner::Player)
	{
		++ResultStats.SpecialSummons;
	}
	Card.SummonedTurn = TurnNumber;
	Card.SetTurn = -1;
	FDuelVisualEvent& SummonEvent = EmitVisual(EDuelVisualEventType::Summon, Side, &Card, TributeCount, CardName(Card), false);
	SummonEvent.Zone = FindMonsterZone(Side, Card.Uid);

	if (IsName(Card, TEXT("Elemental Hero Bubbleman")))
	{
		int32 OwnFieldCards = 0;
		for (const FDuelCard& Own : State.Monsters) if (Own.IsValid() && Own.bFaceUp) ++OwnFieldCards;
		for (const FDuelCard& Own : State.Spells) if (Own.IsValid()) ++OwnFieldCards;
		if (State.Field.IsValid()) ++OwnFieldCards;
		if (State.Hand.Num() == 0 && OwnFieldCards == 1)
		{
			Log(TEXT("Elemental Hero Bubbleman draws 2 cards."), TEXT("effect"));
			Draw(Side, 2);
		}
	}
	else if (IsName(Card, TEXT("Granadora")))
	{
		GainLp(Side, 1000, TEXT("Granadora"));
	}
	else if (IsName(Card, TEXT("Des Frog")) && TributeCount > 0 && !bFlipSummon)
	{
		int32 Tadpoles = 0;
		for (const FDuelCard& GraveCard : State.Graveyard)
		{
			if (IsName(GraveCard, TEXT("T.A.D.P.O.L.E."))) ++Tadpoles;
		}
		for (int32 I = 0; I < Tadpoles; ++I)
		{
			if (EmptyMonsterZone(Side) == INDEX_NONE) break;
			FDuelCard* Copy = FindMonsterInHand(Side, TEXT("Des Frog"));
			bool bFromDeck = false;
			if (!Copy)
			{
				Copy = FindCardInDeck(Side, TEXT("Des Frog"));
				bFromDeck = true;
			}
			if (!Copy) break;
			const int32 CopyUid = Copy->Uid;
			FDuelCard SummonCopy;
			RemoveFromZone(SummonCopy, CopyUid);
			if (PlaceMonster(Side, SummonCopy, true, EDuelPosition::Attack))
			{
				FDuelCard* Placed = FindMonster(CopyUid);
				if (Placed)
				{
					Placed->bSpecialSummoned = true;
					OnSummon(*Placed, true);
				}
				Log(FString::Printf(TEXT("%s Special Summons Des Frog from the %s."), *State.Name,
					bFromDeck ? TEXT("Deck") : TEXT("hand")), TEXT("effect"));
			}
			else
			{
				// The card was removed from its zone, so never drop it if the
				// field filled up between the check and placement.
				MoveToGrave(SummonCopy);
			}
		}
	}
	else if ((IsName(Card, TEXT("Harpie Lady")) || IsName(Card, TEXT("Harpie Lady Sisters")) || IsName(Card, TEXT("Cyber Harpie Lady"))) && !bFlipSummon)
	{
		if (HasField(Side, TEXT("Harpies' Hunting Ground")))
		{
			int32 TargetUid = 0;
			for (const FDuelCard& Spell : SideRef(Other(Side)).Spells)
			{
				if (Spell.IsValid())
				{
					TargetUid = Spell.Uid;
					break;
				}
			}
			if (TargetUid == 0 && SideRef(Other(Side)).Field.IsValid())
			{
				TargetUid = SideRef(Other(Side)).Field.Uid;
			}
			if (TargetUid != 0)
			{
				if (FDuelCard* Target = FindSpellTrap(TargetUid))
				{
					Log(FString::Printf(TEXT("Harpies' Hunting Ground destroys %s."), *CardName(*Target)), TEXT("effect"));
					DestroySpellTrap(*Target, true);
				}
			}
		}
	}

	if (bWinnerSet)
	{
		return;
	}
	if (IsName(Card, TEXT("Harpies' Hunting Ground")))
	{
		// The field card itself never has a summon effect.
	}
	if (EffectRuntime)
	{
		EffectRuntime->OnSummon(Card, bSpecial, bFlipSummon, TributeCount);
	}
}

bool FDuelEngine::NormalSummon(int32 Uid, const TArray<int32>& TributeUids, bool bSet, FString& OutError)
{
	if (!CanPlayerAct() || !IsMainPhase())
	{
		OutError = TEXT("You cannot Summon right now.");
		return false;
	}
	if (Player.bNormalSummoned)
	{
		OutError = TEXT("You have already Normal Summoned this turn.");
		return false;
	}
	FDuelCard* HandCard = nullptr;
	for (FDuelCard& Card : Player.Hand)
	{
		if (Card.Uid == Uid)
		{
			HandCard = &Card;
			break;
		}
	}
	if (!HandCard || !HandCard->IsMonster() || IsNormalSummonLocked(*HandCard))
	{
		OutError = TEXT("That card cannot be Normal Summoned.");
		return false;
	}
	if (EffectRuntime && EffectRuntime->IsSummonLocked(EDuelOwner::Player, false))
	{
		OutError = TEXT("Normal Summons are currently locked.");
		return false;
	}

	const int32 Required = GetTributeCount(*HandCard);
	if (TributeUids.Num() != Required)
	{
		OutError = FString::Printf(TEXT("This Summon requires %d tribute(s)."), Required);
		return false;
	}
	if (EmptyMonsterZone(EDuelOwner::Player) == INDEX_NONE && Required == 0)
	{
		OutError = TEXT("All of your Monster Zones are occupied.");
		return false;
	}

	TSet<int32> SeenTributes;
	TArray<FDuelCard> Tributes;
	for (int32 TributeUid : TributeUids)
	{
		if (SeenTributes.Contains(TributeUid))
		{
			OutError = TEXT("A monster cannot be tributed twice.");
			return false;
		}
		SeenTributes.Add(TributeUid);
		FDuelCard* FieldMonster = FindMonster(TributeUid);
		if (!FieldMonster || FieldMonster->Controller != EDuelOwner::Player)
		{
			OutError = TEXT("One of the selected tributes is not on your field.");
			return false;
		}
		Tributes.Add(*FieldMonster);
	}

	const FString SummonName = HandCard->Data.Name;
	// A Tribute Summon frees a zone, so it is legal even with a full field.
	FDuelCard SelfCard;
	if (!RemoveFromZone(SelfCard, Uid))
	{
		OutError = TEXT("The card is no longer in your hand.");
		return false;
	}

	for (const FDuelCard& Tribute : Tributes)
	{
		FDuelCard TributeCopy;
		if (RemoveFromZone(TributeCopy, Tribute.Uid))
		{
			CleanupEquips(TributeCopy);
			MoveToGrave(TributeCopy);
		}
	}
	if (Required > 0)
	{
		Log(FString::Printf(TEXT("You Tribute Summon %s with %d tribute(s)."), *SummonName, Required), TEXT("summon"));
	}
	else
	{
		Log(FString::Printf(TEXT("You %s %s."), bSet ? TEXT("Set") : TEXT("Normal Summon"), *SummonName), TEXT("summon"));
	}
	if (!PlaceMonster(EDuelOwner::Player, SelfCard, !bSet, bSet ? EDuelPosition::Defense : EDuelPosition::Attack))
	{
		MoveToGrave(SelfCard);
		OutError = TEXT("There was no room for the monster.");
		return false;
	}
	Player.bNormalSummoned = true;

	FDuelCard* Placed = FindMonster(Uid);
	if (Placed)
	{
		if (bSet)
		{
			FDuelVisualEvent& SetEvent = EmitVisual(EDuelVisualEventType::SetCard, EDuelOwner::Player, Placed, Required, SummonName, true);
			SetEvent.Zone = FindMonsterZone(EDuelOwner::Player, Uid);
		}
		else
		{
			OnSummon(*Placed, false, Required);
		}
		if (!bWinnerSet && FindMonster(Uid))
		{
			TriggerSummonTraps(*FindMonster(Uid), true);
		}
	}
	CheckWinner();
	return true;
}

bool FDuelEngine::FlipSummon(int32 Uid, FString& OutError)
{
	if (!CanPlayerAct() || !IsMainPhase())
	{
		OutError = TEXT("You cannot Flip Summon right now.");
		return false;
	}
	FDuelCard* Card = FindMonster(Uid);
	if (!Card || Card->Controller != EDuelOwner::Player || Card->bFaceUp || Card->SetTurn >= TurnNumber)
	{
		OutError = TEXT("That monster cannot be Flip Summoned.");
		return false;
	}
	Card->bFaceUp = true;
	Card->Position = EDuelPosition::Attack;
	Card->PositionChangedTurn = TurnNumber;
	Log(FString::Printf(TEXT("You Flip Summon %s."), *CardName(*Card)), TEXT("summon"));
	OnSummon(*Card, false, 0, true);
	if (!bWinnerSet)
	{
		if (FDuelCard* FlipCard = FindMonster(Uid))
		{
			TriggerFlipEffect(*FlipCard, EDuelOwner::Player);
		}
	}
	if (!bWinnerSet && FindMonster(Uid))
	{
		// Trap Hole checks "Normal or Flip Summon"; the boolean here means
		// "not a Special Summon" inside TriggerSummonTraps.
		TriggerSummonTraps(*FindMonster(Uid), true);
	}
	CheckWinner();
	return true;
}

bool FDuelEngine::ChangePosition(int32 Uid, FString& OutError)
{
	if (!CanPlayerAct() || !IsMainPhase())
	{
		OutError = TEXT("You cannot change battle positions right now.");
		return false;
	}
	FDuelCard* Card = FindMonster(Uid);
	if (!Card || Card->Controller != EDuelOwner::Player || !Card->bFaceUp
		|| Card->PositionChangedTurn == TurnNumber || Card->SummonedTurn == TurnNumber)
	{
		OutError = TEXT("That monster cannot change position this turn.");
		return false;
	}
	if (EffectRuntime && EffectRuntime->IsPositionChangeLocked(*Card))
	{
		OutError = TEXT("That monster's battle position is locked.");
		return false;
	}
	const EDuelPosition PreviousPosition = Card->Position;
	Card->Position = Card->Position == EDuelPosition::Attack ? EDuelPosition::Defense : EDuelPosition::Attack;
	Card->PositionChangedTurn = TurnNumber;
	Log(FString::Printf(TEXT("%s is now in %s Position."), *CardName(*Card),
		Card->Position == EDuelPosition::Attack ? TEXT("Attack") : TEXT("Defense")), TEXT("effect"));
	EmitVisual(EDuelVisualEventType::Position, EDuelOwner::Player, Card, 0,
		Card->Position == EDuelPosition::Attack ? TEXT("ATTACK") : TEXT("DEFENSE"));
	if (EffectRuntime)
	{
		EffectRuntime->OnPositionChanged(*Card, PreviousPosition);
		EffectRuntime->RecomputeContinuous();
	}
	return true;
}

void FDuelEngine::EnterBattlePhase()
{
	if (!CanPlayerAct() || Phase != EDuelPhase::Main1)
	{
		return;
	}
	Phase = EDuelPhase::Battle;
	Log(TEXT("You enter the Battle Phase."), TEXT("phase"));
	EmitVisual(EDuelVisualEventType::PhaseChange, EDuelOwner::Player, nullptr, 0, TEXT("BATTLE PHASE"));
	if (EffectRuntime)
	{
		EffectRuntime->OnBattleStart(EDuelOwner::Player);
	}
}

void FDuelEngine::EndBattlePhase()
{
	if (!CanPlayerAct() || Phase != EDuelPhase::Battle)
	{
		return;
	}
	Phase = EDuelPhase::Main2;
	Log(TEXT("You end the Battle Phase."), TEXT("phase"));
	EmitVisual(EDuelVisualEventType::PhaseChange, EDuelOwner::Player, nullptr, 0, TEXT("MAIN PHASE 2"));
	if (EffectRuntime)
	{
		EffectRuntime->OnBattleEnd();
	}
}

// ---------------------------------------------------------------------------
// Battle
// ---------------------------------------------------------------------------

bool FDuelEngine::CanAttack(const FDuelCard& Card) const
{
	if (bWinnerSet || Phase != EDuelPhase::Battle || Card.Controller != ActiveSide)
	{
		return false;
	}
	if (!Card.IsValid() || !Card.IsMonster() || !Card.bFaceUp || Card.Position != EDuelPosition::Attack || Card.bHasAttacked)
	{
		return false;
	}
	if (EffectRuntime && !EffectRuntime->CanCardAttack(Card))
	{
		return false;
	}
	if (IsName(Card, TEXT("Cave Dragon")))
	{
		bool bOtherDragon = false;
		for (const FDuelCard& Monster : SideRef(Card.Controller).Monsters)
		{
			if (Monster.IsValid() && Monster.Uid != Card.Uid && Monster.bFaceUp && IsDragon(Monster))
			{
				bOtherDragon = true;
				break;
			}
		}
		if (!bOtherDragon)
		{
			return false;
		}
	}
	// Gora Turtle prevents monsters with 1900 or more ATK from attacking.
	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		for (const FDuelCard& OpponentMonster : SideRef(Side).Monsters)
		{
			if (OpponentMonster.IsValid() && OpponentMonster.bFaceUp && IsName(OpponentMonster, TEXT("Gora Turtle"))
				&& GetAtk(Card) >= 1900)
			{
				return false;
			}
		}
	}
	return true;
}

bool FDuelEngine::Attack(int32 AttackerUid, int32 TargetUid, FString& OutError)
{
	if (!IsPlayerTurn())
	{
		OutError = TEXT("It is not your turn.");
		return false;
	}
	return ExecuteAttack(EDuelOwner::Player, AttackerUid, TargetUid, OutError);
}

bool FDuelEngine::ExecuteAttack(EDuelOwner AttackerSide, int32 AttackerUid, int32 TargetUid, FString& OutError)
{
	if (HasPendingChoice())
	{
		OutError = TEXT("Answer the pending choice first.");
		return false;
	}
	if (bWinnerSet || Phase != EDuelPhase::Battle || ActiveSide != AttackerSide)
	{
		OutError = TEXT("You cannot attack right now.");
		return false;
	}
	FDuelCard* Attacker = FindMonster(AttackerUid);
	if (!Attacker || Attacker->Controller != AttackerSide || !CanAttack(*Attacker))
	{
		OutError = TEXT("That monster cannot attack.");
		return false;
	}
	EDuelOwner DefenderSide = Other(AttackerSide);
	FDuelCard* Target = TargetUid > 0 ? FindMonster(TargetUid) : nullptr;
	if (Target && Target->Controller != DefenderSide)
	{
		OutError = TEXT("That is not a valid attack target.");
		return false;
	}
	const bool bDirectAllowed = CountMonsters(DefenderSide) == 0
		|| (IsName(*Attacker, TEXT("Amphibious Bugroth MK-3")) && HasUmi(AttackerSide))
		|| (EffectRuntime && EffectRuntime->CanAttackDirectly(*Attacker));
	if (!Target && !bDirectAllowed)
	{
		OutError = TEXT("You must choose an attack target.");
		return false;
	}
	if (EffectRuntime && !EffectRuntime->CanDeclareAttack(*Attacker, Target == nullptr))
	{
		OutError = TEXT("That monster cannot declare this attack.");
		return false;
	}

	Attacker->bHasAttacked = true;
	++Attacker->AttacksUsed;
	const FString AttackerName = CardName(*Attacker);
	{
		FDuelVisualEvent AttackEvent;
		AttackEvent.Type = EDuelVisualEventType::Attack;
		AttackEvent.Side = AttackerSide;
		AttackEvent.CardUid = Attacker->Uid;
		AttackEvent.CardId = Attacker->Data.Id;
		AttackEvent.TargetUid = Target ? Target->Uid : 0;
		AttackEvent.TargetCardId = Target ? Target->Data.Id : 0;
		AttackEvent.Zone = FindMonsterZone(AttackerSide, Attacker->Uid);
		AttackEvent.TargetZone = Target ? FindMonsterZone(DefenderSide, Target->Uid) : INDEX_NONE;
		AttackEvent.bDirect = Target == nullptr;
		AttackEvent.Text = Target ? CardName(*Target) : TEXT("Direct Attack");
		VisualEvents.Add(AttackEvent);
	}
	Log(FString::Printf(TEXT("%s %s attacks%s!"), *SideRef(AttackerSide).Name,
		AttackerSide == EDuelOwner::Player ? TEXT("use") : TEXT("uses"),
		Target ? *FString::Printf(TEXT(" %s"), *CardName(*Target)) : TEXT(" directly")), TEXT("battle"));

	if (EffectRuntime)
	{
		EffectRuntime->OnAttackDeclared(*Attacker, Target);
		if (bWinnerSet || !FindMonster(AttackerUid))
		{
			return true;
		}
		Attacker = FindMonster(AttackerUid);
		if (TargetUid > 0)
		{
			Target = FindMonster(TargetUid);
			if (!Target)
			{
				return true;
			}
		}
		EffectRuntime->OnAttackTarget(*Attacker, Target);
		if (EffectRuntime->ConsumeAttackNegated())
		{
			Log(FString::Printf(TEXT("%s's attack is negated."), *AttackerName), TEXT("effect"));
			return true;
		}
		if (bWinnerSet || !FindMonster(AttackerUid))
		{
			return true;
		}
		Attacker = FindMonster(AttackerUid);
		if (TargetUid > 0)
		{
			Target = FindMonster(TargetUid);
			if (!Target)
			{
				return true;
			}
		}
	}

	// Winged Kuriboh LV10 punishes an attack during the opponent's Battle Phase.
	FDuelCard* Kuriboh = FindMonsterByName(DefenderSide, TEXT("Winged Kuriboh LV10"));
	if (Kuriboh && Kuriboh->bFaceUp)
	{
		const int32 KuribohUid = Kuriboh->Uid;
		Log(TEXT("Winged Kuriboh LV10 activates!"), TEXT("effect"));
		TArray<int32> Attackers;
		int32 Burn = 0;
		for (const FDuelCard& Monster : SideRef(AttackerSide).Monsters)
		{
			if (Monster.IsValid() && Monster.bFaceUp && Monster.Position == EDuelPosition::Attack)
			{
				Attackers.Add(Monster.Uid);
				Burn += Monster.Data.Atk;
			}
		}
		FDuelCard Sacrifice;
		if (RemoveFromZone(Sacrifice, KuribohUid))
		{
			CleanupEquips(Sacrifice);
			MoveToGrave(Sacrifice);
		}
		for (int32 Uid : Attackers)
		{
			if (FDuelCard* Monster = FindMonster(Uid))
			{
				DestroyMonster(*Monster, false, nullptr, false, TEXT("Winged Kuriboh LV10"));
			}
		}
		InflictDamage(AttackerSide, Burn, TEXT("Winged Kuriboh LV10"));
		CheckWinner();
		return true;
	}

	// Reactive Trap timing: one defensive Trap per attack.
	if (FDuelCard* Trap = PickAttackTrap(DefenderSide, *Attacker, Target))
	{
		const int32 TrapUid = Trap->Uid;
		const FString TrapName = CardName(*Trap);
		bool bTrapNegated = TryCounterTrap(DefenderSide, AttackerSide);
		if (bTrapNegated)
		{
			if (FDuelCard* Negated = FindSpellTrap(TrapUid))
			{
				DestroySpellTrap(*Negated, true);
			}
			Log(FString::Printf(TEXT("%s is negated."), *TrapName), TEXT("trap"));
		}
		if (!bTrapNegated && ResolveAttackTrap(*Trap, DefenderSide, *Attacker, Target, AttackerSide))
		{
			// The attack was negated or the Battle Phase ended. Multi-attack
			// monsters still get their second swing if they survived a negated
			// attack (for example, Magic Cylinder).
			if (FDuelCard* Still = FindMonster(AttackerUid))
			{
				const bool bMermaidExtra = IsName(*Still, TEXT("Mermaid Knight"))
					&& HasUmi(Still->Controller) && Still->AttacksUsed < 2;
				const bool bGrayWingExtra = Still->ExtraAttacks > 0 && Still->AttacksUsed <= 1;
				if (bMermaidExtra || bGrayWingExtra)
				{
					Still->bHasAttacked = false;
				}
			}
			return true;
		}
		if (bWinnerSet || !FindMonster(AttackerUid))
		{
			return true;
		}
		Attacker = FindMonster(AttackerUid);
		if (TargetUid > 0)
		{
			Target = FindMonster(TargetUid);
			if (!Target && CountMonsters(DefenderSide) > 0)
			{
				return true;
			}
			if (!Target && !bDirectAllowed)
			{
				return true;
			}
		}
	}

	if (!Target)
	{
		int32 Damage = GetBattleAtk(*Attacker, nullptr);
		if (EffectRuntime)
		{
			Damage = FMath::FloorToInt(Damage * EffectRuntime->GetBattleDamageMultiplier(Attacker->Uid));
		}
		Log(FString::Printf(TEXT("%s attacks directly for %d damage."), *AttackerName, Damage), TEXT("damage"));
		const int32 LpBefore = GetSide(DefenderSide).LP;
		InflictBattleDamage(DefenderSide, Damage, AttackerName);
		if (EffectRuntime && !bWinnerSet && GetSide(DefenderSide).LP < LpBefore)
		{
			if (FDuelCard* StillAttacker = FindMonster(AttackerUid))
			{
				EffectRuntime->OnBattleDamage(DefenderSide, LpBefore - GetSide(DefenderSide).LP, *StillAttacker, nullptr, true);
			}
		}
		if (FDuelCard* StillAttacker = FindMonster(AttackerUid))
		{
			AfterAttack(*StillAttacker);
		}
		CheckWinner();
		return true;
	}

	ResolveBattle(*Attacker, Target);
	CheckWinner();
	return true;
}

FDuelCard* FDuelEngine::PickAttackTrap(EDuelOwner Defender, FDuelCard& Attacker, FDuelCard* Target)
{
	if (EffectRuntime && EffectRuntime->IsTrapActivationLocked())
	{
		return nullptr;
	}
	FDuelSide& DefenderSide = SideRef(Defender);
	const int32 Incoming = GetBattleAtk(Attacker, Target);
	const bool bLethal = Incoming >= DefenderSide.LP;
	const int32 Attackers = CountMonsters(Attacker.Controller);

	FDuelCard* Mirror = nullptr;
	FDuelCard* Cylinder = nullptr;
	FDuelCard* Negate = nullptr;
	FDuelCard* Hero = nullptr;
	for (FDuelCard& Spell : DefenderSide.Spells)
	{
		if (!Spell.IsValid() || Spell.bFaceUp || Spell.SetTurn >= TurnNumber)
		{
			continue;
		}
		if (!IsAutomaticTrapTimingAllowed(Spell, EDuelTimingWindow::ResponseToAttack))
		{
			continue;
		}
		if (IsName(Spell, TEXT("Mirror Force"))) Mirror = &Spell;
		else if (IsName(Spell, TEXT("Magic Cylinder"))) Cylinder = &Spell;
		else if (IsName(Spell, TEXT("Negate Attack"))) Negate = &Spell;
		else if (IsName(Spell, TEXT("A Hero Emerges"))) Hero = &Spell;
	}
	if (Mirror && (Attackers >= 2 || bLethal)) return Mirror;
	if (Cylinder && (bLethal || Incoming >= 1500)) return Cylinder;
	if (Negate && (bLethal || CountMonsters(Defender) == 0 || Incoming >= 2000)) return Negate;
	if (Hero && CountMonsters(Defender) == 0
		&& DefenderSide.Hand.ContainsByPredicate([](const FDuelCard& C) { return C.IsMonster(); }))
	{
		return Hero;
	}
	return nullptr;
}

bool FDuelEngine::ResolveAttackTrap(FDuelCard& Trap, EDuelOwner Defender, FDuelCard& Attacker, FDuelCard*& Target, EDuelOwner AttackerSide)
{
	const int32 TrapUid = Trap.Uid;
	const FString TrapName = CardName(Trap);
	Trap.bFaceUp = true;
	Log(FString::Printf(TEXT("%s activates %s!"), *SideRef(Defender).Name, *TrapName), TEXT("trap"));
	FDuelVisualEvent& TrapEvent = EmitVisual(EDuelVisualEventType::Trap, Defender, &Trap, 0, TrapName);
	TrapEvent.Zone = FindSpellZone(Defender, TrapUid);

	if (TrapName == TEXT("Mirror Force"))
	{
		TArray<int32> Attackers;
		for (const FDuelCard& Monster : SideRef(AttackerSide).Monsters)
		{
			if (Monster.IsValid() && Monster.bFaceUp && Monster.Position == EDuelPosition::Attack)
			{
				Attackers.Add(Monster.Uid);
			}
		}
		for (int32 Uid : Attackers)
		{
			if (FDuelCard* Monster = FindMonster(Uid))
			{
				DestroyMonster(*Monster, false, nullptr, false, TEXT("Mirror Force"));
			}
		}
		Log(TEXT("Mirror Force destroys all Attack Position monsters."), TEXT("trap"));
		if (FDuelCard* StillThere = FindSpellTrap(TrapUid))
		{
			if (!IsPersistentSpellTrap(*StillThere)) DestroySpellTrap(*StillThere, true);
		}
		return true;
	}
	if (TrapName == TEXT("Magic Cylinder"))
	{
		const int32 Damage = GetAtk(Attacker);
		Log(FString::Printf(TEXT("Magic Cylinder burns %s for %d."), *SideRef(AttackerSide).Name, Damage), TEXT("trap"));
		InflictDamage(AttackerSide, Damage, TEXT("Magic Cylinder"));
		if (FDuelCard* StillThere = FindSpellTrap(TrapUid)) DestroySpellTrap(*StillThere, true);
		return true;
	}
	if (TrapName == TEXT("Negate Attack"))
	{
		Log(TEXT("Negate Attack ends the Battle Phase."), TEXT("trap"));
		EmitVisual(EDuelVisualEventType::PhaseChange, AttackerSide, nullptr, 0, TEXT("ATTACK NEGATED"));
		Phase = EDuelPhase::Main2;
		if (FDuelCard* StillThere = FindSpellTrap(TrapUid)) DestroySpellTrap(*StillThere, true);
		return true;
	}
	if (TrapName == TEXT("A Hero Emerges"))
	{
		FDuelSide& DefenderSide = SideRef(Defender);
		if (DefenderSide.Hand.Num() > 0)
		{
			const int32 Index = Random.RandRange(0, DefenderSide.Hand.Num() - 1);
			FDuelCard Revealed = DefenderSide.Hand[Index];
			RemoveFromZone(Revealed, Revealed.Uid);
			if (Revealed.IsMonster() && CanBeSpecialSummonedByEffect(Revealed) && EmptyMonsterZone(Defender) != INDEX_NONE)
			{
				if (PlaceMonster(Defender, Revealed, true, EDuelPosition::Attack))
				{
					if (FDuelCard* Placed = FindMonster(Revealed.Uid))
					{
						Placed->bSpecialSummoned = true;
						Log(FString::Printf(TEXT("A Hero Emerges reveals %s and Special Summons it."), *CardName(*Placed)), TEXT("trap"));
						Target = Placed;
						OnSummon(*Placed, true);
					}
				}
				else
				{
					MoveToGrave(Revealed);
				}
			}
			else
			{
				EmitVisual(EDuelVisualEventType::Effect, Defender, &Revealed, 0, TEXT("A HERO EMERGES: SENT TO GRAVE"));
				MoveToGrave(Revealed);
				Log(FString::Printf(TEXT("A Hero Emerges reveals %s and sends it to the Graveyard."), *CardName(Revealed)), TEXT("trap"));
			}
		}
		if (FDuelCard* StillThere = FindSpellTrap(TrapUid)) DestroySpellTrap(*StillThere, true);
		return false;
	}

	if (FDuelCard* StillThere = FindSpellTrap(TrapUid)) DestroySpellTrap(*StillThere, true);
	return false;
}

void FDuelEngine::ResolveBattle(FDuelCard& Attacker, FDuelCard* Target)
{
	if (!Target)
	{
		return;
	}
	const bool bWasFaceDown = !Target->bFaceUp;
	const EDuelOwner AttackerSide = Attacker.Controller;
	const EDuelOwner DefenderSide = Other(AttackerSide);
	if (bWasFaceDown)
	{
		Target->bFaceUp = true;
		Target->Position = EDuelPosition::Defense;
	}

	// Sasuke Samurai cuts down a face-down monster without flipping it.
	if (IsName(Attacker, TEXT("Sasuke Samurai")) && bWasFaceDown)
	{
		Log(FString::Printf(TEXT("Sasuke Samurai destroys %s without flipping it."), *CardName(*Target)), TEXT("effect"));
		Target->bFaceUp = false;
		DestroyMonster(*Target, true, &Attacker, bWasFaceDown, TEXT("Sasuke Samurai"));
		AfterAttack(Attacker);
		return;
	}

	const int32 AttackerUid = Attacker.Uid;
	const int32 TargetUid = Target->Uid;
	if (EffectRuntime)
	{
		EffectRuntime->OnDamageStep(Attacker, Target);
		if (bWinnerSet)
		{
			return;
		}
		if (!FindMonster(AttackerUid))
		{
			return;
		}
		Attacker = *FindMonster(AttackerUid);
		Target = FindMonster(TargetUid);
		if (!Target)
		{
			return;
		}
		EffectRuntime->OnDamageCalculated(Attacker, Target);
		if (bWinnerSet)
		{
			return;
		}
		if (!FindMonster(AttackerUid))
		{
			return;
		}
		Attacker = *FindMonster(AttackerUid);
		Target = FindMonster(TargetUid);
		if (!Target)
		{
			return;
		}
	}
	const int32 AttackerAtk = GetBattleAtk(Attacker, Target);
	const int32 TargetAtk = GetAtk(*Target);
	const int32 TargetDef = GetDef(*Target);
	const bool bTargetDefense = Target->Position == EDuelPosition::Defense;

	bool bDestroyTarget = false;
	bool bDestroyAttacker = false;
	int32 DamageToDefender = 0;
	int32 DamageToAttacker = 0;

	const bool bPiercing = IsName(Attacker, TEXT("Spear Dragon"))
		|| (EffectRuntime && EffectRuntime->HasPiercing(Attacker.Uid));

	if (!bTargetDefense)
	{
		if (AttackerAtk > TargetAtk)
		{
			bDestroyTarget = true;
			DamageToDefender = AttackerAtk - TargetAtk;
		}
		else if (AttackerAtk < TargetAtk)
		{
			bDestroyAttacker = true;
			DamageToAttacker = TargetAtk - AttackerAtk;
		}
		else if (AttackerAtk == TargetAtk)
		{
			// Kaiser Glider cannot be destroyed by a battle with equal ATK. That
			// protection applies only to Kaiser Glider itself; the other monster
			// is still destroyed. Two Kaiser Gliders simply bounce off each other.
			const bool bAttackerKaiser = IsName(Attacker, TEXT("Kaiser Glider"));
			const bool bTargetKaiser = IsName(*Target, TEXT("Kaiser Glider"));
			if (bAttackerKaiser && bTargetKaiser)
			{
				Log(TEXT("Both Kaiser Gliders survive the battle."), TEXT("effect"));
			}
			else if (bTargetKaiser)
			{
				Log(TEXT("Kaiser Glider survives the battle; its attacker is destroyed."), TEXT("effect"));
				bDestroyAttacker = true;
			}
			else if (bAttackerKaiser)
			{
				Log(TEXT("Kaiser Glider survives the battle; its target is destroyed."), TEXT("effect"));
				bDestroyTarget = true;
			}
			else
			{
				bDestroyTarget = true;
				bDestroyAttacker = true;
			}
		}
	}
	else
	{
		if (AttackerAtk > TargetDef)
		{
			bDestroyTarget = true;
			if (bPiercing) DamageToDefender = AttackerAtk - TargetDef;
		}
		else if (AttackerAtk < TargetDef)
		{
			DamageToAttacker = TargetDef - AttackerAtk;
		}
	}

	// Five-Headed Dragon cannot be damaged by battles with its protected attributes.
	const TSet<FString> FgdProtected = { TEXT("EARTH"), TEXT("WATER"), TEXT("FIRE"), TEXT("WIND"), TEXT("DARK") };
	if (IsName(Attacker, TEXT("F.G.D.")) && FgdProtected.Contains(Target->Data.Attribute)) DamageToAttacker = 0;
	if (IsName(*Target, TEXT("F.G.D.")) && FgdProtected.Contains(Attacker.Data.Attribute)) DamageToDefender = 0;

	if (DamageToDefender > 0)
	{
		EDuelOwner Receiver = DefenderSide;
		if (EffectRuntime)
		{
			EDuelOwner Redirected = DefenderSide;
			if (EffectRuntime->ShouldRedirectBattleDamage(TargetUid, DefenderSide, Redirected))
			{
				Receiver = Redirected;
			}
			if (EffectRuntime->IsBattleDamageZeroFor(TargetUid))
			{
				DamageToDefender = 0;
			}
			DamageToDefender = FMath::FloorToInt(
				DamageToDefender * EffectRuntime->GetBattleDamageMultiplier(AttackerUid));
		}
		if (DamageToDefender > 0)
		{
			Log(FString::Printf(TEXT("%s %s %d battle damage."), *SideRef(Receiver).Name,
				Receiver == EDuelOwner::Player ? TEXT("take") : TEXT("takes"), DamageToDefender), TEXT("damage"));
			const int32 LpBefore = GetSide(Receiver).LP;
			InflictBattleDamage(Receiver, DamageToDefender, TEXT("battle"));
			if (EffectRuntime && !bWinnerSet && GetSide(Receiver).LP < LpBefore)
			{
				if (FDuelCard* AttackerNow = FindMonster(AttackerUid))
				{
					EffectRuntime->OnBattleDamage(Receiver, LpBefore - GetSide(Receiver).LP,
						*AttackerNow, FindMonster(TargetUid), false);
				}
			}
		}
	}
	if (DamageToAttacker > 0)
	{
		EDuelOwner Receiver = AttackerSide;
		if (EffectRuntime)
		{
			EDuelOwner Redirected = AttackerSide;
			if (EffectRuntime->ShouldRedirectBattleDamage(AttackerUid, AttackerSide, Redirected))
			{
				Receiver = Redirected;
			}
			if (EffectRuntime->IsBattleDamageZeroFor(AttackerUid))
			{
				DamageToAttacker = 0;
			}
			DamageToAttacker = FMath::FloorToInt(
				DamageToAttacker * EffectRuntime->GetBattleDamageMultiplier(TargetUid));
		}
		if (DamageToAttacker > 0)
		{
			Log(FString::Printf(TEXT("%s %s %d battle damage."), *SideRef(Receiver).Name,
				Receiver == EDuelOwner::Player ? TEXT("take") : TEXT("takes"), DamageToAttacker), TEXT("damage"));
			const int32 LpBefore = GetSide(Receiver).LP;
			InflictBattleDamage(Receiver, DamageToAttacker, TEXT("battle"));
			if (EffectRuntime && !bWinnerSet && GetSide(Receiver).LP < LpBefore)
			{
				if (FDuelCard* AttackerNow = FindMonster(AttackerUid))
				{
					EffectRuntime->OnBattleDamage(Receiver, LpBefore - GetSide(Receiver).LP,
						*AttackerNow, FindMonster(TargetUid), false);
				}
			}
		}
	}

	// Flip effects resolve after the damage step but before the card leaves the field.
	if (bWasFaceDown && FindMonster(TargetUid))
	{
		TriggerFlipEffect(*FindMonster(TargetUid), DefenderSide);
	}
	if (bWinnerSet)
	{
		return;
	}

	if (bDestroyTarget)
	{
		FDuelCard* TargetNow = FindMonster(TargetUid);
		if (TargetNow)
		{
			const int32 OriginalAtk = TargetNow->Data.Atk;
			const bool bTargetDestroyed = true;
			const bool bWasWingedKuriboh = IsName(*TargetNow, TEXT("Winged Kuriboh"));
			const bool bWasYomiShip = IsName(*TargetNow, TEXT("Yomi Ship"));
			DestroyMonster(*TargetNow, true, FindMonster(AttackerUid), bWasFaceDown, TEXT("battle"));
			if (bTargetDestroyed)
			{
				FDuelCard* AttackerNow = FindMonster(AttackerUid);
				if (AttackerNow && (IsName(*AttackerNow, TEXT("Elemental Hero Flame Wingman"))
					|| IsName(*AttackerNow, TEXT("Elemental Hero Shining Flare Wingman"))))
				{
					InflictDamage(DefenderSide, OriginalAtk, CardName(*AttackerNow));
				}
				if (AttackerNow && IsName(*AttackerNow, TEXT("Inferno")))
				{
					InflictDamage(DefenderSide, 1500, TEXT("Inferno"));
				}
				if (AttackerNow && IsName(*AttackerNow, TEXT("Fenrir")))
				{
					SideRef(DefenderSide).bSkipDraw = true;
					Log(TEXT("Fenrir makes the opponent skip their next Draw Phase."), TEXT("effect"));
				}
				if (bWasYomiShip)
				{
					if (FDuelCard* YomiAttacker = FindMonster(AttackerUid))
					{
						Log(TEXT("Yomi Ship destroys the monster that destroyed it."), TEXT("effect"));
						DestroyMonster(*YomiAttacker, false, nullptr, false, TEXT("Yomi Ship"));
					}
				}
				if (bWasWingedKuriboh)
				{
					SideRef(DefenderSide).bBattleDamageZeroThisTurn = true;
				}
			}
		}
	}

	if (bDestroyAttacker)
	{
		FDuelCard* AttackerNow = FindMonster(AttackerUid);
		if (AttackerNow)
		{
			DestroyMonster(*AttackerNow, true, FindMonster(TargetUid), false, TEXT("battle"));
		}
	}

	if (FDuelCard* AttackerNow = FindMonster(AttackerUid))
	{
		AfterAttack(*AttackerNow);
	}
}

void FDuelEngine::AfterAttack(FDuelCard& Attacker)
{
	if (IsName(Attacker, TEXT("Spear Dragon")) && Attacker.bFaceUp)
	{
		Attacker.Position = EDuelPosition::Defense;
		Log(TEXT("Spear Dragon changes to Defense Position after attacking."), TEXT("effect"));
		EmitVisual(EDuelVisualEventType::Position, Attacker.Controller, &Attacker, 0, TEXT("SPEAR DRAGON: DEFENSE"));
	}
	if (IsName(Attacker, TEXT("Mermaid Knight")) && HasUmi(Attacker.Controller) && Attacker.AttacksUsed < 2)
	{
		Attacker.bHasAttacked = false;
	}
	if (Attacker.ExtraAttacks > 0 && Attacker.AttacksUsed <= 1)
	{
		Attacker.bHasAttacked = false;
	}
	if (EffectRuntime && EffectRuntime->HasExtraAttack(Attacker.Uid) && Attacker.AttacksUsed <= 1)
	{
		Attacker.bHasAttacked = false;
	}
}

void FDuelEngine::TriggerEndPhaseEffects(EDuelOwner TurnSide)
{
	if (bWinnerSet)
	{
		return;
	}
	// Garuda the Wind Spirit acts during the End Phase of its controller's
	// opponent, so the Garuda belongs to the side that is *not* ending its turn.
	const EDuelOwner Controller = Other(TurnSide);
	FDuelCard* Garuda = FindMonsterByName(Controller, TEXT("Garuda the Wind Spirit"));
	if (!Garuda || !Garuda->bFaceUp)
	{
		return;
	}

	FDuelCard* Target = ChooseMonster(TurnSide, [](const FDuelCard& Card)
	{
		return Card.bFaceUp && Card.Position == EDuelPosition::Attack;
	}, true);
	if (!Target)
	{
		Target = ChooseMonster(TurnSide, [](const FDuelCard& Card) { return Card.bFaceUp; }, true);
	}
	if (Target)
	{
		Target->Position = Target->Position == EDuelPosition::Attack ? EDuelPosition::Defense : EDuelPosition::Attack;
		Target->PositionChangedTurn = TurnNumber;
		Log(FString::Printf(TEXT("Garuda the Wind Spirit changes %s to %s Position."), *CardName(*Target),
			Target->Position == EDuelPosition::Attack ? TEXT("Attack") : TEXT("Defense")), TEXT("effect"));
		EmitVisual(EDuelVisualEventType::Position, Controller, Target, 0,
			Target->Position == EDuelPosition::Attack ? TEXT("GARUDA: ATTACK") : TEXT("GARUDA: DEFENSE"));
	}
}

void FDuelEngine::TriggerSummonTraps(FDuelCard& Summoned, bool bNormalSummon)
{
	if (bWinnerSet)
	{
		return;
	}
	if (EffectRuntime && EffectRuntime->IsTrapActivationLocked())
	{
		return;
	}
	FDuelSide& Defender = SideRef(Other(Summoned.Controller));
	FDuelCard* TrapHole = nullptr;
	FDuelCard* Torrential = nullptr;
	for (FDuelCard& Spell : Defender.Spells)
	{
		if (!Spell.IsValid() || Spell.bFaceUp || Spell.SetTurn >= TurnNumber) continue;
		if (!IsAutomaticTrapTimingAllowed(Spell, EDuelTimingWindow::ResponseToSummon)) continue;
		if (IsName(Spell, TEXT("Trap Hole"))) TrapHole = &Spell;
		else if (IsName(Spell, TEXT("Torrential Tribute"))) Torrential = &Spell;
	}
	const int32 SummonedUid = Summoned.Uid;
	if (TrapHole && bNormalSummon && Summoned.bFaceUp && GetAtk(Summoned) >= 1000)
	{
		FDuelCard* Trap = FindSpellTrap(TrapHole->Uid);
		if (Trap)
		{
			const int32 TrapUid = Trap->Uid;
			if (TryCounterTrap(Other(Summoned.Controller), Summoned.Controller))
			{
				if (FDuelCard* Negated = FindSpellTrap(TrapUid))
				{
					DestroySpellTrap(*Negated, true);
				}
				Log(TEXT("Trap Hole is negated."), TEXT("trap"));
				return;
			}
			if (bWinnerSet) return;
			Trap->bFaceUp = true;
			Log(FString::Printf(TEXT("%s activates Trap Hole!"), *Defender.Name), TEXT("trap"));
			FDuelVisualEvent& TrapEvent = EmitVisual(EDuelVisualEventType::Trap, Other(Summoned.Controller), Trap, 0, TEXT("Trap Hole"));
			TrapEvent.Zone = FindSpellZone(Other(Summoned.Controller), TrapUid);
			if (FDuelCard* Target = FindMonster(SummonedUid))
			{
				DestroyMonster(*Target, false, nullptr, false, TEXT("Trap Hole"));
			}
			if (FDuelCard* StillThere = FindSpellTrap(TrapUid))
			{
				DestroySpellTrap(*StillThere, true);
			}
			return;
		}
	}
	if (Torrential)
	{
		const int32 SummonControllerCount = CountMonsters(Summoned.Controller);
		const int32 DefenderCount = CountMonsters(Other(Summoned.Controller));
		if (SummonControllerCount >= 2 || GetAtk(Summoned) >= 2000 || DefenderCount == 0)
		{
			FDuelCard* Trap = FindSpellTrap(Torrential->Uid);
			if (Trap)
			{
				const int32 TrapUid = Trap->Uid;
				if (TryCounterTrap(Other(Summoned.Controller), Summoned.Controller))
				{
					if (FDuelCard* Negated = FindSpellTrap(TrapUid))
					{
						DestroySpellTrap(*Negated, true);
					}
					Log(TEXT("Torrential Tribute is negated."), TEXT("trap"));
					return;
				}
				if (bWinnerSet) return;
				Trap->bFaceUp = true;
				Log(FString::Printf(TEXT("%s activates Torrential Tribute!"), *Defender.Name), TEXT("trap"));
				FDuelVisualEvent& TrapEvent = EmitVisual(EDuelVisualEventType::Trap, Other(Summoned.Controller), Trap, 0, TEXT("Torrential Tribute"));
				TrapEvent.Zone = FindSpellZone(Other(Summoned.Controller), TrapUid);
				DestroyAllMonsters(TEXT("Torrential Tribute"));
				if (FDuelCard* StillThere = FindSpellTrap(TrapUid))
				{
					DestroySpellTrap(*StillThere, true);
				}
			}
		}
	}
}

// ---------------------------------------------------------------------------
// Destruction, equips, damage
// ---------------------------------------------------------------------------

void FDuelEngine::TriggerFlipEffect(FDuelCard& Card, EDuelOwner Side)
{
	if (bWinnerSet || !Card.IsValid() || !Card.bFaceUp)
	{
		return;
	}
	const FString Name = Card.Data.Name;
	EDuelOwner OpponentSide = Other(Side);
	EmitVisual(EDuelVisualEventType::Effect, Side, &Card, 0, Name);
	if (EffectRuntime)
	{
		EffectRuntime->OnFlip(Card);
		if (bWinnerSet || !FindMonster(Card.Uid))
		{
			return;
		}
	}

	if (Name == TEXT("Man-Eater Bug"))
	{
		if (FDuelCard* Target = ChooseMonster(OpponentSide, [](const FDuelCard&) { return true; }, true))
		{
			Log(TEXT("Man-Eater Bug destroys a monster."), TEXT("effect"));
			DestroyMonster(*Target, false, nullptr, false, TEXT("Man-Eater Bug"));
		}
	}
	else if (Name == TEXT("Penguin Soldier"))
	{
		TArray<int32> Uids;
		for (const FDuelCard& Monster : SideRef(OpponentSide).Monsters)
		{
			if (Monster.IsValid()) Uids.Add(Monster.Uid);
		}
		Uids.Sort([this](int32 A, int32 B)
		{
			const FDuelCard* CA = FindMonster(A);
			const FDuelCard* CB = FindMonster(B);
			return (CA ? GetAtk(*CA) : 0) > (CB ? GetAtk(*CB) : 0);
		});
		for (int32 I = 0; I < Uids.Num() && I < 2; ++I)
		{
			FDuelCard Copy;
			if (RemoveFromZone(Copy, Uids[I]))
			{
				CleanupEquips(Copy);
				Log(FString::Printf(TEXT("Penguin Soldier returns %s to the hand."), *CardName(Copy)), TEXT("effect"));
				MoveToHand(Copy);
			}
		}
	}
	else if (Name == TEXT("Hane-Hane") || Name == TEXT("Gale Lizard"))
	{
		if (FDuelCard* Target = ChooseMonster(OpponentSide, [](const FDuelCard&) { return true; }, true))
		{
			const int32 TargetUid = Target->Uid;
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TargetUid))
			{
				CleanupEquips(Copy);
				Log(FString::Printf(TEXT("%s returns %s to the hand."), *Name, *CardName(Copy)), TEXT("effect"));
				MoveToHand(Copy);
			}
		}
	}
	else if (Name == TEXT("Needle Worm"))
	{
		Log(TEXT("Needle Worm mills the top 5 cards of the opponent's Deck."), TEXT("effect"));
		Mill(OpponentSide, 5);
	}
	else if (Name == TEXT("Magician of Faith"))
	{
		for (FDuelCard& GraveCard : SideRef(Side).Graveyard)
		{
			if (GraveCard.IsSpell())
			{
				FDuelCard Copy;
				const int32 Uid = GraveCard.Uid;
				if (RemoveFromZone(Copy, Uid))
				{
					EmitVisual(EDuelVisualEventType::Search, Side, &Copy, 0, TEXT("MAGICIAN OF FAITH"));
					SideRef(Side).Hand.Add(Copy);
					Log(FString::Printf(TEXT("Magician of Faith returns %s to the hand."), *CardName(Copy)), TEXT("effect"));
				}
				break;
			}
		}
	}
	else if (Name == TEXT("Princess of Tsurugi"))
	{
		int32 Count = 0;
		for (const FDuelCard& Spell : SideRef(OpponentSide).Spells)
		{
			if (Spell.IsValid()) ++Count;
		}
		if (SideRef(OpponentSide).Field.IsValid()) ++Count;
		if (Count > 0)
		{
			InflictDamage(OpponentSide, Count * 500, TEXT("Princess of Tsurugi"));
		}
	}
	else if (Name == TEXT("Lady Assailant of Flames"))
	{
		Log(TEXT("Lady Assailant of Flames banishes the top 3 cards of your Deck."), TEXT("effect"));
		BanishTop(Side, 3);
		InflictDamage(OpponentSide, 800, TEXT("Lady Assailant of Flames"));
	}
	else if (Name == TEXT("Cyber Jar"))
	{
		Log(TEXT("Cyber Jar destroys all monsters and both players pick up 5 cards."), TEXT("effect"));
		DestroyAllMonsters(TEXT("Cyber Jar"));
		for (EDuelOwner PickSide : { EDuelOwner::Player, EDuelOwner::Opponent })
		{
			TArray<FDuelCard> Picked;
			FDuelSide& State = SideRef(PickSide);
			for (int32 I = 0; I < 5 && State.Deck.Num() > 0; ++I)
			{
				Picked.Add(State.Deck.Pop());
			}
			for (const FDuelCard& PickedCard : Picked)
			{
				// Picked cards were popped from the Deck and are not in a zone
				// yet.  Place the local copy directly; RemoveFromZone would fail
				// and silently discard the card.
				bool bSummoned = false;
				if (PickedCard.IsMonster() && CanBeSpecialSummonedByEffect(PickedCard)
					&& GetEffectiveLevel(PickedCard) <= 4 && EmptyMonsterZone(PickSide) != INDEX_NONE)
				{
					bSummoned = PlaceMonster(PickSide, PickedCard, true, EDuelPosition::Attack);
					if (bSummoned)
					{
						if (FDuelCard* Placed = FindMonster(PickedCard.Uid))
						{
							Placed->bSpecialSummoned = true;
						}
						Log(FString::Printf(TEXT("%s Special Summons %s with Cyber Jar."), *State.Name, *CardName(PickedCard)), TEXT("effect"));
						if (FDuelCard* Placed = FindMonster(PickedCard.Uid))
						{
							OnSummon(*Placed, true);
						}
					}
				}
				if (!bSummoned)
				{
					State.Hand.Add(PickedCard);
				}
			}
		}
	}
}

void FDuelEngine::DestroyMonster(FDuelCard& Card, bool bByBattle, FDuelCard* Attacker, bool bWasFaceDown, const FString& Reason)
{
	FDuelCard* Existing = FindMonster(Card.Uid);
	if (!Existing)
	{
		return;
	}
	const int32 Uid = Card.Uid;
	FDuelCard Dead = *Existing;
	if (EffectRuntime && EffectRuntime->ShouldPreventDestruction(Dead, bByBattle, Reason))
	{
		Log(FString::Printf(TEXT("%s is not destroyed (%s)."), *CardName(Dead), *Reason), TEXT("effect"));
		EmitVisual(EDuelVisualEventType::Effect, Dead.Controller, &Dead, 0, TEXT("DESTRUCTION PREVENTED"));
		return;
	}
	const int32 AttackerUid = Attacker ? Attacker->Uid : 0;
	const bool bBanishInstead = EffectRuntime && EffectRuntime->ShouldBanishInsteadOfGrave(Dead);
	const bool bWasFaceUp = Dead.bFaceUp && !bWasFaceDown;
	const EDuelOwner Controller = Dead.Controller;
	const int32 Zone = FindMonsterZone(Controller, Uid);
	if (bByBattle)
	{
		if (Dead.Owner == EDuelOwner::Opponent)
		{
			++ResultStats.MonstersDestroyedByBattle;
		}
		else if (Dead.Owner == EDuelOwner::Player)
		{
			++ResultStats.MonstersLostByBattle;
		}
	}

	if (!RemoveFromZone(Dead, Uid))
	{
		return;
	}
	CleanupEquips(Dead);
	if (bBanishInstead)
	{
		MoveToBanished(Dead);
	}
	else
	{
		MoveToGrave(Dead);
	}
	Log(FString::Printf(TEXT("%s is destroyed%s."), *CardName(Dead),
		Reason.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" (%s)"), *Reason)), TEXT("destroy"));
	FDuelVisualEvent& DestroyEvent = EmitVisual(EDuelVisualEventType::Destroy, Controller, &Dead, 0, Reason);
	DestroyEvent.Zone = Zone;
	if (EffectRuntime)
	{
		EffectRuntime->OnDestroyed(Dead, bByBattle, Reason);
		if (bByBattle && AttackerUid != 0)
		{
			if (FDuelCard* SurvivingAttacker = FindMonster(AttackerUid))
			{
				EffectRuntime->OnBattleDestroyByAttacker(*SurvivingAttacker, Dead);
			}
		}
	}

	// Battle-triggered floaters.
	if (bByBattle)
	{
		if (IsName(Dead, TEXT("UFO Turtle")))
		{
			SpecialSummonAttributeFromDeck(Controller, TEXT("FIRE"), 1500);
		}
		else if (IsName(Dead, TEXT("Mother Grizzly")))
		{
			SpecialSummonAttributeFromDeck(Controller, TEXT("WATER"), 1500);
		}
		else if (IsName(Dead, TEXT("Flying Kamakiri #1")))
		{
			SpecialSummonAttributeFromDeck(Controller, TEXT("WIND"), 1500);
		}
		else if (IsName(Dead, TEXT("Birdface")))
		{
			FDuelCard* Harpie = FindMonsterInDeck(Controller, [this](const FDuelCard& C)
			{
				return C.IsMonster() && IsHarpieLady(C);
			});
			if (Harpie)
			{
				const int32 HarpieUid = Harpie->Uid;
				FDuelCard HarpieCopy;
				if (RemoveFromZone(HarpieCopy, HarpieUid))
				{
					EmitVisual(EDuelVisualEventType::Search, Controller, &HarpieCopy, 0, TEXT("BIRDFACE"));
					SideRef(Controller).Hand.Add(HarpieCopy);
					Log(FString::Printf(TEXT("Birdface adds %s to the hand."), *CardName(HarpieCopy)), TEXT("effect"));
				}
			}
		}
		else if (IsName(Dead, TEXT("T.A.D.P.O.L.E.")))
		{
			AddFromDeckToHand(Controller, TEXT("T.A.D.P.O.L.E."), 3);
		}
		else if (IsName(Dead, TEXT("Silpheed")))
		{
			FDuelSide& Victim = SideRef(Other(Controller));
			if (Victim.Hand.Num() > 0)
			{
				const int32 Index = Random.RandRange(0, Victim.Hand.Num() - 1);
				FDuelCard Discarded = Victim.Hand[Index];
				Victim.Hand.RemoveAt(Index);
				EmitVisual(EDuelVisualEventType::Discard, Other(Controller), &Discarded, 0, TEXT("SILPHEED"));
				MoveToGrave(Discarded);
				Log(FString::Printf(TEXT("Silpheed makes %s discard a card at random."), *Victim.Name), TEXT("effect"));
			}
		}

		// Hero Signal responds to a HERO being destroyed by battle.
		int32 HeroSignalUid = 0;
		for (const FDuelCard& Trap : SideRef(Controller).Spells)
		{
			if (Trap.IsValid() && !Trap.bFaceUp && IsName(Trap, TEXT("Hero Signal")) && Trap.SetTurn < TurnNumber)
			{
				HeroSignalUid = Trap.Uid;
				break;
			}
		}
		if (HeroSignalUid != 0)
		{
			if (FDuelCard* Signal = FindSpellTrap(HeroSignalUid))
			{
				Signal->bFaceUp = true;
				Log(FString::Printf(TEXT("%s activates Hero Signal!"), *SideRef(Controller).Name), TEXT("trap"));
				FDuelVisualEvent& SignalEvent = EmitVisual(EDuelVisualEventType::Trap, Controller, Signal, 0, TEXT("Hero Signal"));
				SignalEvent.Zone = FindSpellZone(Controller, HeroSignalUid);
				SpecialSummonElementalHero(Controller);
				if (FDuelCard* StillThere = FindSpellTrap(HeroSignalUid))
				{
					DestroySpellTrap(*StillThere, true);
				}
			}
		}
	}

	if (IsName(Dead, TEXT("Winged Kuriboh")))
	{
		SideRef(Controller).bBattleDamageZeroThisTurn = true;
		Log(TEXT("Winged Kuriboh reduces this turn's battle damage to 0."), TEXT("effect"));
	}
	if (IsName(Dead, TEXT("Kaiser Glider")))
	{
		if (FDuelCard* Target = ChooseMonster(Other(Controller), [](const FDuelCard&) { return true; }, true))
		{
			const int32 TargetUid = Target->Uid;
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TargetUid))
			{
				CleanupEquips(Copy);
				Log(FString::Printf(TEXT("Kaiser Glider returns %s to the hand."), *CardName(Copy)), TEXT("effect"));
				MoveToHand(Copy);
			}
		}
	}
	if (IsName(Dead, TEXT("Poison Draw Frog")) && bWasFaceUp)
	{
		Log(TEXT("Poison Draw Frog draws a card."), TEXT("effect"));
		Draw(Controller, 1);
	}
	if (IsName(Dead, TEXT("Granadora")))
	{
		InflictDamage(Controller, 2000, TEXT("Granadora"));
	}
	if (IsName(Dead, TEXT("The Thing in the Crater")))
	{
		int32 PyroUid = 0;
		for (const FDuelCard& HandCard : SideRef(Controller).Hand)
		{
			if (HandCard.IsMonster() && HandCard.Data.MonsterType == TEXT("Pyro")
				&& CanBeSpecialSummonedByEffect(HandCard))
			{
				PyroUid = HandCard.Uid;
				break;
			}
		}
		if (PyroUid != 0)
		{
			FDuelCard Copy;
			if (RemoveFromZone(Copy, PyroUid))
			{
				if (PlaceMonster(Controller, Copy, true, EDuelPosition::Attack))
				{
					if (FDuelCard* Placed = FindMonster(PyroUid))
					{
						Placed->bSpecialSummoned = true;
						OnSummon(*Placed, true);
					}
					Log(FString::Printf(TEXT("The Thing in the Crater Special Summons %s."), *CardName(Copy)), TEXT("effect"));
				}
				else
				{
					MoveToGrave(Copy);
				}
			}
		}
	}

	// Backfire burns the opponent when a FIRE monster on its controller's side dies.
	if (Dead.Data.Attribute == TEXT("FIRE"))
	{
		for (const FDuelCard& Spell : SideRef(Controller).Spells)
		{
			if (Spell.IsValid() && Spell.bFaceUp && IsName(Spell, TEXT("Backfire")))
			{
				InflictDamage(Other(Controller), 500, TEXT("Backfire"));
				break;
			}
		}
	}

	CheckWinner();
}

void FDuelEngine::DestroySpellTrap(FDuelCard& Card, bool bByEffect)
{
	if (!Card.IsValid())
	{
		return;
	}
	FDuelCard* Existing = FindSpellTrap(Card.Uid);
	if (!Existing)
	{
		return;
	}
	const FString Name = Existing->Data.Name;
	const int32 Uid = Existing->Uid;
	const EDuelOwner Controller = Existing->Controller;
	const int32 Zone = FindSpellZone(Controller, Uid);
	const int32 TargetUid = Existing->EquippedToUid != 0 ? Existing->EquippedToUid : Existing->TiedToUid;

	FDuelCard Copy;
	if (!RemoveFromZone(Copy, Uid))
	{
		return;
	}
	Copy.Controller = Copy.Owner;
	Copy.bFaceUp = true;
	Copy.Position = EDuelPosition::Attack;
	Copy.EquippedToUid = 0;
	Copy.TiedToUid = 0;

	if (Name == TEXT("Snatch Steal") && TargetUid != 0)
	{
		if (FDuelCard* Target = FindMonster(TargetUid))
		{
			ReturnControl(*Target);
		}
	}
	else if ((Name == TEXT("Premature Burial") || Name == TEXT("Call of the Haunted") || Name == TEXT("Autonomous Action Unit"))
		&& TargetUid != 0)
	{
		if (FDuelCard* Target = FindMonster(TargetUid))
		{
			DestroyMonster(*Target, false, nullptr, false, Name);
		}
	}

	MoveToGrave(Copy);
	Log(FString::Printf(TEXT("%s is destroyed."), *Name), TEXT("destroy"));
	FDuelVisualEvent& DestroyEvent = EmitVisual(EDuelVisualEventType::Destroy, Controller, &Copy, 0, Name);
	DestroyEvent.Zone = Zone;
	if (EffectRuntime)
	{
		EffectRuntime->OnDestroyed(Copy, false, Name);
	}
	if (Name == TEXT("Black Pendant"))
	{
		InflictDamage(Other(Controller), 500, TEXT("Black Pendant"));
	}
}

void FDuelEngine::CleanupEquips(FDuelCard& Card)
{
	TArray<int32> EquipUids;
	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		for (const FDuelCard& Spell : SideRef(Side).Spells)
		{
			if (Spell.IsValid() && (Spell.EquippedToUid == Card.Uid || Spell.TiedToUid == Card.Uid))
			{
				EquipUids.Add(Spell.Uid);
			}
		}
	}
	for (int32 Uid : EquipUids)
	{
		if (FDuelCard* Spell = FindSpellTrap(Uid))
		{
			DestroySpellTrap(*Spell, true);
		}
	}
}

void FDuelEngine::DestroyAllMonsters(const FString& Reason)
{
	TArray<int32> Uids;
	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		for (const FDuelCard& Monster : SideRef(Side).Monsters)
		{
			if (Monster.IsValid()) Uids.Add(Monster.Uid);
		}
	}
	for (int32 Uid : Uids)
	{
		if (FDuelCard* Monster = FindMonster(Uid))
		{
			DestroyMonster(*Monster, false, nullptr, false, Reason);
		}
	}
}

void FDuelEngine::DestroyAllSpellTraps(bool bByEffect)
{
	TArray<int32> Uids;
	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		for (const FDuelCard& Spell : SideRef(Side).Spells)
		{
			if (Spell.IsValid()) Uids.Add(Spell.Uid);
		}
		if (SideRef(Side).Field.IsValid()) Uids.Add(SideRef(Side).Field.Uid);
	}
	for (int32 Uid : Uids)
	{
		if (FDuelCard* Spell = FindSpellTrap(Uid))
		{
			DestroySpellTrap(*Spell, bByEffect);
		}
	}
}

void FDuelEngine::ReturnSpellTrapToHand(FDuelCard& Spell)
{
	if (!Spell.IsValid())
	{
		return;
	}
	FDuelCard* Existing = FindSpellTrap(Spell.Uid);
	if (!Existing)
	{
		return;
	}
	const FString Name = Existing->Data.Name;
	const int32 TargetUid = Existing->EquippedToUid != 0 ? Existing->EquippedToUid : Existing->TiedToUid;
	FDuelCard Copy;
	if (!RemoveFromZone(Copy, Existing->Uid))
	{
		return;
	}
	if (Name == TEXT("Snatch Steal") && TargetUid != 0)
	{
		if (FDuelCard* Target = FindMonster(TargetUid)) ReturnControl(*Target);
	}
	else if ((Name == TEXT("Premature Burial") || Name == TEXT("Call of the Haunted") || Name == TEXT("Autonomous Action Unit"))
		&& TargetUid != 0)
	{
		if (FDuelCard* Target = FindMonster(TargetUid))
		{
			DestroyMonster(*Target, false, nullptr, false, Name);
		}
	}
	MoveToHand(Copy);
}

void FDuelEngine::ReturnAllSpellTrapsToHand()
{
	TArray<int32> Uids;
	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		for (const FDuelCard& Spell : SideRef(Side).Spells)
		{
			if (Spell.IsValid()) Uids.Add(Spell.Uid);
		}
		if (SideRef(Side).Field.IsValid()) Uids.Add(SideRef(Side).Field.Uid);
	}
	for (int32 Uid : Uids)
	{
		if (FDuelCard* Spell = FindSpellTrap(Uid))
		{
			ReturnSpellTrapToHand(*Spell);
		}
	}
}

void FDuelEngine::AttachEquip(FDuelCard& Equip, FDuelCard& Target)
{
	Equip.EquippedToUid = Target.Uid;
	if (EffectRuntime)
	{
		EffectRuntime->RecomputeContinuous();
	}
}

void FDuelEngine::ReturnControl(FDuelCard& Card)
{
	if (Card.Controller == Card.Owner)
	{
		return;
	}
	FDuelCard Copy;
	if (!RemoveFromZone(Copy, Card.Uid))
	{
		return;
	}
	Copy.Controller = Copy.Owner;
	if (PlaceMonster(Copy.Owner, Copy, Copy.bFaceUp, Copy.Position))
	{
		Log(FString::Printf(TEXT("%s returns to %s's control."), *CardName(Copy), *SideRef(Copy.Owner).Name), TEXT("effect"));
	}
	else
	{
		MoveToGrave(Copy);
	}
}

void FDuelEngine::InflictDamage(EDuelOwner Side, int32 Amount, const FString& Reason)
{
	if (Amount <= 0 || bWinnerSet)
	{
		return;
	}
	if (!bApplyingBattleDamage && Side == EDuelOwner::Opponent)
	{
		ResultStats.EffectDamageDealt += Amount;
	}
	FDuelSide& State = SideRef(Side);
	// Life Points are a count, not a signed total: overkill damage clamps at 0
	// so every consumer (HUD, result stats, save) observes a legal value.
	State.LP = FMath::Max(0, State.LP - Amount);
	Log(FString::Printf(TEXT("%s %s %d damage%s."), *State.Name,
		State.Owner == EDuelOwner::Player ? TEXT("take") : TEXT("takes"), Amount,
		Reason.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" (%s)"), *Reason)), TEXT("damage"));
	EmitVisual(EDuelVisualEventType::Damage, Side, nullptr, Amount, Reason);
	CheckWinner();
}

void FDuelEngine::InflictBattleDamage(EDuelOwner Side, int32 Amount, const FString& Reason)
{
	if (Amount <= 0 || bWinnerSet)
	{
		return;
	}
	if (EffectRuntime && EffectRuntime->ShouldPreventBattleDamage(Side))
	{
		Log(FString::Printf(TEXT("%s's battle damage is prevented."), *SideRef(Side).Name), TEXT("effect"));
		return;
	}
	if (SideRef(Side).bBattleDamageZeroThisTurn)
	{
		Log(FString::Printf(TEXT("%s's battle damage becomes 0."), *SideRef(Side).Name), TEXT("effect"));
		return;
	}
	if (Side == EDuelOwner::Opponent)
	{
		ResultStats.BattleDamageDealt += Amount;
	}
	else if (Side == EDuelOwner::Player)
	{
		ResultStats.BattleDamageTaken += Amount;
	}
	bApplyingBattleDamage = true;
	InflictDamage(Side, Amount, Reason);
	bApplyingBattleDamage = false;
}

void FDuelEngine::GainLp(EDuelOwner Side, int32 Amount, const FString& Reason)
{
	if (Amount <= 0 || bWinnerSet) return;
	SideRef(Side).LP += Amount;
	Log(FString::Printf(TEXT("%s gains %d LP%s."), *SideRef(Side).Name, Amount,
		Reason.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" (%s)"), *Reason)), TEXT("heal"));
	EmitVisual(EDuelVisualEventType::Heal, Side, nullptr, Amount, Reason);
}

void FDuelEngine::PayLp(EDuelOwner Side, int32 Amount, const FString& Reason)
{
	if (Amount <= 0 || bWinnerSet) return;
	SideRef(Side).LP = FMath::Max(0, SideRef(Side).LP - Amount);
	Log(FString::Printf(TEXT("%s pays %d LP%s."), *SideRef(Side).Name, Amount,
		Reason.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" (%s)"), *Reason)), TEXT("lp"));
	EmitVisual(EDuelVisualEventType::Cost, Side, nullptr, Amount, Reason.IsEmpty() ? TEXT("COST") : Reason);
	CheckWinner();
}

bool FDuelEngine::IsContinuousTrap(const FString& Name) const
{
	return IsContinuousTrapName(Name);
}

bool FDuelEngine::IsFieldSpellCard(const FDuelCard& Card) const
{
	return Card.Data.Subtype == TEXT("Field") || IsFieldSpellName(Card.Data.Name);
}

bool FDuelEngine::IsPersistentSpellTrap(const FDuelCard& Card) const
{
	if (!Card.IsSpell() && !Card.IsTrap())
	{
		return false;
	}
	if (EffectRuntime && EffectRuntime->ShouldStayOnFieldAfterActivation(Card))
	{
		return true;
	}
	const FString& Subtype = Card.Data.Subtype;
	return Subtype == TEXT("Equip")
		|| Subtype == TEXT("Field")
		|| Subtype == TEXT("Continuous")
		|| IsFieldSpellName(Card.Data.Name)
		|| IsEquipName(Card.Data.Name)
		|| IsContinuousTrapName(Card.Data.Name);
}

bool FDuelEngine::IsManualTrapCard(const FDuelCard& Card) const
{
	if (!Card.IsTrap())
	{
		return false;
	}
	if (IsManualTrapName(Card.Data.Name))
	{
		return true;
	}
	if (EffectRuntime)
	{
		if (Card.Data.Subtype == TEXT("Continuous")
			&& EffectRuntime->HasScriptTrigger(Card.Data.Id, EDEffectTrigger::OnActivate))
		{
			return true;
		}
		return EffectRuntime->HasScriptTrigger(Card.Data.Id, EDEffectTrigger::Manual)
			|| EffectRuntime->HasScriptTrigger(Card.Data.Id, EDEffectTrigger::Continuous);
	}
	return false;
}

// ---------------------------------------------------------------------------
// Summon helpers used by card effects
// ---------------------------------------------------------------------------

void FDuelEngine::SpecialSummonAttributeFromDeck(EDuelOwner Side, const FString& Attribute, int32 MaxAtk)
{
	if (EmptyMonsterZone(Side) == INDEX_NONE)
	{
		return;
	}
	FDuelCard* Candidate = FindMonsterInDeck(Side, [&Attribute, MaxAtk, this](const FDuelCard& Card)
	{
		return Card.Data.Attribute == Attribute && Card.Data.Atk <= MaxAtk
			&& CanBeSpecialSummonedByEffect(Card);
	});
	if (!Candidate)
	{
		return;
	}
	// Prefer the strongest legal target rather than the first one in deck order.
	for (FDuelCard& Card : SideRef(Side).Deck)
	{
		if (Card.IsMonster() && Card.Data.Attribute == Attribute && Card.Data.Atk <= MaxAtk
			&& CanBeSpecialSummonedByEffect(Card) && Card.Data.Atk > Candidate->Data.Atk)
		{
			Candidate = &Card;
		}
	}
	const int32 Uid = Candidate->Uid;
	FDuelCard Copy;
	if (!RemoveFromZone(Copy, Uid))
	{
		return;
	}
	if (!PlaceMonster(Side, Copy, true, EDuelPosition::Attack))
	{
		MoveToGrave(Copy);
		return;
	}
	if (FDuelCard* Placed = FindMonster(Uid))
	{
		Placed->bSpecialSummoned = true;
		Log(FString::Printf(TEXT("%s Special Summons %s from the Deck."), *SideRef(Side).Name, *CardName(*Placed)), TEXT("effect"));
		OnSummon(*Placed, true);
	}
}

void FDuelEngine::AddFromDeckToHand(EDuelOwner Side, const FString& Name, int32 Limit)
{
	FDuelSide& State = SideRef(Side);
	for (int32 I = 0; I < Limit; ++I)
	{
		int32 FoundIndex = INDEX_NONE;
		for (int32 J = 0; J < State.Deck.Num(); ++J)
		{
			if (State.Deck[J].Data.Name == Name)
			{
				FoundIndex = J;
				break;
			}
		}
		if (FoundIndex == INDEX_NONE) return;
		FDuelCard Card = State.Deck[FoundIndex];
		State.Deck.RemoveAt(FoundIndex);
		EmitVisual(EDuelVisualEventType::Search, Side, &Card, 0, Name);
		State.Hand.Add(Card);
		Log(FString::Printf(TEXT("%s adds %s from the Deck to the hand."), *State.Name, *Name), TEXT("effect"));
	}
}

void FDuelEngine::SpecialSummonElementalHero(EDuelOwner Side)
{
	if (EmptyMonsterZone(Side) == INDEX_NONE) return;
	FDuelCard* Candidate = nullptr;
	for (FDuelCard& Card : SideRef(Side).Deck)
	{
		if (Card.IsMonster() && IsElementalHero(Card) && !Card.IsFusion() && GetEffectiveLevel(Card) <= 4)
		{
			Candidate = &Card;
			break;
		}
	}
	if (!Candidate)
	{
		for (FDuelCard& Card : SideRef(Side).Hand)
		{
			if (Card.IsMonster() && IsElementalHero(Card) && !Card.IsFusion() && GetEffectiveLevel(Card) <= 4)
			{
				Candidate = &Card;
				break;
			}
		}
	}
	if (!Candidate) return;
	const int32 Uid = Candidate->Uid;
	FDuelCard Copy;
	if (!RemoveFromZone(Copy, Uid)) return;
	if (!PlaceMonster(Side, Copy, true, EDuelPosition::Attack))
	{
		MoveToGrave(Copy);
		return;
	}
	if (FDuelCard* Placed = FindMonster(Uid))
	{
		Placed->bSpecialSummoned = true;
		Log(FString::Printf(TEXT("%s Special Summons %s."), *SideRef(Side).Name, *CardName(*Placed)), TEXT("trap"));
		OnSummon(*Placed, true);
	}
}

void FDuelEngine::SpecialSummonHarpieSisters(EDuelOwner Side)
{
	if (EmptyMonsterZone(Side) == INDEX_NONE) return;
	FDuelCard* Candidate = FindMonsterInHand(Side, TEXT("Harpie Lady Sisters"));
	bool bFromDeck = false;
	if (!Candidate)
	{
		Candidate = FindCardInDeck(Side, TEXT("Harpie Lady Sisters"));
		bFromDeck = Candidate != nullptr;
	}
	if (!Candidate)
	{
		Candidate = FindMonsterInHand(Side, TEXT("Harpie Lady"));
	}
	if (!Candidate)
	{
		Candidate = FindCardInDeck(Side, TEXT("Harpie Lady"));
		bFromDeck = Candidate != nullptr;
	}
	if (!Candidate)
	{
		Candidate = FindMonsterInHand(Side, TEXT("Cyber Harpie Lady"));
	}
	if (!Candidate)
	{
		Candidate = FindCardInDeck(Side, TEXT("Cyber Harpie Lady"));
		bFromDeck = Candidate != nullptr;
	}
	if (!Candidate) return;
	const int32 Uid = Candidate->Uid;
	const FString SummonedName = Candidate->Data.Name;
	FDuelCard Copy;
	if (!RemoveFromZone(Copy, Uid)) return;
	if (!PlaceMonster(Side, Copy, true, EDuelPosition::Attack))
	{
		MoveToGrave(Copy);
		return;
	}
	if (FDuelCard* Placed = FindMonster(Uid))
	{
		Placed->bSpecialSummoned = true;
		Log(FString::Printf(TEXT("%s Special Summons %s from the %s."), *SideRef(Side).Name,
			*SummonedName, bFromDeck ? TEXT("Deck") : TEXT("hand")), TEXT("effect"));
		OnSummon(*Placed, true);
	}
}

// ---------------------------------------------------------------------------
// Spell / Trap resolution
// ---------------------------------------------------------------------------

bool FDuelEngine::HasEquipTarget(EDuelOwner Side, const FString& Name) const
{
	for (const FDuelCard& Card : SideRef(Side).Monsters)
	{
		if (!Card.IsValid() || !Card.bFaceUp) continue;
		if (Name == TEXT("Fusion Weapon") && (!Card.IsFusion() || Card.Data.Level > 6)) continue;
		if ((Name == TEXT("Burning Spear") || Name == TEXT("Salamandra")) && Card.Data.Attribute != TEXT("FIRE")) continue;
		if (Name == TEXT("Gust Fan") && Card.Data.Attribute != TEXT("WIND")) continue;
		if (Name == TEXT("Steel Shell") && Card.Data.Attribute != TEXT("WATER")) continue;
		if (Name == TEXT("Power of Kaishin") && Card.Data.MonsterType != TEXT("Aqua")) continue;
		if (Name == TEXT("Cyber Shield") && !IsHarpieLady(Card) && !IsName(Card, TEXT("Harpie Lady Sisters"))) continue;
		return true;
	}
	return false;
}

FDuelCard* FDuelEngine::ChooseEquipTarget(EDuelOwner Side, const FString& Name)
{
	FDuelCard* Best = nullptr;
	int32 BestAtk = -1;
	for (FDuelCard& Card : SideRef(Side).Monsters)
	{
		if (!Card.IsValid() || !Card.bFaceUp) continue;
		if (Name == TEXT("Fusion Weapon") && (!Card.IsFusion() || Card.Data.Level > 6)) continue;
		if ((Name == TEXT("Burning Spear") || Name == TEXT("Salamandra")) && Card.Data.Attribute != TEXT("FIRE")) continue;
		if (Name == TEXT("Gust Fan") && Card.Data.Attribute != TEXT("WIND")) continue;
		if (Name == TEXT("Steel Shell") && Card.Data.Attribute != TEXT("WATER")) continue;
		if (Name == TEXT("Power of Kaishin") && Card.Data.MonsterType != TEXT("Aqua")) continue;
		if (Name == TEXT("Cyber Shield") && !IsHarpieLady(Card) && !IsName(Card, TEXT("Harpie Lady Sisters"))) continue;
		const int32 Atk = GetAtk(Card);
		if (Atk > BestAtk)
		{
			Best = &Card;
			BestAtk = Atk;
		}
	}
	return Best;
}

bool FDuelEngine::CanActivateSpellCard(const FDuelCard& Card)
{
	if (!Card.IsSpell() || bWinnerSet || !IsMainPhase() || Card.Controller != ActiveSide)
	{
		return false;
	}
	if (bEnforceActivationTiming)
	{
		FString Reason;
		if (!IsActivationLegal(Card, GetCurrentTimingWindow(), &Reason))
		{
			return false;
		}
	}
	const FDuelSide& State = SideRef(Card.Controller);
	const bool bInHand = State.Hand.ContainsByPredicate([&Card](const FDuelCard& C) { return C.Uid == Card.Uid; });
	if (!bInHand)
	{
		return false;
	}
	const FString& Name = Card.Data.Name;
	const bool bFieldSpell = IsFieldSpellCard(Card);
	if (!bFieldSpell && EmptySpellZone(Card.Controller) == INDEX_NONE)
	{
		return false;
	}

	const EDuelOwner Side = Card.Controller;
	const EDuelOwner Opp = Other(Side);

	if (Name == TEXT("Polymerization") || Name == TEXT("Miracle Fusion") || Name == TEXT("Dragon's Mirror"))
	{
		return FindFusionOption(Side, Name, nullptr, nullptr);
	}
	if (Name == TEXT("Fissure"))
	{
		return ChooseMonster(Opp, [](const FDuelCard& C) { return C.bFaceUp; }, false) != nullptr;
	}
	if (Name == TEXT("Tribute to the Doomed"))
	{
		return State.Hand.Num() > 1 && ChooseMonster(Opp, [](const FDuelCard&) { return true; }, true) != nullptr;
	}
	if (Name == TEXT("Book of Moon"))
	{
		return ChooseMonster(Opp, [](const FDuelCard& C) { return C.bFaceUp; }, true) != nullptr;
	}
	if (Name == TEXT("Monster Reincarnation"))
	{
		return State.Hand.Num() > 1
			&& State.Graveyard.ContainsByPredicate([](const FDuelCard& C) { return C.IsMonster(); });
	}
	if (Name == TEXT("Premature Burial"))
	{
		return State.LP > 800 && EmptyMonsterZone(Side) != INDEX_NONE
			&& State.Graveyard.ContainsByPredicate([this](const FDuelCard& C)
			{
				return C.IsMonster() && CanBeSpecialSummonedByEffect(C);
			});
	}
	if (Name == TEXT("Snatch Steal"))
	{
		return EmptyMonsterZone(Side) != INDEX_NONE && EmptySpellZone(Side) != INDEX_NONE
			&& ChooseMonster(Opp, [](const FDuelCard& C) { return C.bFaceUp; }, true) != nullptr;
	}
	if (Name == TEXT("Autonomous Action Unit"))
	{
		return State.LP >= 1500 && EmptyMonsterZone(Side) != INDEX_NONE && EmptySpellZone(Side) != INDEX_NONE
			&& SideRef(Opp).Graveyard.ContainsByPredicate([this](const FDuelCard& C)
			{
				return C.IsMonster() && CanBeSpecialSummonedByEffect(C);
			});
	}
	if (Name == TEXT("Salvage"))
	{
		int32 Targets = 0;
		for (const FDuelCard& GraveCard : State.Graveyard)
		{
			if (GraveCard.IsMonster() && GraveCard.Data.Attribute == TEXT("WATER") && GraveCard.Data.Atk <= 1500)
			{
				++Targets;
			}
		}
		return Targets >= 2;
	}
	if (Name == TEXT("Heavy Storm") || Name == TEXT("Giant Trunade"))
	{
		for (EDuelOwner CheckSide : { EDuelOwner::Player, EDuelOwner::Opponent })
		{
			if (CountSpells(CheckSide) > 0) return true;
		}
		return false;
	}
	if (Name == TEXT("Nobleman of Extermination"))
	{
		for (const FDuelCard& Spell : SideRef(Opp).Spells)
		{
			if (Spell.IsValid() && !Spell.bFaceUp) return true;
		}
		return false;
	}
	if (Name == TEXT("Special Hurricane"))
	{
		return State.Hand.Num() > 1;
	}
	if (Name == TEXT("Transcendent Wings"))
	{
		const bool bLv10InHand = FindMonsterInHand(Side, TEXT("Winged Kuriboh LV10")) != nullptr;
		int32 HandCostCards = 0;
		for (const FDuelCard& HandCard : State.Hand)
		{
			if (!bLv10InHand || !IsName(HandCard, TEXT("Winged Kuriboh LV10"))) ++HandCostCards;
		}
		// Tributing Winged Kuriboh frees its own Monster Zone, so a full board is
		// still a legal activation when Kuriboh is the tribute.
		return HandCostCards >= 2
			&& FindMonsterByName(Side, TEXT("Winged Kuriboh")) != nullptr
			&& (bLv10InHand || FindCardInDeck(Side, TEXT("Winged Kuriboh LV10")) != nullptr);
	}
	if (Name == TEXT("Elegant Egotist"))
	{
		bool bHarpieOnField = false;
		for (const FDuelCard& Monster : State.Monsters)
		{
			if (Monster.IsValid() && Monster.bFaceUp && IsHarpieLady(Monster)) bHarpieOnField = true;
		}
		if (!bHarpieOnField || EmptyMonsterZone(Side) == INDEX_NONE)
		{
			return false;
		}
		for (const FString& HarpieName : { FString(TEXT("Harpie Lady Sisters")),
			FString(TEXT("Harpie Lady")), FString(TEXT("Cyber Harpie Lady")) })
		{
			if (FindMonsterInHand(Side, HarpieName) || FindCardInDeck(Side, HarpieName))
			{
				return true;
			}
		}
		return false;
	}
	if (Name == TEXT("Incandescent Ordeal"))
	{
		if (!FindMonsterInHand(Side, TEXT("Legendary Flame Lord")) || EmptyMonsterZone(Side) == INDEX_NONE)
		{
			return false;
		}
		int32 Levels = 0;
		for (const FDuelCard& HandCard : State.Hand)
		{
			if (HandCard.IsMonster() && !IsName(HandCard, TEXT("Legendary Flame Lord"))) Levels += GetEffectiveLevel(HandCard);
		}
		for (const FDuelCard& FieldCard : State.Monsters)
		{
			if (FieldCard.IsValid()) Levels += GetEffectiveLevel(FieldCard);
		}
		return Levels >= 7;
	}
	if (Name == TEXT("Pot of Greed") || Name == TEXT("Graceful Charity") || Name == TEXT("Upstart Goblin"))
	{
		return State.Deck.Num() > 0;
	}
	if (Name == TEXT("Card Destruction"))
	{
		return true;
	}
	if (Name == TEXT("Sparks") || Name == TEXT("Token Thanksgiving"))
	{
		return true;
	}
	if (IsEquipName(Name))
	{
		return HasEquipTarget(Side, Name);
	}
	if (bFieldSpell)
	{
		return true;
	}
	return true;
}

void FDuelEngine::ResolveSpell(FDuelCard& Card)
{
	const EDuelOwner Side = Card.Controller;
	const EDuelOwner Opp = Other(Side);
	FDuelSide& State = SideRef(Side);
	const FString Name = Card.Data.Name;

	auto DiscardLowest = [this, &State, Side](int32 Count)
	{
		for (int32 I = 0; I < Count && State.Hand.Num() > 0; ++I)
		{
			int32 BestIndex = 0;
			int32 BestValue = TNumericLimits<int32>::Max();
			for (int32 J = 0; J < State.Hand.Num(); ++J)
			{
				const int32 Value = AiCardValue(State.Hand[J]);
				if (Value < BestValue)
				{
					BestValue = Value;
					BestIndex = J;
				}
			}
			FDuelCard Discarded = State.Hand[BestIndex];
			State.Hand.RemoveAt(BestIndex);
			EmitVisual(EDuelVisualEventType::Discard, Side, &Discarded, 0, TEXT("DISCARD"));
			MoveToGrave(Discarded);
			Log(FString::Printf(TEXT("%s discards %s."), *State.Name, *CardName(Discarded)), TEXT("discard"));
		}
	};

	if (Name == TEXT("Pot of Greed"))
	{
		Draw(Side, 2);
	}
	else if (Name == TEXT("Graceful Charity"))
	{
		Draw(Side, 3);
		if (!bWinnerSet) DiscardLowest(2);
	}
	else if (Name == TEXT("Upstart Goblin"))
	{
		Draw(Side, 1);
		if (!bWinnerSet) GainLp(Opp, 1000, TEXT("Upstart Goblin"));
	}
	else if (Name == TEXT("Card Destruction"))
	{
		for (EDuelOwner DestroySide : { EDuelOwner::Player, EDuelOwner::Opponent })
		{
			FDuelSide& HandSide = SideRef(DestroySide);
			TArray<FDuelCard> HandCopy = HandSide.Hand;
			HandSide.Hand.Reset();
			for (const FDuelCard& HandCard : HandCopy)
			{
				EmitVisual(EDuelVisualEventType::Discard, DestroySide, &HandCard, 0, TEXT("CARD DESTRUCTION"));
				MoveToGrave(HandCard);
			}
			Log(FString::Printf(TEXT("%s discards %d cards."), *HandSide.Name, HandCopy.Num()), TEXT("discard"));
			if (HandCopy.Num() > 0) Draw(DestroySide, HandCopy.Num());
			if (bWinnerSet) return;
		}
	}
	else if (Name == TEXT("Heavy Storm"))
	{
		Log(TEXT("Heavy Storm destroys all Spell and Trap Cards."), TEXT("spell"));
		DestroyAllSpellTraps(true);
		return;
	}
	else if (Name == TEXT("Giant Trunade"))
	{
		Log(TEXT("Giant Trunade returns all Spell and Trap Cards to the hand."), TEXT("spell"));
		ReturnAllSpellTrapsToHand();
		return;
	}
	else if (Name == TEXT("Fissure"))
	{
		if (FDuelCard* Target = ChooseMonster(Opp, [](const FDuelCard& C) { return C.bFaceUp; }, false))
		{
			Log(FString::Printf(TEXT("Fissure destroys %s."), *CardName(*Target)), TEXT("spell"));
			DestroyMonster(*Target, false, nullptr, false, TEXT("Fissure"));
		}
	}
	else if (Name == TEXT("Tribute to the Doomed"))
	{
		DiscardLowest(1);
		if (FDuelCard* Target = ChooseMonster(Opp, [](const FDuelCard&) { return true; }, true))
		{
			Log(FString::Printf(TEXT("Tribute to the Doomed destroys %s."), *CardName(*Target)), TEXT("spell"));
			DestroyMonster(*Target, false, nullptr, false, TEXT("Tribute to the Doomed"));
		}
	}
	else if (Name == TEXT("Book of Moon"))
	{
		if (FDuelCard* Target = ChooseMonster(Opp, [](const FDuelCard& C) { return C.bFaceUp; }, true))
		{
			Target->bFaceUp = false;
			Target->Position = EDuelPosition::Defense;
			Target->SetTurn = TurnNumber;
			Log(FString::Printf(TEXT("Book of Moon sets %s face-down."), *CardName(*Target)), TEXT("spell"));
			EmitVisual(EDuelVisualEventType::Position, Opp, Target, 0, TEXT("BOOK OF MOON: SET"));
		}
	}
	else if (Name == TEXT("Premature Burial"))
	{
		PayLp(Side, 800, TEXT("Premature Burial"));
		if (bWinnerSet) return;
		FDuelCard* Target = nullptr;
		for (FDuelCard& GraveCard : State.Graveyard)
		{
			if (GraveCard.IsMonster() && CanBeSpecialSummonedByEffect(GraveCard)
				&& (!Target || GraveCard.Data.Atk > Target->Data.Atk)) Target = &GraveCard;
		}
		if (Target)
		{
			const int32 TargetUid = Target->Uid;
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TargetUid))
			{
				if (PlaceMonster(Side, Copy, true, EDuelPosition::Attack))
				{
					Copy.bSpecialSummoned = true;
					if (FDuelCard* Placed = FindMonster(TargetUid))
					{
						Placed->bSpecialSummoned = true;
						Card.EquippedToUid = TargetUid;
						Card.TiedToUid = TargetUid;
						Log(FString::Printf(TEXT("Premature Burial revives %s."), *CardName(*Placed)), TEXT("spell"));
						OnSummon(*Placed, true);
					}
				}
				else
				{
					MoveToGrave(Copy);
				}
			}
		}
	}
	else if (Name == TEXT("Snatch Steal"))
	{
		if (FDuelCard* Target = ChooseMonster(Opp, [](const FDuelCard& C) { return C.bFaceUp; }, true))
		{
			const int32 TargetUid = Target->Uid;
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TargetUid))
			{
				CleanupEquips(Copy);
				if (PlaceMonster(Side, Copy, true, Copy.Position))
				{
					Card.EquippedToUid = TargetUid;
					Log(FString::Printf(TEXT("Snatch Steal takes control of %s."), *CardName(Copy)), TEXT("spell"));
				}
				else
				{
					MoveToGrave(Copy);
				}
			}
		}
	}
	else if (Name == TEXT("Autonomous Action Unit"))
	{
		PayLp(Side, 1500, TEXT("Autonomous Action Unit"));
		if (bWinnerSet) return;
		FDuelCard* Target = nullptr;
		for (FDuelCard& GraveCard : SideRef(Opp).Graveyard)
		{
			if (GraveCard.IsMonster() && CanBeSpecialSummonedByEffect(GraveCard)
				&& (!Target || GraveCard.Data.Atk > Target->Data.Atk)) Target = &GraveCard;
		}
		if (Target)
		{
			const int32 TargetUid = Target->Uid;
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TargetUid))
			{
				if (PlaceMonster(Side, Copy, true, EDuelPosition::Attack))
				{
					if (FDuelCard* Placed = FindMonster(TargetUid))
					{
						Placed->bSpecialSummoned = true;
						Card.EquippedToUid = TargetUid;
						Card.TiedToUid = TargetUid;
						Log(FString::Printf(TEXT("Autonomous Action Unit revives %s."), *CardName(*Placed)), TEXT("spell"));
						OnSummon(*Placed, true);
					}
				}
				else
				{
					MoveToGrave(Copy);
				}
			}
		}
	}
	else if (Name == TEXT("Monster Reincarnation"))
	{
		DiscardLowest(1);
		FDuelCard* Target = nullptr;
		for (FDuelCard& GraveCard : State.Graveyard)
		{
			if (GraveCard.IsMonster() && (!Target || GraveCard.Data.Atk > Target->Data.Atk)) Target = &GraveCard;
		}
		if (Target)
		{
			const int32 TargetUid = Target->Uid;
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TargetUid))
			{
				EmitVisual(EDuelVisualEventType::Search, Side, &Copy, 0, TEXT("MONSTER REINCARNATION"));
				State.Hand.Add(Copy);
				Log(FString::Printf(TEXT("Monster Reincarnation returns %s to the hand."), *CardName(Copy)), TEXT("spell"));
			}
		}
	}
	else if (Name == TEXT("Salvage"))
	{
		TArray<int32> FoundUids;
		for (const FDuelCard& GraveCard : State.Graveyard)
		{
			if (FoundUids.Num() >= 2) break;
			if (GraveCard.IsMonster() && GraveCard.Data.Attribute == TEXT("WATER") && GraveCard.Data.Atk <= 1500)
			{
				FoundUids.Add(GraveCard.Uid);
			}
		}
		for (int32 FoundUid : FoundUids)
		{
			FDuelCard Copy;
			if (RemoveFromZone(Copy, FoundUid))
			{
				EmitVisual(EDuelVisualEventType::Search, Side, &Copy, 0, TEXT("SALVAGE"));
				State.Hand.Add(Copy);
				Log(FString::Printf(TEXT("Salvage adds %s to the hand."), *CardName(Copy)), TEXT("spell"));
			}
		}
	}
	else if (Name == TEXT("Nobleman of Extermination"))
	{
		int32 TargetUid = 0;
		bool bTargetWasTrap = false;
		FString TargetName;
		for (const FDuelCard& Spell : SideRef(Opp).Spells)
		{
			if (Spell.IsValid() && !Spell.bFaceUp)
			{
				TargetUid = Spell.Uid;
				bTargetWasTrap = Spell.IsTrap();
				TargetName = Spell.Data.Name;
				break;
			}
		}
		if (TargetUid != 0)
		{
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TargetUid))
			{
				MoveToBanished(Copy);
				Log(FString::Printf(TEXT("Nobleman of Extermination banishes %s."), *TargetName), TEXT("spell"));
				if (bTargetWasTrap)
				{
					for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
					{
						TArray<FDuelCard> Removed;
						for (int32 I = SideRef(Owner).Deck.Num() - 1; I >= 0; --I)
						{
							if (SideRef(Owner).Deck[I].IsTrap() && SideRef(Owner).Deck[I].Data.Name == TargetName)
							{
								Removed.Add(SideRef(Owner).Deck[I]);
								SideRef(Owner).Deck.RemoveAt(I);
							}
						}
						for (const FDuelCard& RemovedCard : Removed) MoveToBanished(RemovedCard);
					}
				}
			}
		}
	}
	else if (Name == TEXT("Special Hurricane"))
	{
		DiscardLowest(1);
		TArray<int32> Uids;
		for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
		{
			for (const FDuelCard& Monster : SideRef(Owner).Monsters)
			{
				if (Monster.IsValid() && Monster.bSpecialSummoned) Uids.Add(Monster.Uid);
			}
		}
		for (int32 Uid : Uids)
		{
			if (FDuelCard* Monster = FindMonster(Uid)) DestroyMonster(*Monster, false, nullptr, false, TEXT("Special Hurricane"));
		}
	}
	else if (Name == TEXT("Transcendent Wings"))
	{
		// Send exactly two other cards; Winged Kuriboh LV10 must stay available
		// to be Special Summoned by this effect.
		for (int32 DiscardIndex = 0; DiscardIndex < 2; ++DiscardIndex)
		{
			int32 BestIndex = INDEX_NONE;
			int32 BestValue = TNumericLimits<int32>::Max();
			for (int32 I = 0; I < State.Hand.Num(); ++I)
			{
				if (IsName(State.Hand[I], TEXT("Winged Kuriboh LV10"))) continue;
				const int32 Value = AiCardValue(State.Hand[I]);
				if (Value < BestValue)
				{
					BestValue = Value;
					BestIndex = I;
				}
			}
			if (BestIndex == INDEX_NONE) break;
			FDuelCard CostCard = State.Hand[BestIndex];
			State.Hand.RemoveAt(BestIndex);
			EmitVisual(EDuelVisualEventType::Discard, Side, &CostCard, 0, TEXT("TRANSCENDENT WINGS"));
			MoveToGrave(CostCard);
			Log(FString::Printf(TEXT("%s discards %s for Transcendent Wings."), *State.Name, *CardName(CostCard)), TEXT("discard"));
		}
		FDuelCard* Kuriboh = FindMonsterByName(Side, TEXT("Winged Kuriboh"));
		if (Kuriboh && Kuriboh->bFaceUp)
		{
			FDuelCard* Lv10 = FindMonsterInHand(Side, TEXT("Winged Kuriboh LV10"));
			bool bFromDeck = false;
			if (!Lv10)
			{
				Lv10 = FindCardInDeck(Side, TEXT("Winged Kuriboh LV10"));
				bFromDeck = true;
			}
			const int32 KuribohUid = Kuriboh->Uid;
			const int32 Lv10Uid = Lv10 ? Lv10->Uid : 0;
			FDuelCard TributeCopy;
			if (RemoveFromZone(TributeCopy, KuribohUid))
			{
				CleanupEquips(TributeCopy);
				MoveToGrave(TributeCopy);
			}
			FDuelCard SummonCopy;
			if (Lv10Uid != 0 && RemoveFromZone(SummonCopy, Lv10Uid))
			{
				if (PlaceMonster(Side, SummonCopy, true, EDuelPosition::Attack))
				{
					if (FDuelCard* Placed = FindMonster(Lv10Uid))
					{
						Placed->bSpecialSummoned = true;
						Log(FString::Printf(TEXT("Transcendent Wings Special Summons Winged Kuriboh LV10 from the %s."),
							bFromDeck ? TEXT("Deck") : TEXT("hand")), TEXT("spell"));
						OnSummon(*Placed, true);
					}
				}
				else
				{
					MoveToGrave(SummonCopy);
				}
			}
		}
	}
	else if (Name == TEXT("Elegant Egotist"))
	{
		SpecialSummonHarpieSisters(Side);
	}
	else if (Name == TEXT("Incandescent Ordeal"))
	{
		ActivateRitual();
	}
	else if (Name == TEXT("Sparks"))
	{
		InflictDamage(Opp, 200, TEXT("Sparks"));
	}
	else if (Name == TEXT("Token Thanksgiving"))
	{
		Log(TEXT("Token Thanksgiving destroys no tokens and restores no Life Points."), TEXT("spell"));
	}
	else if (Name == TEXT("Polymerization") || Name == TEXT("Miracle Fusion") || Name == TEXT("Dragon's Mirror"))
	{
		PerformFusion(Name);
	}
	else if (IsEquipName(Name))
	{
		if (FDuelCard* Target = ChooseEquipTarget(Side, Name))
		{
			AttachEquip(Card, *Target);
			Log(FString::Printf(TEXT("%s equips to %s."), *Name, *CardName(*Target)), TEXT("spell"));
		}
	}
	else
	{
		Log(FString::Printf(TEXT("%s resolves."), *Name), TEXT("spell"));
	}
}

bool FDuelEngine::ActivateSpell(int32 Uid, FString& OutError)
{
	if (!CanPlayerAct() || !IsMainPhase())
	{
		OutError = TEXT("You cannot activate a Spell right now.");
		return false;
	}
	FDuelCard* HandCard = nullptr;
	for (FDuelCard& Card : Player.Hand)
	{
		if (Card.Uid == Uid) { HandCard = &Card; break; }
	}
	if (!HandCard || !CanActivateSpellCard(*HandCard))
	{
		OutError = TEXT("That Spell cannot be activated right now.");
		return false;
	}
	if (bEnforceActivationTiming)
	{
		FString Reason;
		if (!IsActivationLegal(*HandCard, GetCurrentTimingWindow(), &Reason))
		{
			OutError = Reason.IsEmpty() ? TEXT("That Spell cannot be activated in this timing window.") : Reason;
			return false;
		}
	}
	const FString Name = HandCard->Data.Name;
	const bool bFieldSpell = IsFieldSpellCard(*HandCard);
	const bool bStays = IsPersistentSpellTrap(*HandCard);
	FDuelCard Copy;
	if (!RemoveFromZone(Copy, Uid))
	{
		OutError = TEXT("The card is no longer in your hand.");
		return false;
	}

	if (TryCounterSpell(EDuelOwner::Player, EDuelOwner::Opponent))
	{
		MoveToGrave(Copy);
		return true;
	}

	Log(FString::Printf(TEXT("You activate %s."), *Name), TEXT("spell"));
	if (!PlaceSpellTrap(EDuelOwner::Player, Copy, true, bFieldSpell))
	{
		MoveToGrave(Copy);
		OutError = TEXT("There is no room in your Spell & Trap Zone.");
		return false;
	}

	if (FDuelCard* Placed = FindSpellTrap(Uid))
	{
		FDuelVisualEvent& SpellEvent = EmitVisual(EDuelVisualEventType::Spell, EDuelOwner::Player, Placed, 0, Name);
		SpellEvent.Zone = FindSpellZone(EDuelOwner::Player, Uid);
		OnSpellActivated();
		++ResultStats.SpellsActivated;
		ResolveSpell(*Placed);
	}
	if (EffectRuntime)
	{
		if (FDuelCard* Live = FindSpellTrap(Uid))
		{
			EffectRuntime->OnActivate(*Live);
		}
	}
	CheckWinner();
	if (bWinnerSet) return true;

	if (!bStays && FindSpellTrap(Uid))
	{
		FDuelCard Done;
		if (RemoveFromZone(Done, Uid))
		{
			MoveToGrave(Done);
		}
	}
	return true;
}

bool FDuelEngine::SetSpellTrap(int32 Uid, FString& OutError)
{
	if (!CanPlayerAct() || !IsMainPhase())
	{
		OutError = TEXT("You cannot Set a card right now.");
		return false;
	}
	FDuelCard* HandCard = nullptr;
	for (FDuelCard& Card : Player.Hand)
	{
		if (Card.Uid == Uid) { HandCard = &Card; break; }
	}
	if (!HandCard || (!HandCard->IsTrap() && !(HandCard->IsSpell() && HandCard->Data.Subtype == TEXT("Quick-Play")))
		|| EmptySpellZone(EDuelOwner::Player) == INDEX_NONE)
	{
		OutError = TEXT("That card cannot be Set.");
		return false;
	}
	const FString Name = HandCard->Data.Name;
	(void)Name;
	FDuelCard Copy;
	if (!RemoveFromZone(Copy, Uid))
	{
		OutError = TEXT("The card is no longer in your hand.");
		return false;
	}
	if (!PlaceSpellTrap(EDuelOwner::Player, Copy, false, false))
	{
		MoveToHand(Copy);
		OutError = TEXT("There is no room in your Spell & Trap Zone.");
		return false;
	}
	Log(FString::Printf(TEXT("You Set a card face-down.")), TEXT("set"));
	FDuelVisualEvent& SetEvent = EmitVisual(EDuelVisualEventType::SetCard, EDuelOwner::Player, &Copy, 0, TEXT("Set Card"), true);
	SetEvent.Zone = FindSpellZone(EDuelOwner::Player, Uid);
	Copy.TiedToUid = 0;
	return true;
}

bool FDuelEngine::ActivateSetTrap(int32 Uid, FString& OutError)
{
	if (!CanPlayerAct() || !IsMainPhase())
	{
		OutError = TEXT("You cannot activate a Trap right now.");
		return false;
	}
	FDuelCard* Trap = FindSpellTrap(Uid);
	if (!Trap || Trap->Controller != EDuelOwner::Player || Trap->bFaceUp || Trap->SetTurn >= TurnNumber)
	{
		OutError = TEXT("That Trap cannot be activated right now.");
		return false;
	}
	if (bEnforceActivationTiming)
	{
		FString Reason;
		if (!IsActivationLegal(*Trap, GetCurrentTimingWindow(), &Reason))
		{
			OutError = Reason.IsEmpty() ? TEXT("That Trap cannot be activated in this timing window.") : Reason;
			return false;
		}
	}
	if (!IsManualTrapCard(*Trap))
	{
		OutError = TEXT("That Trap activates automatically at the correct timing.");
		return false;
	}
	return ActivateTrapInternal(*Trap, EDuelOwner::Player, false);
}

bool FDuelEngine::ActivateQuickPlayFromHand(int32 Uid, FString& OutError)
{
	if (!CanPlayerAct() || (!IsMainPhase() && Phase != EDuelPhase::Battle))
	{
		OutError = TEXT("A Quick-Play Spell cannot be activated right now.");
		return false;
	}
	FDuelCard* HandCard = nullptr;
	for (FDuelCard& Card : Player.Hand)
	{
		if (Card.Uid == Uid)
		{
			HandCard = &Card;
			break;
		}
	}
	if (!HandCard || !HandCard->IsSpell() || HandCard->Data.Subtype != TEXT("Quick-Play"))
	{
		OutError = TEXT("That card is not a Quick-Play Spell in your hand.");
		return false;
	}
	if (EmptySpellZone(EDuelOwner::Player) == INDEX_NONE)
	{
		OutError = TEXT("There is no room in your Spell & Trap Zone.");
		return false;
	}
	FString Reason;
	if (!IsActivationLegal(*HandCard, GetCurrentTimingWindow(), &Reason))
	{
		OutError = Reason.IsEmpty() ? TEXT("That Quick-Play Spell cannot be activated in this timing window.") : Reason;
		return false;
	}
	// During the Main Phase the card-specific legality checks are still applied.
	// During the Battle Phase the legacy validator does not run, so the timing
	// layer plus the Quick-Play type check are the only guards.
	if (IsMainPhase() && !CanActivateSpellCard(*HandCard))
	{
		OutError = TEXT("That Quick-Play Spell cannot be activated right now.");
		return false;
	}

	const FString Name = HandCard->Data.Name;
	FDuelCard Copy;
	if (!RemoveFromZone(Copy, Uid))
	{
		OutError = TEXT("The card is no longer in your hand.");
		return false;
	}
	if (TryCounterSpell(EDuelOwner::Player, EDuelOwner::Opponent))
	{
		MoveToGrave(Copy);
		return true;
	}
	Log(FString::Printf(TEXT("You activate %s."), *Name), TEXT("spell"));
	if (!PlaceSpellTrap(EDuelOwner::Player, Copy, true, false))
	{
		MoveToGrave(Copy);
		OutError = TEXT("There is no room in your Spell & Trap Zone.");
		return false;
	}
	if (FDuelCard* Placed = FindSpellTrap(Uid))
	{
		FDuelVisualEvent& SpellEvent = EmitVisual(EDuelVisualEventType::Spell, EDuelOwner::Player, Placed, 0, Name);
		SpellEvent.Zone = FindSpellZone(EDuelOwner::Player, Uid);
		OnSpellActivated();
		++ResultStats.SpellsActivated;
		ResolveSpell(*Placed);
	}
	if (EffectRuntime)
	{
		if (FDuelCard* Live = FindSpellTrap(Uid))
		{
			EffectRuntime->OnActivate(*Live);
		}
	}
	CheckWinner();
	if (bWinnerSet)
	{
		return true;
	}
	if (FDuelCard* Done = FindSpellTrap(Uid))
	{
		if (!IsPersistentSpellTrap(*Done))
		{
			FDuelCard Remove;
			if (RemoveFromZone(Remove, Uid))
			{
				MoveToGrave(Remove);
			}
		}
	}
	return true;
}

bool FDuelEngine::ActivateSetSpell(int32 Uid, FString& OutError)
{
	if (!CanPlayerAct() || (!IsMainPhase() && Phase != EDuelPhase::Battle))
	{
		OutError = TEXT("A Set Quick-Play Spell cannot be activated right now.");
		return false;
	}
	FDuelCard* Card = FindSpellTrap(Uid);
	if (!Card || Card->Controller != EDuelOwner::Player || Card->bFaceUp
		|| Card->SetTurn >= TurnNumber || !Card->IsSpell()
		|| Card->Data.Subtype != TEXT("Quick-Play"))
	{
		OutError = TEXT("That Set card is not an activatable Quick-Play Spell.");
		return false;
	}
	FString Reason;
	if (!IsActivationLegal(*Card, GetCurrentTimingWindow(), &Reason))
	{
		OutError = Reason.IsEmpty() ? TEXT("That Quick-Play Spell cannot be activated in this timing window.") : Reason;
		return false;
	}

	const FString Name = Card->Data.Name;
	Card->bFaceUp = true;
	if (EffectRuntime)
	{
		EffectRuntime->RecomputeContinuous();
	}
	if (TryCounterSpell(EDuelOwner::Player, EDuelOwner::Opponent))
	{
		if (FDuelCard* Negated = FindSpellTrap(Uid))
		{
			DestroySpellTrap(*Negated, true);
		}
		return true;
	}
	Log(FString::Printf(TEXT("You activate %s."), *Name), TEXT("spell"));
	if (FDuelCard* Placed = FindSpellTrap(Uid))
	{
		FDuelVisualEvent& SpellEvent = EmitVisual(EDuelVisualEventType::Spell, EDuelOwner::Player, Placed, 0, Name);
		SpellEvent.Zone = FindSpellZone(EDuelOwner::Player, Uid);
		OnSpellActivated();
		++ResultStats.SpellsActivated;
		ResolveSpell(*Placed);
	}
	if (EffectRuntime)
	{
		if (FDuelCard* Live = FindSpellTrap(Uid))
		{
			EffectRuntime->OnActivate(*Live);
		}
	}
	CheckWinner();
	if (bWinnerSet)
	{
		return true;
	}
	CleanupResolvedChainCard(Uid);
	return true;
}

bool FDuelEngine::ActivateTrapInternal(FDuelCard& Trap, EDuelOwner Side, bool bAutomatic)
{
	if (bWinnerSet || !Trap.IsValid())
	{
		return false;
	}
	if (EffectRuntime && EffectRuntime->IsCardActivationLocked(Trap))
	{
		Log(FString::Printf(TEXT("%s cannot be activated because Trap activation is locked."), *Trap.Data.Name), TEXT("trap"));
		return false;
	}
	const int32 Uid = Trap.Uid;
	const FString Name = Trap.Data.Name;
	if (TryCounterTrap(Side, Other(Side)))
	{
		if (FDuelCard* Negated = FindSpellTrap(Uid))
		{
			DestroySpellTrap(*Negated, true);
		}
		Log(FString::Printf(TEXT("%s is negated."), *Name), TEXT("trap"));
		return true;
	}
	if (bWinnerSet)
	{
		return true;
	}
	if (FDuelCard* FieldTrap = FindSpellTrap(Uid))
	{
		FieldTrap->bFaceUp = true;
	}
	if (EffectRuntime)
	{
		EffectRuntime->RecomputeContinuous();
	}
	Log(FString::Printf(TEXT("%s activates %s."), *SideRef(Side).Name, *Name), TEXT("trap"));
	FDuelVisualEvent& TrapEvent = EmitVisual(EDuelVisualEventType::Trap, Side, &Trap, 0, Name);
	TrapEvent.Zone = FindSpellZone(Side, Uid);
	if (Side == EDuelOwner::Player)
	{
		++ResultStats.TrapsActivated;
	}

	FDuelCard* Placed = FindSpellTrap(Uid);
	if (!Placed)
	{
		return false;
	}
	ResolveTrap(*Placed);
	if (EffectRuntime)
	{
		if (FDuelCard* Live = FindSpellTrap(Uid))
		{
			EffectRuntime->OnActivate(*Live);
		}
	}
	CheckWinner();
	if (bWinnerSet)
	{
		return true;
	}
	if (!IsPersistentSpellTrap(*Placed))
	{
		if (FDuelCard* Done = FindSpellTrap(Uid))
		{
			DestroySpellTrap(*Done, true);
		}
	}
	return true;
}

void FDuelEngine::ResolveTrap(FDuelCard& Trap)
{
	const EDuelOwner Side = Trap.Controller;
	const EDuelOwner Opp = Other(Side);
	const FString Name = Trap.Data.Name;
	if (Name == TEXT("Call of the Haunted"))
	{
		FDuelCard* Target = nullptr;
		for (FDuelCard& GraveCard : SideRef(Side).Graveyard)
		{
			if (GraveCard.IsMonster() && CanBeSpecialSummonedByEffect(GraveCard)
				&& (!Target || GraveCard.Data.Atk > Target->Data.Atk)) Target = &GraveCard;
		}
		if (Target)
		{
			const int32 TargetUid = Target->Uid;
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TargetUid))
			{
				if (PlaceMonster(Side, Copy, true, EDuelPosition::Attack))
				{
					if (FDuelCard* Placed = FindMonster(TargetUid))
					{
						Placed->bSpecialSummoned = true;
						Trap.TiedToUid = TargetUid;
						Log(FString::Printf(TEXT("Call of the Haunted revives %s."), *CardName(*Placed)), TEXT("trap"));
						OnSummon(*Placed, true);
					}
				}
				else
				{
					MoveToGrave(Copy);
				}
			}
		}
	}
	else if (Name == TEXT("Backfire"))
	{
		Log(TEXT("Backfire is now active."), TEXT("trap"));
	}
	else if (Name == TEXT("Spiritual Fire Art - Kurenai"))
	{
		FDuelCard* Target = ChooseMonster(Side, [](const FDuelCard& C) { return C.Data.Attribute == TEXT("FIRE"); }, true);
		if (Target)
		{
			const int32 OriginalAtk = Target->Data.Atk;
			const int32 TargetUid = Target->Uid;
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TargetUid))
			{
				CleanupEquips(Copy);
				MoveToGrave(Copy);
				Log(TEXT("Spiritual Fire Art - Kurenai tributes a FIRE monster."), TEXT("trap"));
				InflictDamage(Opp, OriginalAtk, TEXT("Spiritual Fire Art - Kurenai"));
			}
		}
	}
	else if (Name == TEXT("Spiritual Water Art - Aoi"))
	{
		FDuelCard* Target = ChooseMonster(Side, [](const FDuelCard& C) { return C.Data.Attribute == TEXT("WATER"); }, true);
		if (Target)
		{
			const int32 TargetUid = Target->Uid;
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TargetUid))
			{
				CleanupEquips(Copy);
				MoveToGrave(Copy);
				Log(TEXT("Spiritual Water Art - Aoi tributes a WATER monster."), TEXT("trap"));
				if (SideRef(Opp).Hand.Num() > 0)
				{
					int32 Index = 0;
					int32 BestValue = TNumericLimits<int32>::Lowest();
					for (int32 I = 0; I < SideRef(Opp).Hand.Num(); ++I)
					{
						const int32 Value = AiCardValue(SideRef(Opp).Hand[I]);
						if (Value > BestValue)
						{
							BestValue = Value;
							Index = I;
						}
					}
					FDuelCard Discarded = SideRef(Opp).Hand[Index];
					SideRef(Opp).Hand.RemoveAt(Index);
					EmitVisual(EDuelVisualEventType::Discard, Opp, &Discarded, 0, TEXT("SPIRITUAL WATER ART"));
					MoveToGrave(Discarded);
					Log(FString::Printf(TEXT("%s discards %s."), *SideRef(Opp).Name, *CardName(Discarded)), TEXT("trap"));
				}
			}
		}
	}
	else if (Name == TEXT("Spiritual Wind Art - Miyabi"))
	{
		FDuelCard* Target = ChooseMonster(Side, [](const FDuelCard& C) { return C.Data.Attribute == TEXT("WIND"); }, true);
		if (Target)
		{
			const int32 TargetUid = Target->Uid;
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TargetUid))
			{
				CleanupEquips(Copy);
				MoveToGrave(Copy);
				Log(TEXT("Spiritual Wind Art - Miyabi tributes a WIND monster."), TEXT("trap"));
				int32 EnemyUid = 0;
				FDuelCard* EnemyMonster = ChooseMonster(Opp, [](const FDuelCard&) { return true; }, true);
				if (EnemyMonster)
				{
					EnemyUid = EnemyMonster->Uid;
				}
				else
				{
					for (const FDuelCard& EnemySpell : SideRef(Opp).Spells)
					{
						if (EnemySpell.IsValid()) { EnemyUid = EnemySpell.Uid; break; }
					}
					if (EnemyUid == 0 && SideRef(Opp).Field.IsValid()) EnemyUid = SideRef(Opp).Field.Uid;
				}
				if (EnemyUid != 0)
				{
					FDuelCard EnemyCopy;
					if (RemoveFromZone(EnemyCopy, EnemyUid))
					{
						Log(FString::Printf(TEXT("Spiritual Wind Art - Miyabi returns %s to the Deck."), *CardName(EnemyCopy)), TEXT("trap"));
						if (EnemyCopy.IsMonster())
						{
							CleanupEquips(EnemyCopy);
						}
						else
						{
							const FString LinkedName = EnemyCopy.Data.Name;
							const int32 LinkedUid = EnemyCopy.EquippedToUid != 0
								? EnemyCopy.EquippedToUid : EnemyCopy.TiedToUid;
							if (LinkedName == TEXT("Snatch Steal") && LinkedUid != 0)
							{
								if (FDuelCard* Linked = FindMonster(LinkedUid)) ReturnControl(*Linked);
							}
							else if ((LinkedName == TEXT("Premature Burial") || LinkedName == TEXT("Call of the Haunted")
								|| LinkedName == TEXT("Autonomous Action Unit")) && LinkedUid != 0)
							{
								if (FDuelCard* Linked = FindMonster(LinkedUid))
								{
									DestroyMonster(*Linked, false, nullptr, false, LinkedName);
								}
							}
						}
						MoveToDeckBottom(EnemyCopy);
					}
				}
			}
		}
	}
}

bool FDuelEngine::TryCounterSpell(EDuelOwner Caster, EDuelOwner Defender)
{
	if (bWinnerSet) return false;
	if (EffectRuntime && EffectRuntime->IsTrapActivationLocked()) return false;
	for (FDuelCard& Trap : SideRef(Defender).Spells)
	{
		if (Trap.IsValid() && !Trap.bFaceUp && IsName(Trap, TEXT("Magic Jammer")) && Trap.SetTurn < TurnNumber)
		{
			if (SideRef(Defender).Hand.Num() == 0) return false;
			int32 Index = 0;
			int32 LowestValue = TNumericLimits<int32>::Max();
			for (int32 I = 0; I < SideRef(Defender).Hand.Num(); ++I)
			{
				const int32 Value = AiCardValue(SideRef(Defender).Hand[I]);
				if (Value < LowestValue)
				{
					LowestValue = Value;
					Index = I;
				}
			}
			FDuelCard Cost = SideRef(Defender).Hand[Index];
			SideRef(Defender).Hand.RemoveAt(Index);
			EmitVisual(EDuelVisualEventType::Discard, Defender, &Cost, 0, TEXT("MAGIC JAMMER"));
			MoveToGrave(Cost);
			const int32 TrapUid = Trap.Uid;
			if (FDuelCard* LiveTrap = FindSpellTrap(TrapUid))
			{
				LiveTrap->bFaceUp = true;
				Log(FString::Printf(TEXT("%s activates Magic Jammer and discards %s."), *SideRef(Defender).Name, *CardName(Cost)), TEXT("trap"));
				FDuelVisualEvent& CounterEvent = EmitVisual(EDuelVisualEventType::Trap, Defender, LiveTrap, 0, TEXT("Magic Jammer"));
				CounterEvent.Zone = FindSpellZone(Defender, TrapUid);
				if (FDuelCard* Done = FindSpellTrap(TrapUid)) DestroySpellTrap(*Done, true);
			}
			Log(FString::Printf(TEXT("The Spell is negated.")), TEXT("trap"));
			return true;
		}
	}
	return false;
}

bool FDuelEngine::TryCounterTrap(EDuelOwner Caster, EDuelOwner Defender)
{
	if (bWinnerSet) return false;
	if (EffectRuntime && EffectRuntime->IsTrapActivationLocked()) return false;
	for (FDuelCard& Trap : SideRef(Defender).Spells)
	{
		if (Trap.IsValid() && !Trap.bFaceUp && IsName(Trap, TEXT("Seven Tools of the Bandit")) && Trap.SetTurn < TurnNumber)
		{
			if (SideRef(Defender).LP <= 1000) return false;
			const int32 TrapUid = Trap.Uid;
			PayLp(Defender, 1000, TEXT("Seven Tools of the Bandit"));
			if (FDuelCard* LiveTrap = FindSpellTrap(TrapUid))
			{
				LiveTrap->bFaceUp = true;
				Log(FString::Printf(TEXT("%s activates Seven Tools of the Bandit."), *SideRef(Defender).Name), TEXT("trap"));
				FDuelVisualEvent& CounterEvent = EmitVisual(EDuelVisualEventType::Trap, Defender, LiveTrap, 0, TEXT("Seven Tools of the Bandit"));
				CounterEvent.Zone = FindSpellZone(Defender, TrapUid);
				if (FDuelCard* Done = FindSpellTrap(TrapUid)) DestroySpellTrap(*Done, true);
			}
			return true;
		}
	}
	return false;
}

bool FDuelEngine::FindFusionOption(EDuelOwner Side, const FString& FusionType, int32* OutResult, TArray<int32>* OutMaterialUids) const
{
	if (!Database)
	{
		return false;
	}
	if (FusionType == TEXT("Fusion Gate") && EffectRuntime && !EffectRuntime->IsFusionAllowed(FusionType))
	{
		return false;
	}

	const bool bFromHand = FusionType == TEXT("Polymerization");
	const FDuelSide& State = SideRef(Side);
	TArray<const FDuelCard*> Candidates;
	if (bFromHand)
	{
		for (const FDuelCard& Card : State.Hand)
		{
			if (Card.IsMonster()) Candidates.Add(&Card);
		}
	}
	for (const FDuelCard& Card : State.Monsters)
	{
		if (Card.IsValid()) Candidates.Add(&Card);
	}
	if (!bFromHand)
	{
		for (const FDuelCard& Card : State.Graveyard)
		{
			if (Card.IsMonster()) Candidates.Add(&Card);
		}
	}

	const bool bNoEmptyZone = EmptyMonsterZone(Side) == INDEX_NONE;
	if (bNoEmptyZone)
	{
		// When the board is full, prefer using a material that is already on the
		// field so the Fusion Monster can take its zone.
		Candidates.Sort([&State](const FDuelCard& A, const FDuelCard& B)
		{
			const bool bAOnField = State.Monsters.ContainsByPredicate([&A](const FDuelCard& M) { return M.IsValid() && M.Uid == A.Uid; });
			const bool bBOnField = State.Monsters.ContainsByPredicate([&B](const FDuelCard& M) { return M.IsValid() && M.Uid == B.Uid; });
			if (bAOnField != bBOnField) return bAOnField;
			return A.Data.Atk < B.Data.Atk;
		});
	}

	for (const FFusionRecipeDef& Recipe : Database->GetFusions())
	{
		if (!Recipe.FusionTypes.Contains(FusionType))
		{
			continue;
		}
		const FDuelCard* ResultCard = nullptr;
		for (const FDuelCard& ExtraCard : State.Extra)
		{
			if (ExtraCard.Data.Id == Recipe.Result)
			{
				ResultCard = &ExtraCard;
				break;
			}
		}
		if (!ResultCard)
		{
			continue;
		}

		TArray<int32> MaterialUids;
		TSet<int32> Used;
		if (Recipe.AnyCount > 0)
		{
			TArray<const FDuelCard*> Matching;
			for (const FDuelCard* Candidate : Candidates)
			{
				if (Recipe.MaterialsType.IsEmpty() || Candidate->Data.MonsterType == Recipe.MaterialsType)
				{
					Matching.Add(Candidate);
				}
			}
			if (Matching.Num() < Recipe.AnyCount) continue;
			if (bNoEmptyZone)
			{
				Matching.Sort([&State](const FDuelCard& A, const FDuelCard& B)
				{
					const bool bAOnField = State.Monsters.ContainsByPredicate([&A](const FDuelCard& M) { return M.IsValid() && M.Uid == A.Uid; });
					const bool bBOnField = State.Monsters.ContainsByPredicate([&B](const FDuelCard& M) { return M.IsValid() && M.Uid == B.Uid; });
					if (bAOnField != bBOnField) return bAOnField;
					return A.Data.Atk < B.Data.Atk;
				});
			}
			else
			{
				Matching.Sort([](const FDuelCard& A, const FDuelCard& B) { return A.Data.Atk < B.Data.Atk; });
			}
			for (int32 I = 0; I < Recipe.AnyCount; ++I)
			{
				MaterialUids.Add(Matching[I]->Uid);
			}
		}
		else
		{
			bool bAllFound = true;
			for (int32 MaterialId : Recipe.Materials)
			{
				const FDuelCard* Found = nullptr;
				for (const FDuelCard* Candidate : Candidates)
				{
					if (Candidate->Data.Id == MaterialId && !Used.Contains(Candidate->Uid))
					{
						Found = Candidate;
						break;
					}
				}
				if (!Found)
				{
					bAllFound = false;
					break;
				}
				Used.Add(Found->Uid);
				MaterialUids.Add(Found->Uid);
			}
			if (!bAllFound) continue;
		}

		if (MaterialUids.Num() == 0)
		{
			continue;
		}
		if (bNoEmptyZone)
		{
			bool bUsesFieldMaterial = false;
			for (int32 Uid : MaterialUids)
			{
				if (State.Monsters.ContainsByPredicate([Uid](const FDuelCard& M) { return M.IsValid() && M.Uid == Uid; }))
				{
					bUsesFieldMaterial = true;
					break;
				}
			}
			if (!bUsesFieldMaterial)
			{
				continue;
			}
		}

		if (OutResult) *OutResult = Recipe.Result;
		if (OutMaterialUids) *OutMaterialUids = MaterialUids;
		return true;
	}
	return false;
}

bool FDuelEngine::PerformFusion(const FString& FusionType)
{
	const EDuelOwner Side = ActiveSide;
	int32 ResultId = 0;
	TArray<int32> MaterialUids;
	if (!FindFusionOption(Side, FusionType, &ResultId, &MaterialUids))
	{
		return false;
	}

	const bool bBanishMaterials = FusionType != TEXT("Polymerization");
	TArray<FString> MaterialNames;
	for (int32 Uid : MaterialUids)
	{
		FDuelCard* Material = FindCard(Uid);
		if (!Material) continue;
		MaterialNames.Add(CardName(*Material));
		const bool bOnField = FindMonster(Uid) != nullptr;
		FDuelCard Copy;
		if (!RemoveFromZone(Copy, Uid)) continue;
		if (bOnField) CleanupEquips(Copy);
		if (bBanishMaterials) MoveToBanished(Copy);
		else MoveToGrave(Copy);
	}

	FDuelCard ResultCard;
	bool bFound = false;
	for (int32 I = 0; I < SideRef(Side).Extra.Num(); ++I)
	{
		if (SideRef(Side).Extra[I].Data.Id == ResultId)
		{
			ResultCard = SideRef(Side).Extra[I];
			SideRef(Side).Extra.RemoveAt(I);
			bFound = true;
			break;
		}
	}
	if (!bFound)
	{
		return false;
	}
	EmitVisual(EDuelVisualEventType::Fusion, Side, &ResultCard, 0, FString::Join(MaterialNames, TEXT(", ")));

	if (!PlaceMonster(Side, ResultCard, true, EDuelPosition::Attack))
	{
		MoveToGrave(ResultCard);
		return false;
	}
	if (FDuelCard* Placed = FindMonster(ResultCard.Uid))
	{
		Placed->bSpecialSummoned = true;
		if (Side == EDuelOwner::Player)
		{
			++ResultStats.FusionSummons;
		}
		Log(FString::Printf(TEXT("%s Fusion Summons %s using %s."), *SideRef(Side).Name, *CardName(*Placed),
			*FString::Join(MaterialNames, TEXT(", "))), TEXT("summon"));
		OnSummon(*Placed, true);
		if (!bWinnerSet)
		{
			if (FDuelCard* Live = FindMonster(ResultCard.Uid))
			{
				TriggerSummonTraps(*Live, false);
				if (EffectRuntime)
				{
					EffectRuntime->OnFusionSummon(*Live);
				}
			}
		}
	}
	return true;
}

bool FDuelEngine::ActivateRitual()
{
	const EDuelOwner Side = ActiveSide;
	FDuelCard* RitualMonster = FindMonsterInHand(Side, TEXT("Legendary Flame Lord"));
	if (!RitualMonster || EmptyMonsterZone(Side) == INDEX_NONE)
	{
		return false;
	}
	// Capture the UID before any hand tributes invalidate the array pointer.
	const int32 RitualUid = RitualMonster->Uid;

	TArray<FDuelCard*> Candidates;
	for (FDuelCard& HandCard : SideRef(Side).Hand)
	{
		if (HandCard.IsMonster() && !IsName(HandCard, TEXT("Legendary Flame Lord")))
		{
			Candidates.Add(&HandCard);
		}
	}
	for (FDuelCard& FieldCard : SideRef(Side).Monsters)
	{
		if (FieldCard.IsValid()) Candidates.Add(&FieldCard);
	}
	Candidates.Sort([this](const FDuelCard& A, const FDuelCard& B)
	{
		return GetEffectiveLevel(A) < GetEffectiveLevel(B);
	});
	int32 TotalLevel = 0;
	TArray<int32> TributeUids;
	for (FDuelCard* Candidate : Candidates)
	{
		if (TotalLevel >= 7) break;
		TributeUids.Add(Candidate->Uid);
		TotalLevel += GetEffectiveLevel(*Candidate);
	}
	if (TotalLevel < 7)
	{
		return false;
	}
	for (int32 Uid : TributeUids)
	{
		FDuelCard* Card = FindCard(Uid);
		if (!Card) continue;
		const bool bOnField = FindMonster(Uid) != nullptr;
		FDuelCard Copy;
		if (!RemoveFromZone(Copy, Uid)) continue;
		if (bOnField) CleanupEquips(Copy);
		MoveToGrave(Copy);
		Log(FString::Printf(TEXT("%s is tributed for the Ritual Summon."), *CardName(Copy)), TEXT("summon"));
	}
	FDuelCard SummonCopy;
	if (!RemoveFromZone(SummonCopy, RitualUid))
	{
		return false;
	}
	EmitVisual(EDuelVisualEventType::Ritual, Side, &SummonCopy, TotalLevel, TEXT("LEGENDARY FLAME LORD"));
	if (!PlaceMonster(Side, SummonCopy, true, EDuelPosition::Attack))
	{
		MoveToGrave(SummonCopy);
		return false;
	}
	if (FDuelCard* Placed = FindMonster(RitualUid))
	{
		Placed->bSpecialSummoned = true;
		if (Side == EDuelOwner::Player)
		{
			++ResultStats.RitualSummons;
		}
		Log(FString::Printf(TEXT("%s Ritual Summons Legendary Flame Lord."), *SideRef(Side).Name), TEXT("summon"));
		OnSummon(*Placed, true);
		if (!bWinnerSet)
		{
			if (FDuelCard* Live = FindMonster(RitualUid))
			{
				TriggerSummonTraps(*Live, false);
				if (EffectRuntime)
				{
					EffectRuntime->OnRitualSummon(*Live);
				}
			}
		}
	}
	return true;
}

TArray<FDuelActionInfo> FDuelEngine::GetMonsterEffectActionsFor(const FDuelCard& Card)
{
	TArray<FDuelActionInfo> Actions;
	if (bWinnerSet || !IsMainPhase() || Card.Controller != ActiveSide || !Card.bFaceUp)
	{
		return Actions;
	}
	const EDuelOwner Side = Card.Controller;
	const EDuelOwner Opp = Other(Side);

	if (IsName(Card, TEXT("Elemental Hero Thunder Giant")))
	{
		if (Card.EffectUsedTurn == TurnNumber)
		{
			return Actions;
		}
		bool bTarget = false;
		for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
		{
			for (const FDuelCard& Monster : SideRef(Owner).Monsters)
			{
				if (Monster.IsValid() && Monster.bFaceUp && Monster.Data.Atk < GetAtk(Card))
				{
					bTarget = true;
					break;
				}
			}
		}
		if (bTarget && SideRef(Side).Hand.Num() > 0)
		{
			Actions.Add({ EDuelAction::ActivateEffect, TEXT("Discard 1: destroy a monster"), 0 });
		}
	}
	else if (IsName(Card, TEXT("Legendary Flame Lord")))
	{
		if (Card.Counters >= 3)
		{
			Actions.Add({ EDuelAction::ActivateEffect, TEXT("Remove 3 counters: destroy monsters"), 0 });
		}
	}
	else if (IsName(Card, TEXT("Gray Wing")))
	{
		if (Phase == EDuelPhase::Main1 && Card.EffectUsedTurn != TurnNumber && SideRef(Side).Hand.Num() > 0)
		{
			Actions.Add({ EDuelAction::ActivateEffect, TEXT("Discard 1: attack twice"), 0 });
		}
	}
	else if (IsName(Card, TEXT("Lady Ninja Yae")))
	{
		bool bOpponentHasBackrow = SideRef(Opp).Field.IsValid();
		if (!bOpponentHasBackrow)
		{
			for (const FDuelCard& Spell : SideRef(Opp).Spells)
			{
				if (Spell.IsValid()) { bOpponentHasBackrow = true; break; }
			}
		}
		if (bOpponentHasBackrow)
		{
			for (const FDuelCard& HandCard : SideRef(Side).Hand)
			{
				if (HandCard.IsMonster() && HandCard.Data.Attribute == TEXT("WIND"))
				{
					Actions.Add({ EDuelAction::ActivateEffect, TEXT("Discard WIND: bounce Spells/Traps"), 0 });
					break;
				}
			}
		}
	}
	else if (IsName(Card, TEXT("Levia-Dragon - Daedalus")))
	{
		if (HasField(Side, TEXT("Umi")) || HasField(Side, TEXT("A Legendary Ocean")))
		{
			Actions.Add({ EDuelAction::ActivateEffect, TEXT("Send Umi: destroy all other cards"), 0 });
		}
	}
	else if (IsName(Card, TEXT("Ocean Dragon Lord - Neo-Daedalus")))
	{
		if (HasField(Side, TEXT("Umi")) || HasField(Side, TEXT("A Legendary Ocean")))
		{
			Actions.Add({ EDuelAction::ActivateEffect, TEXT("Send Umi: wipe the field"), 0 });
		}
	}
	else if (IsName(Card, TEXT("Ultimate Baseball Kid")))
	{
		for (const FDuelCard& Own : SideRef(Side).Monsters)
		{
			if (Own.IsValid() && Own.Uid != Card.Uid && Own.Data.Attribute == TEXT("FIRE"))
			{
				Actions.Add({ EDuelAction::ActivateEffect, TEXT("Tribute FIRE: 500 damage"), 0 });
				break;
			}
		}
	}
	if (EffectRuntime)
	{
		const TArray<FDuelActionInfo> RuntimeActions = EffectRuntime->GetManualActions(Card);
		Actions.Append(RuntimeActions);
	}
	return Actions;
}

bool FDuelEngine::CanActivateMonsterEffect(const FDuelCard& Card)
{
	return GetMonsterEffectActionsFor(Card).Num() > 0;
}

bool FDuelEngine::ActivateMonsterEffect(int32 Uid, FString& OutError)
{
	if (EffectRuntime && EffectRuntime->IsMonsterEffectLocked())
	{
		OutError = TEXT("Monster effects are currently locked.");
		return false;
	}
	if (HasPendingChoice())
	{
		OutError = TEXT("Answer the pending choice first.");
		return false;
	}
	FDuelCard* Card = FindMonster(Uid);
	if (!Card || Card->Controller != ActiveSide)
	{
		OutError = TEXT("That monster is not on your field.");
		return false;
	}
	if (EffectRuntime && EffectRuntime->HasManualEffect(*Card))
	{
		for (int32 ScriptIndex = 0; ScriptIndex < EffectRuntime->GetScriptCount(Card->Data.Id); ++ScriptIndex)
		{
			if (EffectRuntime->GetScriptTrigger(Card->Data.Id, ScriptIndex) == EDEffectTrigger::Manual)
			{
				FString RuntimeError;
				if (EffectRuntime->ActivateManualScript(Card->Uid, ScriptIndex, RuntimeError))
				{
					return true;
				}
				OutError = RuntimeError;
				return false;
			}
		}
	}
	if (GetMonsterEffectActionsFor(*Card).Num() == 0)
	{
		OutError = TEXT("That effect cannot be activated right now.");
		return false;
	}
	if (bEnforceActivationTiming)
	{
		FString Reason;
		if (!IsActivationLegal(*Card, GetCurrentTimingWindow(), &Reason))
		{
			OutError = Reason.IsEmpty() ? TEXT("That monster effect cannot be activated in this timing window.") : Reason;
			return false;
		}
	}
	const EDuelOwner Side = Card->Controller;
	const EDuelOwner Opp = Other(Side);
	const FString Name = CardName(*Card);
	const int32 CardUid = Card->Uid;
	const int32 CurrentAtk = GetAtk(*Card);

	if (Name == TEXT("Elemental Hero Thunder Giant"))
	{
		FDuelSide& State = SideRef(Side);
		if (State.Hand.Num() == 0) return false;
		int32 BestIndex = 0;
		int32 BestValue = TNumericLimits<int32>::Max();
		for (int32 I = 0; I < State.Hand.Num(); ++I)
		{
			if (AiCardValue(State.Hand[I]) < BestValue)
			{
				BestValue = AiCardValue(State.Hand[I]);
				BestIndex = I;
			}
		}
		FDuelCard Discarded = State.Hand[BestIndex];
		State.Hand.RemoveAt(BestIndex);
		EmitVisual(EDuelVisualEventType::Discard, Side, &Discarded, 0, TEXT("THUNDER GIANT"));
		MoveToGrave(Discarded);
		Log(FString::Printf(TEXT("Elemental Hero Thunder Giant discards %s."), *CardName(Discarded)), TEXT("effect"));
		FDuelCard* Target = nullptr;
		for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
		{
			for (FDuelCard& Monster : SideRef(Owner).Monsters)
			{
				if (Monster.IsValid() && Monster.bFaceUp && Monster.Uid != CardUid
					&& Monster.Data.Atk < CurrentAtk
					&& (!Target || Monster.Data.Atk > Target->Data.Atk))
				{
					Target = &Monster;
				}
			}
		}
		if (Target)
		{
			Log(FString::Printf(TEXT("Elemental Hero Thunder Giant destroys %s."), *CardName(*Target)), TEXT("effect"));
			EmitVisual(EDuelVisualEventType::Effect, Side, nullptr, 0, TEXT("Thunder Giant"));
			DestroyMonster(*Target, false, nullptr, false, TEXT("Thunder Giant"));
		}
	}
	else if (Name == TEXT("Legendary Flame Lord"))
	{
		if (Card->Counters >= 3)
		{
			Card->Counters -= 3;
			TArray<int32> MonsterUids;
			for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
			{
				for (const FDuelCard& Monster : SideRef(Owner).Monsters)
				{
					if (Monster.IsValid() && Monster.Uid != CardUid) MonsterUids.Add(Monster.Uid);
				}
			}
			Log(TEXT("Legendary Flame Lord removes 3 Spell Counters and destroys all other monsters."), TEXT("effect"));
			EmitVisual(EDuelVisualEventType::Effect, Side, nullptr, 0, TEXT("SPELL COUNTERS"));
			for (int32 MonsterUid : MonsterUids)
			{
				if (FDuelCard* Monster = FindMonster(MonsterUid))
				{
					DestroyMonster(*Monster, false, nullptr, false, TEXT("Legendary Flame Lord"));
				}
			}
		}
	}
	else if (Name == TEXT("Gray Wing"))
	{
		FDuelSide& State = SideRef(Side);
		if (State.Hand.Num() == 0)
		{
			return false;
		}
		int32 BestIndex = 0;
		int32 BestValue = TNumericLimits<int32>::Max();
		for (int32 I = 0; I < State.Hand.Num(); ++I)
		{
			const int32 Value = AiCardValue(State.Hand[I]);
			if (Value < BestValue)
			{
				BestValue = Value;
				BestIndex = I;
			}
		}
		FDuelCard Discarded = State.Hand[BestIndex];
		State.Hand.RemoveAt(BestIndex);
		EmitVisual(EDuelVisualEventType::Discard, Side, &Discarded, 0, TEXT("GRAY WING"));
		MoveToGrave(Discarded);
		if (FDuelCard* Still = FindMonster(CardUid))
		{
			Still->ExtraAttacks = 1;
			Still->bHasAttacked = false;
		}
		Log(FString::Printf(TEXT("Gray Wing discards %s and can attack twice this Battle Phase."), *CardName(Discarded)), TEXT("effect"));
		EmitVisual(EDuelVisualEventType::Effect, Side, nullptr, 0, TEXT("GRAY WING: DOUBLE ATTACK"));
	}
	else if (Name == TEXT("Lady Ninja Yae"))
	{
		FDuelSide& State = SideRef(Side);
		int32 WindUid = 0;
		FString WindName;
		for (const FDuelCard& HandCard : State.Hand)
		{
			if (HandCard.IsMonster() && HandCard.Data.Attribute == TEXT("WIND"))
			{
				WindUid = HandCard.Uid;
				WindName = HandCard.Data.Name;
				break;
			}
		}
		if (WindUid == 0)
		{
			return false;
		}
		FDuelCard Discarded;
		if (RemoveFromZone(Discarded, WindUid))
		{
			EmitVisual(EDuelVisualEventType::Discard, Side, &Discarded, 0, TEXT("LADY NINJA YAE"));
			MoveToGrave(Discarded);
		}
		TArray<int32> SpellUids;
		for (const FDuelCard& Spell : SideRef(Opp).Spells)
		{
			if (Spell.IsValid()) SpellUids.Add(Spell.Uid);
		}
		if (SideRef(Opp).Field.IsValid()) SpellUids.Add(SideRef(Opp).Field.Uid);
		for (int32 SpellUid : SpellUids)
		{
			if (FDuelCard* Spell = FindSpellTrap(SpellUid))
			{
				ReturnSpellTrapToHand(*Spell);
			}
		}
		Log(FString::Printf(TEXT("Lady Ninja Yae discards %s and returns the opponent's Spell/Trap Cards to the hand."), *WindName), TEXT("effect"));
		EmitVisual(EDuelVisualEventType::Effect, Side, nullptr, 0, TEXT("LADY NINJA YAE"));
	}
	else if (Name == TEXT("Levia-Dragon - Daedalus") || Name == TEXT("Ocean Dragon Lord - Neo-Daedalus"))
	{
		if (HasField(Side, TEXT("Umi")) || HasField(Side, TEXT("A Legendary Ocean")))
		{
			if (FDuelCard* FieldCard = FindSpellTrap(SideRef(Side).Field.Uid))
			{
				FDuelCard FieldCopy;
				const int32 FieldUid = FieldCard->Uid;
				const FString FieldName = FieldCard->Data.Name;
				if (RemoveFromZone(FieldCopy, FieldUid))
				{
					MoveToGrave(FieldCopy);
					Log(FString::Printf(TEXT("%s sends %s to the Graveyard."), *Name, *FieldName), TEXT("effect"));
				}
			}
			TArray<int32> MonsterUids;
			for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
			{
				for (const FDuelCard& Monster : SideRef(Owner).Monsters)
				{
					if (Monster.IsValid() && Monster.Uid != CardUid) MonsterUids.Add(Monster.Uid);
				}
			}
			for (int32 MonsterUid : MonsterUids)
			{
				if (FDuelCard* Monster = FindMonster(MonsterUid))
				{
					DestroyMonster(*Monster, false, nullptr, false, Name);
				}
			}
			DestroyAllSpellTraps(true);
			if (Name == TEXT("Ocean Dragon Lord - Neo-Daedalus"))
			{
				for (EDuelOwner Owner : { EDuelOwner::Player, EDuelOwner::Opponent })
				{
					TArray<FDuelCard> HandCopy = SideRef(Owner).Hand;
					SideRef(Owner).Hand.Reset();
					for (const FDuelCard& HandCard : HandCopy)
					{
						EmitVisual(EDuelVisualEventType::Discard, Owner, &HandCard, 0, TEXT("NEO-DAEDALUS"));
						MoveToGrave(HandCard);
					}
				}
				Log(TEXT("Ocean Dragon Lord - Neo-Daedalus sends both hands to the Graveyard."), TEXT("effect"));
			}
			Log(FString::Printf(TEXT("%s destroys all other cards."), *Name), TEXT("effect"));
		}
	}
	else if (Name == TEXT("Ultimate Baseball Kid"))
	{
		FDuelCard* Tribute = nullptr;
		for (FDuelCard& Own : SideRef(Side).Monsters)
		{
			if (Own.IsValid() && Own.bFaceUp && Own.Uid != CardUid && Own.Data.Attribute == TEXT("FIRE"))
			{
				Tribute = &Own;
				break;
			}
		}
		if (Tribute)
		{
			const int32 TributeUid = Tribute->Uid;
			FDuelCard Copy;
			if (RemoveFromZone(Copy, TributeUid))
			{
				CleanupEquips(Copy);
				MoveToGrave(Copy);
				Log(TEXT("Ultimate Baseball Kid tributes a FIRE monster."), TEXT("effect"));
				InflictDamage(Opp, 500, TEXT("Ultimate Baseball Kid"));
			}
		}
	}
	if (FDuelCard* Still = FindMonster(CardUid))
	{
		if (Name == TEXT("Elemental Hero Thunder Giant") || Name == TEXT("Gray Wing"))
		{
			Still->EffectUsedTurn = TurnNumber;
		}
	}
	CheckWinner();
	return true;
}

// ---------------------------------------------------------------------------
// Opponent AI
// ---------------------------------------------------------------------------

void FDuelEngine::AiPlayMainPhase()
{
	if (bWinnerSet) return;
	AiActivateSpells();
	if (bWinnerSet) return;
	AiNormalSummon();
	if (bWinnerSet) return;
	AiActivateSpells();
	if (bWinnerSet) return;
	AiSetTraps();
	if (bWinnerSet) return;
	AiActivateMonsterEffects();
	if (bWinnerSet) return;
	AiActivateManualTraps();
}

void FDuelEngine::AiNormalSummon()
{
	if (bWinnerSet) return;
	const EDuelOwner Side = ActiveSide;
	FDuelSide& State = SideRef(Side);
	if (State.bNormalSummoned) return;

	const int32 CurrentBestAtk = [this, Side]()
	{
		int32 Best = 0;
		for (const FDuelCard& Monster : SideRef(Side).Monsters)
		{
			if (Monster.IsValid() && Monster.bFaceUp) Best = FMath::Max(Best, GetAtk(Monster));
		}
		return Best;
	}();
	const int32 AvailableMonsters = CountMonsters(Side);

	FDuelCard* Best = nullptr;
	int32 BestScore = TNumericLimits<int32>::Lowest();
	for (FDuelCard& HandCard : State.Hand)
	{
		if (!HandCard.IsMonster() || IsNormalSummonLocked(HandCard)) continue;
		const int32 Required = GetTributeCount(HandCard);
		if (Required > 0 && (AvailableMonsters < Required || HandCard.Data.Atk < CurrentBestAtk + 200)) continue;
		if (Required == 0 && EmptyMonsterZone(Side) == INDEX_NONE) continue;
		const int32 Score = HandCard.Data.Atk + HandCard.Data.Level * 20 - Required * 60;
		if (Score > BestScore)
		{
			Best = &HandCard;
			BestScore = Score;
		}
	}
	if (!Best)
	{
		return;
	}

	const int32 Uid = Best->Uid;
	const FString Name = Best->Data.Name;
	const int32 Required = GetTributeCount(*Best);
	if (Required == 0 && EmptyMonsterZone(Side) == INDEX_NONE) return;

	TArray<int32> TributeUids;
	if (Required > 0)
	{
		TArray<FDuelCard*> Tributes = OwnMonsters(Side);
		Tributes.Sort([](const FDuelCard& A, const FDuelCard& B) { return A.Data.Atk < B.Data.Atk; });
		for (int32 I = 0; I < Required && I < Tributes.Num(); ++I)
		{
			TributeUids.Add(Tributes[I]->Uid);
		}
		if (TributeUids.Num() < Required) return;
	}

	FDuelCard Copy;
	if (!RemoveFromZone(Copy, Uid)) return;
	for (int32 TributeUid : TributeUids)
	{
		FDuelCard* TributeCard = FindMonster(TributeUid);
		if (!TributeCard) continue;
		const FString TributeName = CardName(*TributeCard);
		FDuelCard TributeCopy;
		if (RemoveFromZone(TributeCopy, TributeUid))
		{
			CleanupEquips(TributeCopy);
			MoveToGrave(TributeCopy);
			Log(FString::Printf(TEXT("%s tributes %s."), *State.Name, *TributeName), TEXT("summon"));
		}
	}
	if (!PlaceMonster(Side, Copy, true, EDuelPosition::Attack))
	{
		MoveToGrave(Copy);
		return;
	}
	State.bNormalSummoned = true;
	Log(FString::Printf(TEXT("%s Normal Summons %s."), *State.Name, *Name), TEXT("summon"));
	if (FDuelCard* Placed = FindMonster(Uid))
	{
		OnSummon(*Placed, false, Required);
		if (!bWinnerSet && FindMonster(Uid))
		{
			TriggerSummonTraps(*FindMonster(Uid), true);
		}
	}
}

void FDuelEngine::AiSetTraps()
{
	if (bWinnerSet) return;
	const EDuelOwner Side = ActiveSide;
	FDuelSide& State = SideRef(Side);
	TArray<int32> TrapUids;
	for (const FDuelCard& HandCard : State.Hand)
	{
		if (HandCard.IsTrap()) TrapUids.Add(HandCard.Uid);
	}
	for (int32 Uid : TrapUids)
	{
		if (EmptySpellZone(Side) == INDEX_NONE) break;
		FDuelCard* HandCard = nullptr;
		for (FDuelCard& Card : State.Hand)
		{
			if (Card.Uid == Uid) { HandCard = &Card; break; }
		}
		if (!HandCard) continue;
		if (IsName(*HandCard, TEXT("Call of the Haunted"))
			&& !State.Graveyard.ContainsByPredicate([this](const FDuelCard& C)
			{
				return C.IsMonster() && CanBeSpecialSummonedByEffect(C);
			}))
		{
			continue;
		}
		FDuelCard Copy;
		if (RemoveFromZone(Copy, Uid))
		{
			if (PlaceSpellTrap(Side, Copy, false, false))
			{
				Log(FString::Printf(TEXT("%s Sets a card face-down."), *State.Name), TEXT("set"));
				FDuelVisualEvent& SetEvent = EmitVisual(EDuelVisualEventType::SetCard, Side, &Copy, 0, TEXT("Set Card"), true);
				SetEvent.Zone = FindSpellZone(Side, Uid);
			}
			else
			{
				MoveToHand(Copy);
			}
		}
	}
}

void FDuelEngine::AiActivateSpellCard(FDuelCard& Card)
{
	const EDuelOwner Side = ActiveSide;
	const EDuelOwner Opp = Other(Side);
	const int32 Uid = Card.Uid;
	const FString Name = Card.Data.Name;
	const bool bFieldSpell = IsFieldSpellCard(Card);
	const bool bStays = IsPersistentSpellTrap(Card);

	FDuelCard Copy;
	if (!RemoveFromZone(Copy, Uid))
	{
		return;
	}
	if (TryCounterSpell(Side, Opp))
	{
		MoveToGrave(Copy);
		return;
	}
	Log(FString::Printf(TEXT("%s activates %s."), *SideRef(Side).Name, *Name), TEXT("spell"));
	if (!PlaceSpellTrap(Side, Copy, true, bFieldSpell))
	{
		MoveToHand(Copy);
		return;
	}
	if (FDuelCard* Placed = FindSpellTrap(Uid))
	{
		FDuelVisualEvent& SpellEvent = EmitVisual(EDuelVisualEventType::Spell, Side, Placed, 0, Name);
		SpellEvent.Zone = FindSpellZone(Side, Uid);
		OnSpellActivated();
		if (Side == EDuelOwner::Player)
		{
			++ResultStats.SpellsActivated;
		}
		ResolveSpell(*Placed);
	}
	if (EffectRuntime)
	{
		if (FDuelCard* Live = FindSpellTrap(Uid))
		{
			EffectRuntime->OnActivate(*Live);
		}
	}
	CheckWinner();
	if (bWinnerSet) return;
	if (!bStays && FindSpellTrap(Uid))
	{
		FDuelCard Done;
		if (RemoveFromZone(Done, Uid)) MoveToGrave(Done);
	}
}

void FDuelEngine::AiActivateSpells()
{
	if (bWinnerSet) return;
	const EDuelOwner Side = ActiveSide;
	const EDuelOwner Opp = Other(Side);
	TSet<int32> Attempted;

	for (int32 Pass = 0; Pass < 12 && !bWinnerSet; ++Pass)
	{
		int32 CandidateUid = 0;
		for (const FDuelCard& HandCard : SideRef(Side).Hand)
		{
			if (!HandCard.IsSpell() || Attempted.Contains(HandCard.Uid)) continue;
			const FString& Name = HandCard.Data.Name;
			bool bWant = false;
			if (Name == TEXT("Pot of Greed") || Name == TEXT("Graceful Charity") || Name == TEXT("Upstart Goblin")
				|| Name == TEXT("Sparks") || Name == TEXT("Card Destruction"))
			{
				bWant = Name != TEXT("Card Destruction")
					|| (SideRef(Opp).Hand.Num() >= 4 || SideRef(Side).Hand.Num() >= 5);
			}
			else if (Name == TEXT("Heavy Storm") || Name == TEXT("Giant Trunade"))
			{
				bWant = CountSpells(Opp) >= 2;
			}
			else if (Name == TEXT("Polymerization") || Name == TEXT("Miracle Fusion") || Name == TEXT("Dragon's Mirror"))
			{
				bWant = FindFusionOption(Side, Name, nullptr, nullptr);
			}
			else if (Name == TEXT("Fissure") || Name == TEXT("Book of Moon") || Name == TEXT("Snatch Steal")
				|| Name == TEXT("Tribute to the Doomed") || Name == TEXT("Premature Burial")
				|| Name == TEXT("Autonomous Action Unit") || Name == TEXT("Monster Reincarnation")
				|| Name == TEXT("Salvage") || Name == TEXT("Nobleman of Extermination")
				|| Name == TEXT("Incandescent Ordeal") || Name == TEXT("Transcendent Wings")
				|| Name == TEXT("Elegant Egotist") || Name == TEXT("Special Hurricane"))
			{
				bWant = true;
			}
			else if (IsEquipName(Name))
			{
				bWant = HasEquipTarget(Side, Name);
			}
			else if (IsFieldSpellName(Name))
			{
				bWant = !SideRef(Side).Field.IsValid() || SideRef(Side).Field.Data.Name != Name;
			}

			if (!bWant || !CanActivateSpellCard(HandCard))
			{
				continue;
			}
			CandidateUid = HandCard.Uid;
			break;
		}
		if (CandidateUid == 0)
		{
			break;
		}
		Attempted.Add(CandidateUid);
		if (FDuelCard* HandCard = FindCard(CandidateUid))
		{
			AiActivateSpellCard(*HandCard);
		}
	}
}

void FDuelEngine::AiActivateMonsterEffects()
{
	if (bWinnerSet) return;
	for (int32 Pass = 0; Pass < 5 && !bWinnerSet; ++Pass)
	{
		TArray<int32> MonsterUids;
		for (const FDuelCard& Monster : SideRef(ActiveSide).Monsters)
		{
			if (Monster.IsValid()) MonsterUids.Add(Monster.Uid);
		}
		bool bUsed = false;
		for (int32 MonsterUid : MonsterUids)
		{
			FDuelCard* Monster = FindMonster(MonsterUid);
			if (!Monster) continue;
			if (GetMonsterEffectActionsFor(*Monster).Num() > 0)
			{
				FString Error;
				if (ActivateMonsterEffect(MonsterUid, Error))
				{
					bUsed = true;
					break;
				}
			}
		}
		if (!bUsed) break;
	}
}

void FDuelEngine::AiActivateManualTraps()
{
	if (bWinnerSet) return;
	const EDuelOwner Side = ActiveSide;
	FDuelSide& State = SideRef(Side);
	TArray<int32> TrapUids;
	for (const FDuelCard& Spell : State.Spells)
	{
		if (!Spell.IsValid() || Spell.bFaceUp || Spell.SetTurn >= TurnNumber) continue;
		if (IsManualTrapCard(Spell)) TrapUids.Add(Spell.Uid);
	}
	for (int32 Uid : TrapUids)
	{
		FDuelCard* Trap = FindSpellTrap(Uid);
		if (!Trap) continue;
		bool bUse = false;
		if (IsName(*Trap, TEXT("Call of the Haunted")))
		{
			bUse = EmptyMonsterZone(Side) != INDEX_NONE
				&& State.Graveyard.ContainsByPredicate([this](const FDuelCard& C)
				{
					return C.IsMonster() && CanBeSpecialSummonedByEffect(C);
				});
		}
		else if (IsName(*Trap, TEXT("Backfire")))
		{
			bUse = State.Monsters.ContainsByPredicate([](const FDuelCard& C)
			{
				return C.IsValid() && C.Data.Attribute == TEXT("FIRE");
			});
		}
		else if (IsName(*Trap, TEXT("Spiritual Fire Art - Kurenai")))
		{
			bUse = State.Monsters.ContainsByPredicate([](const FDuelCard& C)
			{
				return C.IsValid() && C.Data.Attribute == TEXT("FIRE");
			});
		}
		else if (IsName(*Trap, TEXT("Spiritual Water Art - Aoi")))
		{
			bUse = State.Monsters.ContainsByPredicate([](const FDuelCard& C)
			{
				return C.IsValid() && C.Data.Attribute == TEXT("WATER");
			});
		}
		else if (IsName(*Trap, TEXT("Spiritual Wind Art - Miyabi")))
		{
			bUse = State.Monsters.ContainsByPredicate([](const FDuelCard& C)
			{
				return C.IsValid() && C.Data.Attribute == TEXT("WIND");
			});
		}
		if (bUse)
		{
			ActivateTrapInternal(*Trap, Side, false);
			if (bWinnerSet) return;
		}
	}
}

void FDuelEngine::AiPlayBattlePhase()
{
	if (bWinnerSet || Phase != EDuelPhase::Battle) return;
	const EDuelOwner Side = ActiveSide;
	const EDuelOwner Opp = Other(Side);
	TSet<int32> Attempted;

	for (int32 Pass = 0; Pass < 16 && !bWinnerSet; ++Pass)
	{
		FDuelCard* Attacker = nullptr;
		for (FDuelCard& Monster : SideRef(Side).Monsters)
		{
			if (Monster.IsValid() && !Attempted.Contains(Monster.Uid) && CanAttack(Monster))
			{
				if (!Attacker || GetAtk(Monster) > GetAtk(*Attacker))
				{
					Attacker = &Monster;
				}
			}
		}
		if (!Attacker)
		{
			break;
		}

		const int32 AttackerUid = Attacker->Uid;
		const bool bDirectAvailable = CountMonsters(Opp) == 0
			|| (IsName(*Attacker, TEXT("Amphibious Bugroth MK-3")) && HasUmi(Side));

		int32 TargetUid = 0;
		int32 BestScore = bDirectAvailable ? 10 : TNumericLimits<int32>::Lowest();
		if (!bDirectAvailable)
		{
			for (const FDuelCard& Defender : SideRef(Opp).Monsters)
			{
				if (!Defender.IsValid()) continue;
				int32 Score = TNumericLimits<int32>::Lowest();
				if (!Defender.bFaceUp)
				{
					const int32 Atk = GetAtk(*Attacker);
					if (IsName(*Attacker, TEXT("Sasuke Samurai"))) Score = 80;
					else if (Atk >= 1900) Score = 30;
					else if (Atk >= 1200) Score = 5;
				}
				else if (Defender.Position == EDuelPosition::Attack)
				{
					const int32 Atk = GetAtk(*Attacker);
					const int32 DefAtk = GetAtk(Defender);
					if (Atk > DefAtk) Score = 100 + (Atk - DefAtk);
					else if (Atk == DefAtk && !IsName(*Attacker, TEXT("Kaiser Glider")) && !IsName(Defender, TEXT("Kaiser Glider"))) Score = 0;
				}
				else
				{
					const int32 Atk = GetAtk(*Attacker);
					const int32 Def = GetDef(Defender);
					if (Atk > Def) Score = 40 + (IsName(*Attacker, TEXT("Spear Dragon")) ? (Atk - Def) : 0);
				}
				if (Score > BestScore)
				{
					BestScore = Score;
					TargetUid = Defender.Uid;
				}
			}
		}

		if (!bDirectAvailable && BestScore <= 0)
		{
			Attempted.Add(AttackerUid);
			continue;
		}

		FString Error;
		if (!ExecuteAttack(Side, AttackerUid, TargetUid, Error))
		{
			Attempted.Add(AttackerUid);
		}
	}
}

bool FDuelEngine::AiAttackWith(FDuelCard& Attacker)
{
	FString Error;
	return ExecuteAttack(EDuelOwner::Opponent, Attacker.Uid, 0, Error);
}

int32 FDuelEngine::AiCardValue(const FDuelCard& Card) const
{
	if (Card.IsMonster())
	{
		int32 Value = Card.Data.Atk / 100 + Card.Data.Def / 200 + Card.Data.Level * 3;
		if (Card.Data.CardType != TEXT("Normal Monster")) Value += 8;
		if (Card.IsFusion()) Value += 12;
		if (Card.IsRitual()) Value += 10;
		return Value;
	}
	int32 Value = 10;
	const FString& Name = Card.Data.Name;
	if (Name == TEXT("Mirror Force") || Name == TEXT("Magic Cylinder") || Name == TEXT("Torrential Tribute")
		|| Name == TEXT("Trap Hole") || Name == TEXT("Pot of Greed") || Name == TEXT("Graceful Charity")
		|| Name == TEXT("Heavy Storm") || Name == TEXT("Snatch Steal") || Name == TEXT("Premature Burial")
		|| Name == TEXT("Polymerization") || Name == TEXT("Miracle Fusion"))
	{
		Value += 10;
	}
	if (IsEquipName(Name)) Value += 2;
	return Value;
}

void FDuelEngine::AiDiscardToLimit()
{
	const EDuelOwner Side = ActiveSide;
	FDuelSide& State = SideRef(Side);
	while (State.Hand.Num() > HandLimit)
	{
		int32 BestIndex = 0;
		int32 BestValue = TNumericLimits<int32>::Max();
		for (int32 I = 0; I < State.Hand.Num(); ++I)
		{
			const int32 Value = AiCardValue(State.Hand[I]);
			if (Value < BestValue)
			{
				BestValue = Value;
				BestIndex = I;
			}
		}
		FDuelCard Card = State.Hand[BestIndex];
		State.Hand.RemoveAt(BestIndex);
		EmitVisual(EDuelVisualEventType::Discard, Side, &Card, 0, TEXT("HAND LIMIT"));
		MoveToGrave(Card);
		Log(FString::Printf(TEXT("%s discards %s to the 6-card hand limit."), *State.Name, *CardName(Card)), TEXT("phase"));
	}
}

void FDuelEngine::DebugFinishDuel(bool bPlayerWins)
{
	if (!bWinnerSet)
	{
		if (bPlayerWins) Opponent.LP = 0;
		else Player.LP = 0;
		EndDuel(bPlayerWins ? EDuelOwner::Player : EDuelOwner::Opponent,
			bPlayerWins
				? FString::Printf(TEXT("%s's Life Points reached 0."), *OpponentDisplayName)
				: FString(TEXT("Your Life Points reached 0.")));
	}
}

// ---------------------------------------------------------------------------
// Rules architecture: choices, chain, timing, deck validation, scenario/ante
// ---------------------------------------------------------------------------

namespace
{
	bool IsResponseTimingWindow(EDuelTimingWindow Window)
	{
		return Window == EDuelTimingWindow::ResponseToActivation
			|| Window == EDuelTimingWindow::ResponseToTrap
			|| Window == EDuelTimingWindow::ResponseToSummon
			|| Window == EDuelTimingWindow::ResponseToAttack;
	}

	bool IsMainTimingWindow(EDuelTimingWindow Window)
	{
		return Window == EDuelTimingWindow::Main1 || Window == EDuelTimingWindow::Main2;
	}

	bool IsWindowInList(const TArray<EDuelTimingWindow>& Windows, EDuelTimingWindow Window)
	{
		return Windows.Contains(Window) || Windows.Contains(EDuelTimingWindow::Any);
	}
}

// ---------------------------------------------------------------------------
// Choices / targeting
// ---------------------------------------------------------------------------

bool FDuelEngine::HasPendingChoiceFor(EDuelOwner Side) const
{
	for (const FDuelChoiceRequest& Request : PendingChoices)
	{
		if (Request.Side == Side)
		{
			return true;
		}
	}
	return false;
}

const FDuelChoiceRequest* FDuelEngine::GetPendingChoice() const
{
	return PendingChoices.Num() > 0 ? &PendingChoices[0] : nullptr;
}

int32 FDuelEngine::RequestChoice(const FDuelChoiceRequest& Request,
	TFunction<void(const FDuelChoiceRequest&, const TArray<int32>&)> OnResolved)
{
	if (bWinnerSet)
	{
		Log(TEXT("A choice was requested after the duel ended."), TEXT("error"));
		return 0;
	}
	FDuelChoiceRequest Stored = Request;
	if (Stored.Options.Num() == 0)
	{
		Log(TEXT("A choice request had no options and was ignored."), TEXT("error"));
		return 0;
	}
	if (Stored.RequestId <= 0
		|| PendingChoices.ContainsByPredicate([&Stored](const FDuelChoiceRequest& Existing)
		{
			return Existing.RequestId == Stored.RequestId;
		})
		|| ChoiceResolvers.Contains(Stored.RequestId))
	{
		Stored.RequestId = NextChoiceRequestId++;
	}
	else
	{
		NextChoiceRequestId = FMath::Max(NextChoiceRequestId, Stored.RequestId + 1);
	}
	if (Stored.MinSelections < 0)
	{
		Stored.MinSelections = 0;
	}
	Stored.MinSelections = FMath::Min(Stored.MinSelections, Stored.Options.Num());
	if (Stored.MaxSelections <= 0)
	{
		Stored.MaxSelections = 1;
	}
	if (Stored.MaxSelections < Stored.MinSelections)
	{
		Stored.MaxSelections = Stored.MinSelections;
	}
	Stored.MaxSelections = FMath::Min(Stored.MaxSelections, Stored.Options.Num());

	const int32 RequestId = Stored.RequestId;
	if (OnResolved)
	{
		ChoiceResolvers.Add(RequestId, MoveTemp(OnResolved));
	}
	const bool bAutoAnswer = bAutoAnswerAllChoices
		|| (bAutoAnswerAiChoices && Stored.Side == EDuelOwner::Opponent);
	if (bAutoAnswer)
	{
		TArray<int32> OptionIds;
		BuildAutoChoiceAnswer(Stored, OptionIds);
		Log(FString::Printf(TEXT("AI answers: %s"), *Stored.Prompt), TEXT("choice"));
		InvokeChoiceResolver(RequestId, Stored, OptionIds);
		return RequestId;
	}

	PendingChoices.Add(Stored);
	Log(FString::Printf(TEXT("Choice pending: %s"), *Stored.Prompt), TEXT("choice"));
	return RequestId;
}

bool FDuelEngine::BuildAutoChoiceAnswer(const FDuelChoiceRequest& Request, TArray<int32>& OutOptionIds) const
{
	OutOptionIds.Reset();
	TSet<int32> Chosen;

	auto AddIfLegal = [&Request, &OutOptionIds, &Chosen](int32 OptionId) -> bool
	{
		if (OutOptionIds.Num() >= Request.MaxSelections)
		{
			return false;
		}
		const FDuelChoiceOption* Option = Request.Options.FindByPredicate([OptionId](const FDuelChoiceOption& Candidate)
		{
			return Candidate.Id == OptionId;
		});
		if (!Option || !Option->bEnabled || Chosen.Contains(OptionId))
		{
			return false;
		}
		Chosen.Add(OptionId);
		OutOptionIds.Add(OptionId);
		return true;
	};

	for (int32 OptionId : Request.DefaultOptionIds)
	{
		AddIfLegal(OptionId);
	}
	if (OutOptionIds.Num() < Request.MinSelections)
	{
		for (const FDuelChoiceOption& Option : Request.Options)
		{
			if (OutOptionIds.Num() >= Request.MinSelections)
			{
				break;
			}
			AddIfLegal(Option.Id);
		}
	}
	return OutOptionIds.Num() >= Request.MinSelections;
}

bool FDuelEngine::IsChoiceAnswerValid(const FDuelChoiceRequest& Request, const TArray<int32>& OptionIds, FString& OutError) const
{
	if (OptionIds.Num() < Request.MinSelections)
	{
		OutError = FString::Printf(TEXT("At least %d option(s) must be selected."), Request.MinSelections);
		return false;
	}
	if (OptionIds.Num() > Request.MaxSelections)
	{
		OutError = FString::Printf(TEXT("At most %d option(s) may be selected."), Request.MaxSelections);
		return false;
	}
	TSet<int32> Seen;
	for (int32 OptionId : OptionIds)
	{
		const FDuelChoiceOption* Option = Request.Options.FindByPredicate([OptionId](const FDuelChoiceOption& Candidate)
		{
			return Candidate.Id == OptionId;
		});
		if (!Option)
		{
			OutError = FString::Printf(TEXT("Option %d is not part of this choice."), OptionId);
			return false;
		}
		if (!Option->bEnabled)
		{
			OutError = Option->DisabledReason.IsEmpty()
				? FString::Printf(TEXT("Option %d is not legal."), OptionId)
				: Option->DisabledReason;
			return false;
		}
		if (Seen.Contains(OptionId))
		{
			OutError = FString::Printf(TEXT("Option %d was selected twice."), OptionId);
			return false;
		}
		Seen.Add(OptionId);
	}
	return true;
}

void FDuelEngine::InvokeChoiceResolver(int32 RequestId, const FDuelChoiceRequest& Request, const TArray<int32>& OptionIds)
{
	TFunction<void(const FDuelChoiceRequest&, const TArray<int32>&)> Resolver;
	if (TFunction<void(const FDuelChoiceRequest&, const TArray<int32>&)>* Found = ChoiceResolvers.Find(RequestId))
	{
		Resolver = MoveTemp(*Found);
		ChoiceResolvers.Remove(RequestId);
	}
	if (Resolver)
	{
		Resolver(Request, OptionIds);
	}
}

bool FDuelEngine::AnswerChoice(int32 RequestId, const TArray<int32>& OptionIds, FString& OutError)
{
	if (PendingChoices.Num() == 0)
	{
		OutError = TEXT("There is no pending choice.");
		return false;
	}
	if (PendingChoices[0].RequestId != RequestId)
	{
		OutError = TEXT("That is not the active choice.");
		return false;
	}

	const FDuelChoiceRequest Request = PendingChoices[0];
	if (!IsChoiceAnswerValid(Request, OptionIds, OutError))
	{
		return false;
	}

	PendingChoices.RemoveAt(0);
	InvokeChoiceResolver(Request.RequestId, Request, OptionIds);

	FString Labels;
	for (int32 OptionId : OptionIds)
	{
		for (const FDuelChoiceOption& Option : Request.Options)
		{
			if (Option.Id == OptionId && !Option.Label.IsEmpty())
			{
				Labels += Labels.IsEmpty() ? Option.Label : FString::Printf(TEXT(", %s"), *Option.Label);
				break;
			}
		}
	}
	Log(FString::Printf(TEXT("Choice answered: %s%s"), *Request.Prompt,
		Labels.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" -> %s"), *Labels)), TEXT("choice"));

	// If the player's answer uncovered an opponent-side question, drain it now
	// so the AI cannot stall behind the player queue.
	if (bAutoAnswerAiChoices)
	{
		while (!bWinnerSet)
		{
			const FDuelChoiceRequest* HeadChoice = GetPendingChoice();
			if (!HeadChoice || HeadChoice->Side != EDuelOwner::Opponent)
			{
				break;
			}
			FString AutoError;
			if (!AutoAnswerPendingChoice(&AutoError))
			{
				break;
			}
		}
	}
	return true;
}

bool FDuelEngine::AutoAnswerPendingChoice(FString* OutError)
{
	if (PendingChoices.Num() == 0)
	{
		if (OutError) *OutError = TEXT("There is no pending choice.");
		return false;
	}
	const FDuelChoiceRequest Request = PendingChoices[0];
	TArray<int32> OptionIds;
	BuildAutoChoiceAnswer(Request, OptionIds);
	FString Error;
	if (!AnswerChoice(Request.RequestId, OptionIds, Error))
	{
		if (OutError) *OutError = Error;
		return false;
	}
	return true;
}

bool FDuelEngine::CancelChoice(int32 RequestId, FString& OutError)
{
	if (PendingChoices.Num() == 0)
	{
		OutError = TEXT("There is no pending choice.");
		return false;
	}
	if (PendingChoices[0].RequestId != RequestId)
	{
		OutError = TEXT("That is not the active choice.");
		return false;
	}
	if (!PendingChoices[0].bCancellable)
	{
		OutError = TEXT("That choice cannot be cancelled.");
		return false;
	}
	const FDuelChoiceRequest Request = PendingChoices[0];
	PendingChoices.RemoveAt(0);
	InvokeChoiceResolver(Request.RequestId, Request, TArray<int32>());
	Log(FString::Printf(TEXT("Choice cancelled: %s"), *Request.Prompt), TEXT("choice"));
	return true;
}

void FDuelEngine::ClearPendingChoices()
{
	PendingChoices.Reset();
	ChoiceResolvers.Reset();
}

int32 FDuelEngine::RequestOptionalTrigger(const FDuelCard& SourceCard, const FString& Prompt, bool bDefaultYes,
	TFunction<void(bool)> OnResolved)
{
	FDuelChoiceRequest Request;
	Request.Type = EDuelChoiceType::YesNo;
	Request.Prompt = Prompt;
	Request.Side = EDuelOwner::Player;
	Request.MinSelections = 1;
	Request.MaxSelections = 1;
	Request.SourceCardUid = SourceCard.Uid;
	Request.SourceCardId = SourceCard.Data.Id;
	Request.DefaultOptionIds.Add(bDefaultYes ? 1 : 2);

	FDuelChoiceOption Yes;
	Yes.Id = 1;
	Yes.Label = TEXT("Activate");
	Request.Options.Add(Yes);

	FDuelChoiceOption No;
	No.Id = 2;
	No.Label = TEXT("Do not activate");
	Request.Options.Add(No);

	return RequestChoice(Request, [OnResolved](const FDuelChoiceRequest&, const TArray<int32>& OptionIds)
	{
		if (OnResolved)
		{
			OnResolved(OptionIds.Num() > 0 && OptionIds[0] == 1);
		}
	});
}

// ---------------------------------------------------------------------------
// Chain stack
// ---------------------------------------------------------------------------

EDuelSpellSpeed FDuelEngine::GetSpellSpeed(const FDuelCard& Card) const
{
	if (EffectRuntime)
	{
		const int32 ScriptSpeed = EffectRuntime->GetSpellSpeedOverride(Card.Data.Id);
		if (ScriptSpeed >= 1 && ScriptSpeed <= 3)
		{
			return static_cast<EDuelSpellSpeed>(ScriptSpeed);
		}
	}
	const FDuelActivationRule Rule = ResolveActivationRule(Card);
	if (Rule.SpellSpeedOverride >= 1 && Rule.SpellSpeedOverride <= 3)
	{
		return static_cast<EDuelSpellSpeed>(Rule.SpellSpeedOverride);
	}
	if (Card.IsTrap())
	{
		return Card.Data.Subtype == TEXT("Counter") ? EDuelSpellSpeed::Speed3 : EDuelSpellSpeed::Speed2;
	}
	if (Card.IsSpell())
	{
		return Card.Data.Subtype == TEXT("Quick-Play") ? EDuelSpellSpeed::Speed2 : EDuelSpellSpeed::Speed1;
	}
	if (Card.IsMonster() && Rule.bQuickEffect)
	{
		return EDuelSpellSpeed::Speed2;
	}
	return EDuelSpellSpeed::Speed1;
}

bool FDuelEngine::CanAddChainLink(EDuelSpellSpeed Speed, FString* OutReason) const
{
	if (ChainLinks.Num() == 0)
	{
		if (OutReason) *OutReason = TEXT("No chain is open.");
		return false;
	}
	if (!bEnforceChainSpellSpeeds)
	{
		return true;
	}
	const EDuelSpellSpeed Top = ChainLinks.Last().Speed;
	if (Top == EDuelSpellSpeed::Speed3 && Speed != EDuelSpellSpeed::Speed3)
	{
		if (OutReason) *OutReason = TEXT("Only a Spell Speed 3 card can respond to a Counter Trap.");
		return false;
	}
	if (static_cast<uint8>(Speed) < static_cast<uint8>(Top))
	{
		if (OutReason) *OutReason = TEXT("A chain link cannot be slower than the previous link.");
		return false;
	}
	return true;
}

int32 FDuelEngine::StartChain(const FDuelChainLink& Link, FString& OutError)
{
	if (ChainLinks.Num() > 0)
	{
		OutError = TEXT("A chain is already open.");
		return 0;
	}
	return AddChainLink(Link, OutError);
}

int32 FDuelEngine::AddChainLink(const FDuelChainLink& Link, FString& OutError)
{
	if (bWinnerSet)
	{
		OutError = TEXT("The duel is over.");
		return 0;
	}
	if (ChainLinks.Num() > 0 && !CanAddChainLink(Link.Speed, &OutError))
	{
		return 0;
	}

	FDuelChainLink Stored = Link;
	if (Stored.CardUid > 0)
	{
		const FDuelCard* Card = FindCard(Stored.CardUid);
		if (!Card)
		{
			OutError = TEXT("That chain card is no longer on the field or in a known zone.");
			return 0;
		}
		if (Stored.CardId <= 0)
		{
			Stored.CardId = Card->Data.Id;
		}
		if (Stored.Label.IsEmpty())
		{
			Stored.Label = Card->Data.Name;
		}
	}
	Stored.LinkIndex = ChainLinks.Num() + 1;
	Stored.bResolved = false;
	ChainLinks.Add(Stored);
	if (EffectRuntime)
	{
		EffectRuntime->OnChain(Stored);
	}
	Log(FString::Printf(TEXT("Chain link %d: %s (Spell Speed %d)."), Stored.LinkIndex,
		Stored.Label.IsEmpty() ? TEXT("effect") : *Stored.Label, static_cast<int32>(Stored.Speed)), TEXT("chain"));
	EmitVisual(EDuelVisualEventType::Effect, Stored.Controller, FindCard(Stored.CardUid), Stored.LinkIndex,
		Stored.Label.IsEmpty() ? TEXT("CHAIN") : Stored.Label);
	return Stored.LinkIndex;
}

bool FDuelEngine::NegateChainLink(int32 ChainLinkNumber, FString& OutError)
{
	for (FDuelChainLink& Link : ChainLinks)
	{
		if (Link.LinkIndex == ChainLinkNumber)
		{
			if (Link.bResolved)
			{
				OutError = TEXT("That chain link has already resolved.");
				return false;
			}
			Link.bNegated = true;
			Log(FString::Printf(TEXT("Chain link %d (%s) is negated."), Link.LinkIndex,
				Link.Label.IsEmpty() ? TEXT("effect") : *Link.Label), TEXT("chain"));
			return true;
		}
	}
	OutError = TEXT("That chain link does not exist.");
	return false;
}

void FDuelEngine::ExecuteChainLinkCard(FDuelChainLink& Link)
{
	if (!Link.bCardEffect || Link.CardUid <= 0)
	{
		return;
	}
	FDuelCard* Card = FindCard(Link.CardUid);
	if (!Card)
	{
		return;
	}
	Card->bFaceUp = true;
	if (Card->IsSpell())
	{
		ResolveSpell(*Card);
	}
	else if (Card->IsTrap())
	{
		ResolveTrap(*Card);
	}
}

void FDuelEngine::CleanupResolvedChainCard(int32 CardUid)
{
	FDuelCard* Card = FindSpellTrap(CardUid);
	if (!Card || !Card->bFaceUp)
	{
		return;
	}
	if (IsPersistentSpellTrap(*Card))
	{
		return;
	}
	FDuelCard Copy;
	if (RemoveFromZone(Copy, CardUid))
	{
		MoveToGrave(Copy);
	}
}

int32 FDuelEngine::ResolveChain(FString& OutError)
{
	if (ChainLinks.Num() == 0)
	{
		OutError = TEXT("There is no chain to resolve.");
		return 0;
	}

	TArray<FDuelChainLink> Pending = ChainLinks;
	ChainLinks.Reset();
	LastResolvedChain.Reset();
	ResolvedChainOrder.Reset();

	for (int32 I = Pending.Num() - 1; I >= 0; --I)
	{
		FDuelChainLink Link = Pending[I];
		Link.bResolved = true;
		LastResolvedChain.Add(Link);
		ResolvedChainOrder.Add(Link.CardUid);
		if (Link.bNegated)
		{
			Log(FString::Printf(TEXT("Chain link %d (%s) resolves negated."), Link.LinkIndex,
				Link.Label.IsEmpty() ? TEXT("effect") : *Link.Label), TEXT("chain"));
			continue;
		}

		ExecuteChainLinkCard(Link);
		if (Link.EffectId != 0 && ChainEffectResolver)
		{
			ChainEffectResolver(Link);
		}
		else if (Link.EffectId != 0)
		{
			Log(FString::Printf(TEXT("Chain link %d resolves effect %d."), Link.LinkIndex, Link.EffectId), TEXT("chain"));
		}
		if (Link.bCardEffect)
		{
			CleanupResolvedChainCard(Link.CardUid);
		}
		if (!bWinnerSet)
		{
			CheckWinner();
		}

		if (bWinnerSet)
		{
			break;
		}
	}

	Log(FString::Printf(TEXT("Chain resolved in reverse order (%d link(s))."), LastResolvedChain.Num()), TEXT("chain"));
	return LastResolvedChain.Num();
}

void FDuelEngine::ClearChain()
{
	ChainLinks.Reset();
}

// ---------------------------------------------------------------------------
// Activation windows / timing
// ---------------------------------------------------------------------------

EDuelTimingWindow FDuelEngine::GetCurrentTimingWindow() const
{
	if (bWinnerSet)
	{
		return EDuelTimingWindow::None;
	}
	switch (Phase)
	{
	case EDuelPhase::Main1: return EDuelTimingWindow::Main1;
	case EDuelPhase::Main2: return EDuelTimingWindow::Main2;
	case EDuelPhase::Battle: return EDuelTimingWindow::Battle;
	default: return EDuelTimingWindow::None;
	}
}

FDuelActivationRule FDuelEngine::ResolveActivationRule(const FDuelCard& Card) const
{
	if (const FDuelActivationRule* Found = ActivationRules.Find(Card.Data.Id))
	{
		return *Found;
	}
	FDuelActivationRule Rule;
	Rule.Mode = Card.IsTrap() ? EDuelActivationMode::Automatic : EDuelActivationMode::Manual;
	Rule.bQuickEffect = Card.IsSpell() && Card.Data.Subtype == TEXT("Quick-Play");
	Rule.bCounterTrap = Card.IsTrap() && Card.Data.Subtype == TEXT("Counter");
	return Rule;
}

EDuelActivationMode FDuelEngine::GetActivationMode(const FDuelCard& Card) const
{
	return ResolveActivationRule(Card).Mode;
}

bool FDuelEngine::IsActivationLegal(const FDuelCard& Card, EDuelTimingWindow Window, FString* OutReason) const
{
	auto Fail = [OutReason](const TCHAR* Reason)
	{
		if (OutReason) *OutReason = Reason;
		return false;
	};

	if (Window == EDuelTimingWindow::None)
	{
		return Fail(TEXT("There is no timing window for that activation."));
	}

	const FDuelActivationRule Rule = ResolveActivationRule(Card);
	const bool bResponseWindow = IsResponseTimingWindow(Window);
	const bool bMainWindow = IsMainTimingWindow(Window);
	const bool bQuickPlay = Rule.bQuickEffect
		|| (Card.IsSpell() && Card.Data.Subtype == TEXT("Quick-Play"));
	const bool bCounterTrap = Rule.bCounterTrap
		|| (Card.IsTrap() && Card.Data.Subtype == TEXT("Counter"));

	if (Rule.AllowedWindows.Num() > 0)
	{
		if (!IsWindowInList(Rule.AllowedWindows, Window))
		{
			return Fail(TEXT("That card cannot be activated in this timing window."));
		}
	}
	else if (Card.IsSpell())
	{
		if (bQuickPlay)
		{
			if (!bMainWindow && Window != EDuelTimingWindow::Battle && !bResponseWindow)
			{
				return Fail(TEXT("Quick-Play Spells can be activated from the hand during your Main or Battle Phase, or as a chain response."));
			}
		}
		else if (!bMainWindow)
		{
			return Fail(TEXT("Normal Spells can only be activated during your Main Phase."));
		}
	}
	else if (Card.IsTrap())
	{
		if (bCounterTrap)
		{
			if (!bResponseWindow)
			{
				return Fail(TEXT("Counter Traps can only be activated in response to an activation, Summon or attack."));
			}
		}
		else if (!bMainWindow && !bResponseWindow)
		{
			return Fail(TEXT("That Trap cannot be activated in this timing window."));
		}
	}
	else if (Card.IsMonster())
	{
		if (!bMainWindow && !(Rule.bQuickEffect && (Window == EDuelTimingWindow::Battle || bResponseWindow)))
		{
			return Fail(TEXT("That monster effect cannot be activated in this timing window."));
		}
	}
	else
	{
		return Fail(TEXT("That card has no activatable effect."));
	}

	if (bCounterTrap && !bResponseWindow)
	{
		return Fail(TEXT("Counter Traps can only be activated in a response window."));
	}
	if (Window == EDuelTimingWindow::DamageStep
		&& !Rule.AllowedWindows.Contains(EDuelTimingWindow::DamageStep)
		&& !Rule.AllowedWindows.Contains(EDuelTimingWindow::Any))
	{
		return Fail(TEXT("Cards cannot normally be activated during the Damage Step."));
	}
	return true;
}

bool FDuelEngine::IsAutomaticTrapTimingAllowed(const FDuelCard& Card, EDuelTimingWindow Window) const
{
	if (!bEnforceActivationTiming)
	{
		return true;
	}
	if (bLegacyAutomaticTraps)
	{
		return true;
	}
	if (GetActivationMode(Card) == EDuelActivationMode::Manual)
	{
		return false;
	}
	return IsActivationLegal(Card, Window, nullptr);
}

bool FDuelEngine::ActivateCounterTrapResponse(int32 TrapUid, int32 TargetChainLinkNumber, FString& OutError)
{
	FDuelCard* Trap = FindSpellTrap(TrapUid);
	if (!Trap || !Trap->IsTrap())
	{
		OutError = TEXT("That Counter Trap is not available.");
		return false;
	}
	const bool bCounter = Trap->Data.Subtype == TEXT("Counter") || ResolveActivationRule(*Trap).bCounterTrap;
	if (!bCounter)
	{
		OutError = TEXT("That card is not a Counter Trap.");
		return false;
	}
	if (Trap->bFaceUp || Trap->SetTurn >= TurnNumber)
	{
		OutError = TEXT("That Counter Trap cannot be activated yet.");
		return false;
	}
	if (EffectRuntime && EffectRuntime->IsCardActivationLocked(*Trap))
	{
		OutError = TEXT("Trap activation is currently locked.");
		return false;
	}
	if (!IsActivationLegal(*Trap, EDuelTimingWindow::ResponseToActivation, &OutError))
	{
		return false;
	}
	if (ChainLinks.Num() == 0 || ChainLinks.Last().LinkIndex != TargetChainLinkNumber)
	{
		OutError = TEXT("A Counter Trap must respond to the most recent chain link.");
		return false;
	}

	FDuelChainLink Link;
	Link.CardUid = Trap->Uid;
	Link.CardId = Trap->Data.Id;
	Link.Controller = Trap->Controller;
	Link.Speed = EDuelSpellSpeed::Speed3;
	Link.LinkType = EDuelChainLinkType::Trap;
	Link.Label = Trap->Data.Name;
	Link.bCardEffect = true;
	const EDuelOwner TrapController = Trap->Controller;
	const FString TrapName = Trap->Data.Name;
	if (AddChainLink(Link, OutError) == 0)
	{
		return false;
	}
	Trap->bFaceUp = true;
	if (EffectRuntime)
	{
		EffectRuntime->OnCounterTrapResponse(*Trap, TargetChainLinkNumber);
	}
	if (ChainLinks.IsValidIndex(TargetChainLinkNumber - 1)
		&& !ChainLinks[TargetChainLinkNumber - 1].bNegated)
	{
		if (!NegateChainLink(TargetChainLinkNumber, OutError))
		{
			return false;
		}
	}
	if (TrapController == EDuelOwner::Player)
	{
		++ResultStats.TrapsActivated;
	}
	Log(FString::Printf(TEXT("%s activates %s in response to chain link %d."),
		*SideRef(TrapController).Name, *TrapName, TargetChainLinkNumber), TEXT("trap"));
	return true;
}

// ---------------------------------------------------------------------------
// Deck validation / banned list
// ---------------------------------------------------------------------------

FDuelDeckValidationResult FDuelEngine::ValidateDeck(const TArray<int32>& Main, const TArray<int32>& Extra) const
{
	FDuelDeckValidationResult Result;
	Result.MainCount = Main.Num();
	Result.ExtraCount = Extra.Num();

	if (Main.Num() < BannedList.MinMain)
	{
		Result.AddError(FString::Printf(TEXT("Main Deck has %d cards; at least %d are required."), Main.Num(), BannedList.MinMain));
	}
	if (Main.Num() > BannedList.MaxMain)
	{
		Result.AddError(FString::Printf(TEXT("Main Deck has %d cards; at most %d are allowed."), Main.Num(), BannedList.MaxMain));
	}
	if (Extra.Num() > BannedList.MaxExtra)
	{
		Result.AddError(FString::Printf(TEXT("Extra Deck has %d cards; at most %d are allowed."), Extra.Num(), BannedList.MaxExtra));
	}
	if (!Database)
	{
		Result.AddWarning(TEXT("Card database is not available; card existence was not checked."));
	}

	TMap<int32, int32> MainCounts;
	TMap<int32, int32> ExtraCounts;
	TMap<int32, int32> CombinedCounts;
	for (int32 CardId : Main)
	{
		++MainCounts.FindOrAdd(CardId);
		++CombinedCounts.FindOrAdd(CardId);
		if (CardId <= 0)
		{
			Result.AddError(TEXT("Main Deck contains an invalid card id."));
		}
		else if (Database && !Database->FindCard(CardId))
		{
			Result.AddError(FString::Printf(TEXT("Main Deck contains unknown card %d."), CardId));
		}
		else if (Database)
		{
			const FCardRecord* Record = Database->FindCard(CardId);
			if (Record && Record->CardType.Contains(TEXT("Fusion")))
			{
				Result.AddError(FString::Printf(TEXT("Main Deck contains Fusion Monster %s (%d); Fusion Monsters belong in the Extra Deck."),
					*Record->Name, CardId));
			}
		}
	}
	for (int32 CardId : Extra)
	{
		++ExtraCounts.FindOrAdd(CardId);
		++CombinedCounts.FindOrAdd(CardId);
		if (CardId <= 0)
		{
			Result.AddError(TEXT("Extra Deck contains an invalid card id."));
			continue;
		}
		if (Database)
		{
			const FCardRecord* Record = Database->FindCard(CardId);
			if (!Record)
			{
				Result.AddError(FString::Printf(TEXT("Extra Deck contains unknown card %d."), CardId));
			}
			else if (!Record->CardType.Contains(TEXT("Fusion")))
			{
				Result.AddError(FString::Printf(TEXT("Extra Deck card %s (%d) is not a Fusion Monster."),
					*Record->Name, CardId));
			}
		}
	}

	auto CheckCopies = [&Result, this](const TMap<int32, int32>& Counts, const TCHAR* ZoneName)
	{
		for (const TPair<int32, int32>& Pair : Counts)
		{
			const int32 CardId = Pair.Key;
			const int32 Count = Pair.Value;
			const int32 Limit = BannedList.GetLimit(CardId);
			const int32 CopyLimit = FMath::Min(Limit, BannedList.MaxCopies);
			if (Limit == 0)
			{
				Result.AddError(FString::Printf(TEXT("%s contains banned card %d."), ZoneName, CardId));
			}
			else if (Count > CopyLimit)
			{
				const FString Reason = BannedList.GetReason(CardId);
				Result.AddError(FString::Printf(TEXT("%s contains %d copies of card %d; the limit is %d%s."),
					ZoneName, Count, CardId, CopyLimit,
					Reason.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" (%s)"), *Reason)));
			}
			if (Count > BannedList.MaxCopies)
			{
				Result.AddError(FString::Printf(TEXT("%s contains %d copies of card %d; at most %d are allowed."),
					ZoneName, Count, CardId, BannedList.MaxCopies));
			}
		}
	};
	CheckCopies(MainCounts, TEXT("Main Deck"));
	CheckCopies(ExtraCounts, TEXT("Extra Deck"));

	for (const TPair<int32, int32>& Pair : CombinedCounts)
	{
		const int32 CopyLimit = FMath::Min(BannedList.GetLimit(Pair.Key), BannedList.MaxCopies);
		if (Pair.Value > CopyLimit)
		{
			const FString Reason = BannedList.GetReason(Pair.Key);
			Result.AddError(FString::Printf(TEXT("Card %d appears %d times across the Main and Extra Decks; the combined limit is %d%s."),
				Pair.Key, Pair.Value, CopyLimit,
				Reason.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" (%s)"), *Reason)));
		}
	}
	return Result;
}

bool FDuelEngine::LoadBannedListFromJson(const FString& JsonText, FString& OutError)
{
	TSharedPtr<FJsonValue> RootValue;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
	if (!FJsonSerializer::Deserialize(Reader, RootValue) || !RootValue.IsValid())
	{
		OutError = TEXT("The banned-list JSON could not be parsed.");
		return false;
	}

	FDuelBannedListRuleset NewRules;
	auto ReadIdAndLimit = [&NewRules, &OutError](const TSharedPtr<FJsonObject>& Object) -> bool
	{
		if (!Object.IsValid())
		{
			OutError = TEXT("A banned-list entry must be an object.");
			return false;
		}
		double IdNumber = 0.0;
		double LimitNumber = 3.0;
		if (!Object->TryGetNumberField(TEXT("id"), IdNumber)
			&& !Object->TryGetNumberField(TEXT("card_id"), IdNumber)
			&& !Object->TryGetNumberField(TEXT("cardId"), IdNumber))
		{
			OutError = TEXT("A banned-list entry is missing its card id.");
			return false;
		}
		Object->TryGetNumberField(TEXT("limit"), LimitNumber);
		const int32 CardId = static_cast<int32>(IdNumber);
		const int32 Limit = FMath::Clamp(static_cast<int32>(LimitNumber), 0, 3);
		if (CardId <= 0)
		{
			OutError = TEXT("A banned-list entry has an invalid card id.");
			return false;
		}
		FString Reason;
		Object->TryGetStringField(TEXT("reason"), Reason);
		NewRules.SetLimit(CardId, Limit, Reason);
		return true;
	};

	auto ReadIdArray = [&NewRules](const TArray<TSharedPtr<FJsonValue>>* Values, int32 DefaultLimit)
	{
		if (!Values)
		{
			return;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Values)
		{
			if (!Value.IsValid())
			{
				continue;
			}
			double IdNumber = 0.0;
			if (Value->TryGetNumber(IdNumber))
			{
				const int32 CardId = static_cast<int32>(IdNumber);
				if (CardId > 0)
				{
					NewRules.SetLimit(CardId, DefaultLimit);
				}
				continue;
			}
			const TSharedPtr<FJsonObject> Object = Value->AsObject();
			if (!Object.IsValid())
			{
				continue;
			}
			if (!Object->TryGetNumberField(TEXT("card_id"), IdNumber)
				&& !Object->TryGetNumberField(TEXT("id"), IdNumber))
			{
				continue;
			}
			double LimitNumber = static_cast<double>(DefaultLimit);
			Object->TryGetNumberField(TEXT("limit"), LimitNumber);
			FString Reason;
			Object->TryGetStringField(TEXT("reason"), Reason);
			const int32 CardId = static_cast<int32>(IdNumber);
			if (CardId > 0)
			{
				NewRules.SetLimit(CardId,
					FMath::Clamp(static_cast<int32>(LimitNumber), 0, 3), Reason);
			}
		}
	};

	if (RootValue->Type == EJson::Array)
	{
		const TArray<TSharedPtr<FJsonValue>>& RootArray = RootValue->AsArray();
		for (const TSharedPtr<FJsonValue>& Value : RootArray)
		{
			if (!Value.IsValid() || !Value->AsObject().IsValid())
			{
				OutError = TEXT("A banned-list array entry must be an object.");
				return false;
			}
			if (!ReadIdAndLimit(Value->AsObject()))
			{
				return false;
			}
		}
	}
	else
	{
		const TSharedPtr<FJsonObject> Root = RootValue->AsObject();
		if (!Root.IsValid())
		{
			OutError = TEXT("The banned-list JSON must be an object or an array.");
			return false;
		}
		Root->TryGetStringField(TEXT("ruleset_id"), NewRules.RulesetId);
		const TSharedPtr<FJsonObject>* RulesObject = nullptr;
		if (Root->TryGetObjectField(TEXT("rules"), RulesObject) && RulesObject && RulesObject->IsValid())
		{
			double Number = 0.0;
			if ((*RulesObject)->TryGetNumberField(TEXT("min_main"), Number))
			{
				NewRules.MinMain = FMath::Clamp(static_cast<int32>(Number), 1, 200);
			}
			if ((*RulesObject)->TryGetNumberField(TEXT("max_main"), Number))
			{
				NewRules.MaxMain = FMath::Clamp(static_cast<int32>(Number), 1, 200);
			}
			if ((*RulesObject)->TryGetNumberField(TEXT("max_extra"), Number))
			{
				// The release gate follows the 2006 Fusion Deck cap (15), even
				// when an older A06 rules file still advertises 20.
				NewRules.MaxExtra = FMath::Clamp(static_cast<int32>(Number), 0, 15);
			}
			if ((*RulesObject)->TryGetNumberField(TEXT("max_copies"), Number))
			{
				NewRules.MaxCopies = FMath::Clamp(static_cast<int32>(Number), 1, 10);
			}
			if (NewRules.MaxMain < NewRules.MinMain)
			{
				NewRules.MaxMain = NewRules.MinMain;
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
		if (Root->TryGetArrayField(TEXT("cards"), Entries))
		{
			for (const TSharedPtr<FJsonValue>& Value : *Entries)
			{
				const TSharedPtr<FJsonObject> Object = Value.IsValid() ? Value->AsObject() : TSharedPtr<FJsonObject>();
				if (!ReadIdAndLimit(Object))
				{
					return false;
				}
			}
		}
		const TArray<TSharedPtr<FJsonValue>>* Banned = nullptr;
		const TArray<TSharedPtr<FJsonValue>>* Limited = nullptr;
		const TArray<TSharedPtr<FJsonValue>>* SemiLimited = nullptr;
		Root->TryGetArrayField(TEXT("banned"), Banned);
		Root->TryGetArrayField(TEXT("limited"), Limited);
		Root->TryGetArrayField(TEXT("semi_limited"), SemiLimited);
		ReadIdArray(Banned, 0);
		ReadIdArray(Limited, 1);
		ReadIdArray(SemiLimited, 2);
		if (!Entries && !Banned && !Limited && !SemiLimited)
		{
			OutError = TEXT("The banned-list JSON has no 'cards', 'banned', 'limited' or 'semi_limited' data.");
			return false;
		}
	}

	BannedList = NewRules;
	return true;
}

bool FDuelEngine::LoadBannedListFromFile(const FString& FilePath, FString& OutError)
{
	FString JsonText;
	if (!FFileHelper::LoadFileToString(JsonText, *FilePath))
	{
		OutError = FString::Printf(TEXT("Could not read banned-list file '%s'."), *FilePath);
		return false;
	}
	return LoadBannedListFromJson(JsonText, OutError);
}

bool FDuelEngine::LoadDefaultBannedList(FString& OutError)
{
	const FString Path = FPaths::ProjectContentDir() / TEXT("Data/Rules/banned_limited.json");
	return LoadBannedListFromFile(Path, OutError);
}

// ---------------------------------------------------------------------------
// Scenario / puzzle / exam setup
// ---------------------------------------------------------------------------

bool FDuelEngine::SetupScenarioSide(EDuelOwner Side, const FDuelScenario& Scenario, FString& OutError)
{
	FDuelSide& State = SideRef(Side);
	State = FDuelSide();
	State.Owner = Side;
	State.Name = Side == EDuelOwner::Player ? TEXT("You") : OpponentDisplayName;
	State.LP = Side == EDuelOwner::Player ? Scenario.PlayerLp : Scenario.OpponentLp;
	State.Monsters.SetNum(5);
	State.Spells.SetNum(5);

	const TArray<int32>& DeckCards = Side == EDuelOwner::Player ? Scenario.PlayerDeck : Scenario.OpponentDeck;
	for (int32 I = DeckCards.Num() - 1; I >= 0; --I)
	{
		if (DeckCards[I] > 0)
		{
			State.Deck.Add(MakeCard(DeckCards[I], Side, false));
		}
	}
	const TArray<int32>& HandCards = Side == EDuelOwner::Player ? Scenario.PlayerHand : Scenario.OpponentHand;
	for (int32 CardId : HandCards)
	{
		if (CardId > 0) State.Hand.Add(MakeCard(CardId, Side, false));
	}
	const TArray<int32>& GraveCards = Side == EDuelOwner::Player ? Scenario.PlayerGraveyard : Scenario.OpponentGraveyard;
	for (int32 CardId : GraveCards)
	{
		if (CardId > 0)
		{
			FDuelCard Card = MakeCard(CardId, Side, false);
			Card.bFaceUp = true;
			State.Graveyard.Add(Card);
		}
	}
	const TArray<int32>& ExtraCards = Side == EDuelOwner::Player ? Scenario.PlayerExtra : Scenario.OpponentExtra;
	for (int32 CardId : ExtraCards)
	{
		if (CardId > 0) State.Extra.Add(MakeCard(CardId, Side, true));
	}

	const TArray<FDuelScenarioCard>& FieldCards = Side == EDuelOwner::Player ? Scenario.PlayerField : Scenario.OpponentField;
	for (const FDuelScenarioCard& Spec : FieldCards)
	{
		if (Spec.CardId <= 0)
		{
			continue;
		}
		if (Spec.Zone == EDuelZone::Monster)
		{
			FDuelCard Card = MakeCard(Spec.CardId, Side, false);
			const EDuelPosition Position = (Spec.bDefense || Spec.bFaceDown) ? EDuelPosition::Defense : EDuelPosition::Attack;
			if (!PlaceMonster(Side, Card, !Spec.bFaceDown, Position, Spec.ZoneIndex))
			{
				OutError = FString::Printf(TEXT("Scenario monster %d could not be placed."), Spec.CardId);
				return false;
			}
		}
		else if (Spec.Zone == EDuelZone::SpellTrap)
		{
			FDuelCard Card = MakeCard(Spec.CardId, Side, false);
			if (Spec.ZoneIndex >= 0 && Spec.ZoneIndex < State.Spells.Num())
			{
				if (State.Spells[Spec.ZoneIndex].IsValid())
				{
					OutError = FString::Printf(TEXT("Scenario Spell/Trap zone %d is already occupied."), Spec.ZoneIndex);
					return false;
				}
				Card.Controller = Side;
				Card.bFaceUp = !Spec.bFaceDown;
				Card.Position = EDuelPosition::Attack;
				Card.SetTurn = Card.bFaceUp ? -1 : TurnNumber;
				State.Spells[Spec.ZoneIndex] = Card;
			}
			else if (!PlaceSpellTrap(Side, Card, !Spec.bFaceDown, false))
			{
				OutError = FString::Printf(TEXT("Scenario Spell/Trap %d could not be placed."), Spec.CardId);
				return false;
			}
		}
		else if (Spec.Zone == EDuelZone::Field)
		{
			FDuelCard Card = MakeCard(Spec.CardId, Side, false);
			if (!PlaceSpellTrap(Side, Card, !Spec.bFaceDown, true))
			{
				OutError = FString::Printf(TEXT("Scenario Field Spell %d could not be placed."), Spec.CardId);
				return false;
			}
		}
		else if (Spec.Zone == EDuelZone::Hand)
		{
			State.Hand.Add(MakeCard(Spec.CardId, Side, false));
		}
		else if (Spec.Zone == EDuelZone::Deck)
		{
			State.Deck.Insert(MakeCard(Spec.CardId, Side, false), 0);
		}
		else if (Spec.Zone == EDuelZone::Graveyard)
		{
			State.Graveyard.Add(MakeCard(Spec.CardId, Side, false));
		}
		else if (Spec.Zone == EDuelZone::Banished)
		{
			State.Banished.Add(MakeCard(Spec.CardId, Side, false));
		}
		else if (Spec.Zone == EDuelZone::Extra)
		{
			State.Extra.Add(MakeCard(Spec.CardId, Side, true));
		}
	}
	return true;
}

bool FDuelEngine::StartScenario(const FDuelScenario& Scenario, FString& OutError)
{
	OutError.Reset();
	if (!Database)
	{
		OutError = TEXT("A card database is required to start a scenario.");
		return false;
	}

	ResetDuelState();
	bStarted = true;
	bScenarioActive = true;
	ActiveScenario = Scenario;
	ScenarioPlayerTurns = 0;
	ScenarioElapsedSeconds = 0.f;
	bScenarioObjectiveComplete = false;
	ResultStats.Mode = Scenario.Mode.IsEmpty() ? TEXT("puzzle") : Scenario.Mode;
	if (Scenario.Seed != 0)
	{
		Random.Initialize(Scenario.Seed);
	}

	PlayerDeckId = Scenario.Id.IsEmpty() ? TEXT("scenario") : FString::Printf(TEXT("scenario:%s"), *Scenario.Id);
	OpponentDeckId = PlayerDeckId;
	OpponentCharacterId = Scenario.Id.IsEmpty() ? TEXT("puzzle") : Scenario.Id;
	OpponentDisplayName = Scenario.Name.IsEmpty() ? TEXT("Opponent") : Scenario.Name;
	Opponent.Name = OpponentDisplayName;
	Player.Name = TEXT("You");

	if (!SetupScenarioSide(EDuelOwner::Player, Scenario, OutError)
		|| !SetupScenarioSide(EDuelOwner::Opponent, Scenario, OutError))
	{
		bStarted = false;
		bScenarioActive = false;
		return false;
	}

	// Resolve ante UIDs against the fixed decks.
	if (AnteState.bEnabled)
	{
		for (const FDuelCard& Card : Player.Deck)
		{
			if (Card.Data.Id == AnteState.PlayerCardId)
			{
				AnteState.PlayerCardUid = Card.Uid;
				break;
			}
		}
		for (const FDuelCard& Card : Opponent.Deck)
		{
			if (Card.Data.Id == AnteState.OpponentCardId)
			{
				AnteState.OpponentCardUid = Card.Uid;
				break;
			}
		}
	}

	const EDuelOwner FirstSide = Scenario.bPlayerGoesFirst ? EDuelOwner::Player : EDuelOwner::Opponent;
	if (!Scenario.bDrawOnFirstTurn)
	{
		SideRef(FirstSide).bSkipDraw = true;
	}
	if (EffectRuntime)
	{
		EffectRuntime->OnDuelStart();
	}
	Log(FString::Printf(TEXT("Scenario '%s' begins. %s"), *Scenario.Id,
		Scenario.TurnLimit > 0 ? *FString::Printf(TEXT("Turn limit: %d."), Scenario.TurnLimit) : TEXT("")), TEXT("turn"));
	StartTurn(FirstSide);
	if (FirstSide == EDuelOwner::Opponent && !bWinnerSet)
	{
		bAiTurnPending = true;
		LastAiMessage = FString::Printf(TEXT("%s is taking their turn."), *OpponentDisplayName);
	}
	return true;
}

int32 FDuelEngine::GetScenarioTurnsRemaining() const
{
	if (!bScenarioActive || ActiveScenario.TurnLimit <= 0)
	{
		return 0;
	}
	return FMath::Max(0, ActiveScenario.TurnLimit - ScenarioPlayerTurns);
}

bool FDuelEngine::CheckScenarioTimeout(float ElapsedSeconds)
{
	if (!bScenarioActive || bWinnerSet)
	{
		return false;
	}
	ScenarioElapsedSeconds = FMath::Max(ScenarioElapsedSeconds, ElapsedSeconds);
	if (ActiveScenario.TimeLimitSeconds > 0.f && ScenarioElapsedSeconds > ActiveScenario.TimeLimitSeconds)
	{
		EndDuel(EDuelOwner::Opponent, TEXT("The time limit was reached."));
		return true;
	}
	return false;
}

bool FDuelEngine::IsScenarioObjectiveComplete() const
{
	if (!bScenarioActive || !ActiveScenario.HasObjective())
	{
		return false;
	}
	const FDuelScenario& S = ActiveScenario;
	if (S.RequiredBattleDamage > 0 && ResultStats.BattleDamageDealt < S.RequiredBattleDamage) return false;
	if (S.RequiredMonstersDestroyed > 0 && ResultStats.MonstersDestroyedByBattle < S.RequiredMonstersDestroyed) return false;
	if (S.RequiredFusionSummons > 0 && ResultStats.FusionSummons < S.RequiredFusionSummons) return false;
	if (S.RequiredRitualSummons > 0 && ResultStats.RitualSummons < S.RequiredRitualSummons) return false;
	if (S.RequiredSpecialSummons > 0 && ResultStats.SpecialSummons < S.RequiredSpecialSummons) return false;
	if (S.RequiredSpellsActivated > 0 && ResultStats.SpellsActivated < S.RequiredSpellsActivated) return false;
	if (S.RequiredTrapsActivated > 0 && ResultStats.TrapsActivated < S.RequiredTrapsActivated) return false;
	return true;
}

void FDuelEngine::CheckScenarioCompletion()
{
	if (!bScenarioActive || bWinnerSet || bScenarioObjectiveComplete)
	{
		return;
	}
	if (IsScenarioObjectiveComplete())
	{
		bScenarioObjectiveComplete = true;
		EndDuel(EDuelOwner::Player, TEXT("The scenario objective was completed."));
	}
}

void FDuelEngine::Surrender()
{
	if (!bWinnerSet)
	{
		EndDuel(EDuelOwner::Opponent, TEXT("You surrendered."));
	}
}

// ---------------------------------------------------------------------------
// Ante
// ---------------------------------------------------------------------------

void FDuelEngine::ConfigureAnte(bool bEnabled, int32 InPlayerCardId, int32 InOpponentCardId)
{
	AnteState = FDuelAnteState();
	AnteState.bEnabled = bEnabled;
	if (bEnabled)
	{
		AnteState.PlayerCardId = InPlayerCardId;
		AnteState.OpponentCardId = InOpponentCardId;
		AnteState.bPlayerSelected = InPlayerCardId > 0;
		AnteState.bOpponentSelected = InOpponentCardId > 0;
	}
}

bool FDuelEngine::IsCardInSideDeck(EDuelOwner Side, int32 CardId) const
{
	for (const FDuelCard& Card : SideRef(Side).Deck)
	{
		if (Card.Data.Id == CardId)
		{
			return true;
		}
	}
	return false;
}

bool FDuelEngine::SelectAnteCard(EDuelOwner Side, int32 CardId, FString& OutError)
{
	if (!AnteState.bEnabled)
	{
		OutError = TEXT("Ante is not enabled for this duel.");
		return false;
	}
	if (CardId <= 0)
	{
		OutError = TEXT("Choose a valid card to ante.");
		return false;
	}
	if (Database && !Database->FindCard(CardId))
	{
		OutError = FString::Printf(TEXT("Card %d does not exist."), CardId);
		return false;
	}

	int32 FoundUid = 0;
	for (const FDuelCard& Card : SideRef(Side).Deck)
	{
		if (Card.Data.Id == CardId)
		{
			FoundUid = Card.Uid;
			break;
		}
	}
	if (bStarted && FoundUid == 0)
	{
		OutError = FString::Printf(TEXT("Card %d is not in that duelist's Deck."), CardId);
		return false;
	}

	if (Side == EDuelOwner::Player)
	{
		AnteState.PlayerCardId = CardId;
		AnteState.PlayerCardUid = FoundUid;
		AnteState.bPlayerSelected = true;
	}
	else
	{
		AnteState.OpponentCardId = CardId;
		AnteState.OpponentCardUid = FoundUid;
		AnteState.bOpponentSelected = true;
	}
	return true;
}

bool FDuelEngine::FinalizeAnteSelection(FString& OutError)
{
	if (!AnteState.bEnabled)
	{
		OutError = TEXT("Ante is not enabled for this duel.");
		return false;
	}
	if (!AnteState.bPlayerSelected || !AnteState.bOpponentSelected)
	{
		OutError = TEXT("Both duelists must select an ante card.");
		return false;
	}
	return true;
}

void FDuelEngine::ResolveAnteOnDuelEnd()
{
	if (!AnteState.bEnabled)
	{
		return;
	}
	if (!bStarted || TurnNumber <= 0)
	{
		AnteState.Note = TEXT("Ante was not resolved because the duel did not start.");
		return;
	}
	AnteState.bTransferred = false;
	AnteState.bPlayerWon = false;
	AnteState.WinnerCardId = 0;
	AnteState.LoserCardId = 0;

	if (ResultStats.bDraw)
	{
		AnteState.Note = TEXT("Ante cards were returned because the duel was a draw.");
	}
	else if (AnteState.bPlayerSelected && AnteState.bOpponentSelected)
	{
		const bool bPlayerWon = Winner == EDuelOwner::Player;
		AnteState.bTransferred = true;
		AnteState.bPlayerWon = bPlayerWon;
		AnteState.WinnerCardId = bPlayerWon ? AnteState.OpponentCardId : AnteState.PlayerCardId;
		AnteState.LoserCardId = bPlayerWon ? AnteState.PlayerCardId : AnteState.OpponentCardId;
		AnteState.Note = bPlayerWon
			? FString::Printf(TEXT("You win the ante card %d."), AnteState.WinnerCardId)
			: FString::Printf(TEXT("You lose the ante card %d."), AnteState.LoserCardId);
	}
	else
	{
		AnteState.Note = TEXT("Ante was not transferred because a selection was missing.");
	}
	if (AnteResultHook)
	{
		AnteResultHook(AnteState);
	}
}

// ---------------------------------------------------------------------------
// Result statistics
// ---------------------------------------------------------------------------

void FDuelEngine::FinalizeResultStats()
{
	ResultStats.Turns = TurnNumber;
	ResultStats.PlayerLp = Player.LP;
	ResultStats.OpponentLp = Opponent.LP;
	ResultStats.bPlayerWon = bWinnerSet && Winner == EDuelOwner::Player;
	ResultStats.bDraw = bWinnerSet && Player.LP <= 0 && Opponent.LP <= 0;
	ResultStats.OpponentId = OpponentCharacterId;
	ResultStats.bWentSecond = bScenarioActive && !ActiveScenario.bPlayerGoesFirst;
}

namespace
{
	int32 SelfTestCountOwnedCards(const FDuelSide& First, const FDuelSide& Second, EDuelOwner Owner);
}

bool FDuelEngine::CheckDuelStateInvariants(int32 ExpectedPlayerCards, int32 ExpectedOpponentCards,
	TArray<FString>& OutErrors) const
{
	const int32 StartErrorCount = OutErrors.Num();
	auto AddError = [&OutErrors](const FString& Message)
	{
		OutErrors.Add(Message);
	};

	if (Player.Monsters.Num() != 5 || Opponent.Monsters.Num() != 5)
	{
		AddError(TEXT("Monster Zone arrays must always contain five slots."));
	}
	if (Player.Spells.Num() != 5 || Opponent.Spells.Num() != 5)
	{
		AddError(TEXT("Spell & Trap Zone arrays must always contain five slots."));
	}
	if (Player.LP < 0 || Opponent.LP < 0)
	{
		AddError(FString::Printf(TEXT("Life Points went negative (player %d, opponent %d)."), Player.LP, Opponent.LP));
	}
	if (bWinnerSet)
	{
		if (Phase != EDuelPhase::Over)
		{
			AddError(TEXT("A finished duel must be in the Over phase."));
		}
	}
	else if (Phase == EDuelPhase::Over)
	{
		AddError(TEXT("The Over phase is only legal after a winner is set."));
	}
	if (bStarted && TurnNumber <= 0)
	{
		AddError(TEXT("A started duel must have a positive turn number."));
	}
	if (ActiveSide != EDuelOwner::Player && ActiveSide != EDuelOwner::Opponent)
	{
		AddError(TEXT("Active side is not a valid duelist."));
	}
	if (bAwaitingDiscard && Player.Hand.Num() <= HandLimit)
	{
		AddError(TEXT("A discard is pending even though the player is at or below the hand limit."));
	}
	if (HasPendingChoice())
	{
		AddError(TEXT("A pending choice was left unanswered after a completed step."));
	}
	if (IsChainOpen())
	{
		AddError(FString::Printf(TEXT("A chain was left open (%d link(s))."), ChainLinks.Num()));
	}

	TSet<int32> SeenUids;
	TArray<int32> EquipTargets;
	TArray<int32> TiedTargets;

	auto CheckCard = [&](const FDuelCard& Card, EDuelOwner Side, const TCHAR* Zone,
		bool bFieldZone, bool bExtraZone, bool bMainDeckZone)
	{
		const TCHAR* SideName = Side == EDuelOwner::Player ? TEXT("Player") : TEXT("Opponent");
		if (Card.Uid <= 0)
		{
			AddError(FString::Printf(TEXT("%s %s contains a card with no instance uid."), SideName, Zone));
			return;
		}
		if (Card.Data.Id <= 0)
		{
			AddError(FString::Printf(TEXT("%s %s uid %d has no card id."), SideName, Zone, Card.Uid));
		}
		if (!bFieldZone && Card.Owner != Side)
		{
			AddError(FString::Printf(TEXT("%s %s uid %d is owned by the other duelist."), SideName, Zone, Card.Uid));
		}
		if (Card.Controller != EDuelOwner::Player && Card.Controller != EDuelOwner::Opponent)
		{
			AddError(FString::Printf(TEXT("%s %s uid %d has an invalid controller."), SideName, Zone, Card.Uid));
		}
		if (SeenUids.Contains(Card.Uid))
		{
			AddError(FString::Printf(TEXT("Duplicate card instance uid %d."), Card.Uid));
		}
		else
		{
			SeenUids.Add(Card.Uid);
		}
		if (bExtraZone && !Card.bExtra)
		{
			AddError(FString::Printf(TEXT("Extra Deck uid %d is not marked as an Extra Deck card."), Card.Uid));
		}
		if (bMainDeckZone && Card.bExtra)
		{
			AddError(FString::Printf(TEXT("Main Deck uid %d is marked as an Extra Deck card."), Card.Uid));
		}
		if (Card.Counters < 0 || Card.AttacksUsed < 0 || Card.ExtraAttacks < 0)
		{
			AddError(FString::Printf(TEXT("Card uid %d has a negative counter/attack value."), Card.Uid));
		}
		if (Card.EquippedToUid < 0 || Card.TiedToUid < 0)
		{
			AddError(FString::Printf(TEXT("Card uid %d has a negative equipment/tie target."), Card.Uid));
		}
		if (Card.SummonedTurn > TurnNumber || Card.PositionChangedTurn > TurnNumber
			|| Card.SetTurn > TurnNumber || Card.EffectUsedTurn > TurnNumber)
		{
			AddError(FString::Printf(TEXT("Card uid %d has a turn stamp from the future."), Card.Uid));
		}
		if (Card.EquippedToUid != 0)
		{
			EquipTargets.Add(Card.EquippedToUid);
		}
		if (Card.TiedToUid != 0)
		{
			TiedTargets.Add(Card.TiedToUid);
		}
	};

	for (EDuelOwner Side : { EDuelOwner::Player, EDuelOwner::Opponent })
	{
		const FDuelSide& State = SideRef(Side);
		const TCHAR* SideName = Side == EDuelOwner::Player ? TEXT("Player") : TEXT("Opponent");

		auto VisitArray = [&](const TArray<FDuelCard>& Cards, const TCHAR* Zone,
			bool bExtraZone, bool bMainDeckZone)
		{
			for (const FDuelCard& Card : Cards)
			{
				if (Card.Uid <= 0)
				{
					AddError(FString::Printf(TEXT("%s %s contains an invalid card entry."), SideName, Zone));
					continue;
				}
				CheckCard(Card, Side, Zone, false, bExtraZone, bMainDeckZone);
			}
		};

		VisitArray(State.Deck, TEXT("Deck"), false, true);
		VisitArray(State.Hand, TEXT("Hand"), false, false);
		VisitArray(State.Graveyard, TEXT("Graveyard"), false, false);
		VisitArray(State.Banished, TEXT("Banished"), false, false);
		VisitArray(State.Extra, TEXT("Extra Deck"), true, false);

		for (int32 I = 0; I < State.Monsters.Num(); ++I)
		{
			const FDuelCard& Card = State.Monsters[I];
			if (!Card.IsValid())
			{
				continue;
			}
			CheckCard(Card, Side, TEXT("Monster Zone"), true, false, false);
			if (!Card.IsMonster())
			{
				AddError(FString::Printf(TEXT("%s Monster Zone %d contains a non-monster card uid %d."),
					SideName, I, Card.Uid));
			}
		}
		for (int32 I = 0; I < State.Spells.Num(); ++I)
		{
			const FDuelCard& Card = State.Spells[I];
			if (!Card.IsValid())
			{
				continue;
			}
			CheckCard(Card, Side, TEXT("Spell & Trap Zone"), true, false, false);
			if (!Card.IsSpell() && !Card.IsTrap())
			{
				AddError(FString::Printf(TEXT("%s Spell & Trap Zone %d contains a non-Spell/Trap uid %d."),
					SideName, I, Card.Uid));
			}
		}
		if (State.Field.IsValid())
		{
			CheckCard(State.Field, Side, TEXT("Field Zone"), true, false, false);
			if (!State.Field.IsSpell())
			{
				AddError(FString::Printf(TEXT("%s Field Zone contains a non-Spell uid %d."), SideName, State.Field.Uid));
			}
		}
	}

	for (int32 Uid : EquipTargets)
	{
		if (!SeenUids.Contains(Uid))
		{
			AddError(FString::Printf(TEXT("Equipment points at missing card uid %d."), Uid));
		}
	}
	for (int32 Uid : TiedTargets)
	{
		if (!SeenUids.Contains(Uid))
		{
			AddError(FString::Printf(TEXT("Card tie points at missing card uid %d."), Uid));
		}
	}

	if (ExpectedPlayerCards >= 0)
	{
		const int32 Actual = SelfTestCountOwnedCards(Player, Opponent, EDuelOwner::Player);
		if (Actual != ExpectedPlayerCards)
		{
			AddError(FString::Printf(TEXT("Player card count changed from %d to %d."), ExpectedPlayerCards, Actual));
		}
	}
	if (ExpectedOpponentCards >= 0)
	{
		const int32 Actual = SelfTestCountOwnedCards(Player, Opponent, EDuelOwner::Opponent);
		if (Actual != ExpectedOpponentCards)
		{
			AddError(FString::Printf(TEXT("Opponent card count changed from %d to %d."), ExpectedOpponentCards, Actual));
		}
	}

	return OutErrors.Num() == StartErrorCount;
}

namespace
{
	constexpr int32 SelfTestMaxIterations = 10000;
	constexpr int32 SelfTestMaxSteps = 240;
	constexpr int32 SelfTestMaxTurns = 120;

	FString SelfTestJoinErrors(const TArray<FString>& Errors)
	{
		return Errors.Num() > 0 ? FString::Join(Errors, TEXT(" | ")) : FString();
	}

	bool SelfTestLoadJsonObject(const FString& Path, TSharedPtr<FJsonObject>& OutObject, FString& OutError)
	{
		OutObject.Reset();
		FString Raw;
		if (!FFileHelper::LoadFileToString(Raw, *Path))
		{
			OutError = FString::Printf(TEXT("cannot read %s"), *Path);
			return false;
		}
		TSharedPtr<FJsonValue> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid() || !Root->AsObject().IsValid())
		{
			OutError = FString::Printf(TEXT("invalid JSON object in %s"), *Path);
			return false;
		}
		OutObject = Root->AsObject();
		return true;
	}

	FString SelfTestReadString(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, const FString& Default = FString())
	{
		FString Value;
		if (Object.IsValid() && Object->TryGetStringField(Field, Value))
		{
			return Value;
		}
		return Default;
	}

	int32 SelfTestReadInt(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, int32 Default = 0)
	{
		int32 Value = Default;
		if (Object.IsValid())
		{
			Object->TryGetNumberField(Field, Value);
		}
		return Value;
	}

	bool SelfTestReadBool(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, bool bDefault = false)
	{
		bool bValue = bDefault;
		if (Object.IsValid())
		{
			Object->TryGetBoolField(Field, bValue);
		}
		return bValue;
	}

	void SelfTestReadIntArray(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, TArray<int32>& OutValues)
	{
		OutValues.Reset();
		const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
		if (!Object.IsValid() || !Object->TryGetArrayField(Field, Values) || !Values)
		{
			return;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Values)
		{
			if (Value.IsValid() && Value->Type == EJson::Number)
			{
				OutValues.Add(static_cast<int32>(Value->AsNumber()));
			}
		}
	}

	int32 SelfTestCountOwnedCards(const FDuelSide& First, const FDuelSide& Second, EDuelOwner Owner)
	{
		int32 Count = 0;
		auto CountSide = [&Count, Owner](const FDuelSide& Side)
		{
			auto CountArray = [&Count, Owner](const TArray<FDuelCard>& Cards)
			{
				for (const FDuelCard& Card : Cards)
				{
					if (Card.IsValid() && Card.Owner == Owner)
					{
						++Count;
					}
				}
			};
			CountArray(Side.Deck);
			CountArray(Side.Hand);
			CountArray(Side.Graveyard);
			CountArray(Side.Banished);
			CountArray(Side.Extra);
			for (const FDuelCard& Card : Side.Monsters)
			{
				if (Card.IsValid() && Card.Owner == Owner)
				{
					++Count;
				}
			}
			for (const FDuelCard& Card : Side.Spells)
			{
				if (Card.IsValid() && Card.Owner == Owner)
				{
					++Count;
				}
			}
			if (Side.Field.IsValid() && Side.Field.Owner == Owner)
			{
				++Count;
			}
		};
		CountSide(First);
		CountSide(Second);
		return Count;
	}

	bool SelfTestHasWinCondition(UCardDatabaseSubsystem* Database, const TArray<int32>& CardIds)
	{
		if (!Database)
		{
			return false;
		}
		for (int32 CardId : CardIds)
		{
			const FCardRecord* Card = Database->FindCard(CardId);
			if (!Card)
			{
				continue;
			}
			if (Card->IsMonster() && Card->Atk > 0)
			{
				return true;
			}
			if (Card->Name.Contains(TEXT("Exodia"), ESearchCase::IgnoreCase)
				|| Card->Name.Contains(TEXT("Final Countdown"), ESearchCase::IgnoreCase)
				|| Card->Name.Contains(TEXT("Destiny Board"), ESearchCase::IgnoreCase)
				|| Card->Name.Contains(TEXT("Last Turn"), ESearchCase::IgnoreCase))
			{
				return true;
			}
			if (!Card->IsMonster()
				&& (Card->Description.Contains(TEXT("inflict"), ESearchCase::IgnoreCase)
					|| Card->Description.Contains(TEXT("damage to your opponent"), ESearchCase::IgnoreCase)
					|| Card->Description.Contains(TEXT("damage to both players"), ESearchCase::IgnoreCase)))
			{
				return true;
			}
		}
		return false;
	}

	FDuelScenario SelfTestBuildPuzzleScenario(const TSharedPtr<FJsonObject>& Puzzle)
	{
		FDuelScenario Scenario;
		Scenario.Id = SelfTestReadString(Puzzle, TEXT("id"));
		Scenario.Name = SelfTestReadString(Puzzle, TEXT("title"));
		Scenario.Mode = TEXT("puzzle");
		Scenario.Seed = SelfTestReadInt(Puzzle, TEXT("seed"));
		Scenario.TurnLimit = SelfTestReadInt(Puzzle, TEXT("turn_limit"));
		Scenario.TimeLimitSeconds = static_cast<float>(SelfTestReadInt(Puzzle, TEXT("time_limit")));
		Scenario.bPlayerGoesFirst = true;
		Scenario.bDrawOnFirstTurn = false;

		auto ReadSide = [&](const TCHAR* SideField, int32& OutLp, TArray<int32>& Hand,
			TArray<int32>& Deck, TArray<int32>& Graveyard, TArray<int32>& Extra,
			TArray<FDuelScenarioCard>& OutField)
		{
			const TSharedPtr<FJsonObject>* SideObject = nullptr;
			if (!Puzzle.IsValid() || !Puzzle->TryGetObjectField(SideField, SideObject)
				|| !SideObject || !SideObject->IsValid())
			{
				return;
			}
			const TSharedPtr<FJsonObject> Side = *SideObject;
			OutLp = SelfTestReadInt(Side, TEXT("lp"), OutLp);
			SelfTestReadIntArray(Side, TEXT("hand"), Hand);
			SelfTestReadIntArray(Side, TEXT("deck"), Deck);
			SelfTestReadIntArray(Side, TEXT("graveyard"), Graveyard);
			SelfTestReadIntArray(Side, TEXT("extra"), Extra);

			const TArray<TSharedPtr<FJsonValue>>* FieldValues = nullptr;
			if (Side->TryGetArrayField(TEXT("field"), FieldValues) && FieldValues)
			{
				for (int32 I = 0; I < FieldValues->Num(); ++I)
				{
					const TSharedPtr<FJsonValue>& Value = (*FieldValues)[I];
					const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
					if (!Entry.IsValid())
					{
						continue;
					}
					FDuelScenarioCard Spec;
					Spec.CardId = SelfTestReadInt(Entry, TEXT("card_id"));
					Spec.Zone = EDuelZone::Monster;
					Spec.ZoneIndex = I;
					Spec.bFaceDown = !SelfTestReadBool(Entry, TEXT("face_up"), true);
					Spec.bDefense = SelfTestReadString(Entry, TEXT("position"), TEXT("attack")).Equals(
						TEXT("defense"), ESearchCase::IgnoreCase);
					OutField.Add(Spec);
				}
			}

			const TArray<TSharedPtr<FJsonValue>>* SpellValues = nullptr;
			if (Side->TryGetArrayField(TEXT("spell_traps"), SpellValues) && SpellValues)
			{
				for (int32 I = 0; I < SpellValues->Num(); ++I)
				{
					const TSharedPtr<FJsonValue>& Value = (*SpellValues)[I];
					const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
					if (!Entry.IsValid())
					{
						continue;
					}
					FDuelScenarioCard Spec;
					Spec.CardId = SelfTestReadInt(Entry, TEXT("card_id"));
					Spec.Zone = EDuelZone::SpellTrap;
					Spec.ZoneIndex = I;
					Spec.bFaceDown = !SelfTestReadBool(Entry, TEXT("face_up"), false);
					OutField.Add(Spec);
				}
			}
		};

		ReadSide(TEXT("player"), Scenario.PlayerLp, Scenario.PlayerHand, Scenario.PlayerDeck,
			Scenario.PlayerGraveyard, Scenario.PlayerExtra, Scenario.PlayerField);
		ReadSide(TEXT("opponent_state"), Scenario.OpponentLp, Scenario.OpponentHand, Scenario.OpponentDeck,
			Scenario.OpponentGraveyard, Scenario.OpponentExtra, Scenario.OpponentField);
		return Scenario;
	}
}

FString FDuelEngine::RunSelfTest(UCardDatabaseSubsystem* Database, int32 Iterations)
{
	const double StartSeconds = FPlatformTime::Seconds();
	if (!Database)
	{
		return TEXT("Duel self-test: card database missing.");
	}

	// -DADuelSelfTest=N, on top of the legacy -DADuelSelfTest switch handled by
	// the HUD.  The static function also owns the parse so console callers and
	// the HUD call site share one implementation.
	int32 RequestedIterations = FMath::Clamp(Iterations, 1, SelfTestMaxIterations);
	FString CountText;
	const TCHAR* CommandLine = FCommandLine::Get();
	if (FParse::Value(CommandLine, TEXT("DADuelSelfTest="), CountText))
	{
		const int32 Parsed = FCString::Atoi(*CountText);
		if (Parsed > 0)
		{
			RequestedIterations = FMath::Clamp(Parsed, 1, SelfTestMaxIterations);
		}
	}

	// Load the A06/Judge list once; every gate duel and every deck audit below
	// shares the same ruleset.
	FDuelEngine RulesEngine(Database, 0);
	FString BanlistError;
	const bool bBanlistLoaded = RulesEngine.LoadDefaultBannedList(BanlistError);
	if (!bBanlistLoaded)
	{
		UE_LOG(LogDuelAcademyIsland, Warning,
			TEXT("[DeckLegality] banned_limited.json unavailable (%s); only copy/size checks are authoritative."),
			*BanlistError);
	}
	const FDuelBannedListRuleset GateBanned = RulesEngine.GetBannedList();

	int32 ConstructedTotal = 0;
	int32 ConstructedPass = 0;
	int32 PuzzleTotal = 0;
	int32 PuzzlePass = 0;

	auto AuditConstructedDeck = [&](const FString& DeckId, const TCHAR* Source,
		const TArray<int32>& Main, const TArray<int32>& Extra)
	{
		++ConstructedTotal;
		FDuelDeckValidationResult Result = RulesEngine.ValidateDeck(Main, Extra);
		TArray<int32> AllCards = Main;
		AllCards.Append(Extra);
		if (!SelfTestHasWinCondition(Database, AllCards))
		{
			Result.AddError(TEXT("no legal win condition (no attack-capable monster or damage/alternate-win card)"));
		}
		if (Result.bValid)
		{
			++ConstructedPass;
			UE_LOG(LogDuelAcademyIsland, Log,
				TEXT("[DeckLegality] PASS %s (%s, main=%d extra=%d)"), *DeckId, Source, Main.Num(), Extra.Num());
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("[DeckLegality] FAIL %s (%s, main=%d extra=%d): %s"),
				*DeckId, Source, Main.Num(), Extra.Num(), *SelfTestJoinErrors(Result.Errors));
		}
	};

	// Starter/shop decks owned by A06 and consumed by FDuelEngine::Start.
	for (const FStarterDeckDef& Deck : Database->GetDecks())
	{
		AuditConstructedDeck(Deck.Id, TEXT("Data/decks.json"), Deck.Cards, Deck.Extra);
	}

	// A06's saved player-deck catalogue (one deck per object in "decks").
	{
		const FString PlayerDeckPath = FPaths::ProjectContentDir() / TEXT("Data/Decks/player_decks.json");
		TSharedPtr<FJsonObject> Root;
		FString LoadError;
		if (SelfTestLoadJsonObject(PlayerDeckPath, Root, LoadError))
		{
			const TArray<TSharedPtr<FJsonValue>>* Decks = nullptr;
			if (Root->TryGetArrayField(TEXT("decks"), Decks) && Decks)
			{
				for (const TSharedPtr<FJsonValue>& Value : *Decks)
				{
					const TSharedPtr<FJsonObject> Entry = Value.IsValid() ? Value->AsObject() : nullptr;
					if (!Entry.IsValid())
					{
						continue;
					}
					TArray<int32> Main;
					TArray<int32> Extra;
					SelfTestReadIntArray(Entry, TEXT("main"), Main);
					SelfTestReadIntArray(Entry, TEXT("extra"), Extra);
					AuditConstructedDeck(SelfTestReadString(Entry, TEXT("id"), TEXT("player_deck")),
						TEXT("Data/Decks/player_decks.json"), Main, Extra);
				}
			}
		}
		else
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[DeckLegality] %s"), *LoadError);
		}
	}

	// A07/A06 opponent decks.  FDuelEngine itself does not register these in
	// UCardDatabaseSubsystem yet, so the gate reads the same files the opponent
	// loader ships and validates the lists the port will hand to the engine.
	{
		const FString OpponentDeckDir = FPaths::ProjectContentDir() / TEXT("Data/Opponents/decks");
		TArray<FString> Files;
		IFileManager::Get().FindFiles(Files, *OpponentDeckDir, TEXT("*.json"));
		Files.Sort();
		for (const FString& File : Files)
		{
			const FString Path = OpponentDeckDir / File;
			TSharedPtr<FJsonObject> Root;
			FString LoadError;
			if (!SelfTestLoadJsonObject(Path, Root, LoadError))
			{
				++ConstructedTotal;
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[DeckLegality] FAIL %s: %s"), *File, *LoadError);
				continue;
			}
			TArray<int32> Main;
			TArray<int32> Extra;
			SelfTestReadIntArray(Root, TEXT("cards"), Main);
			if (Main.Num() == 0)
			{
				SelfTestReadIntArray(Root, TEXT("main"), Main);
			}
			SelfTestReadIntArray(Root, TEXT("extra"), Extra);
			AuditConstructedDeck(SelfTestReadString(Root, TEXT("id"), FPaths::GetBaseFilename(File)),
				TEXT("Data/Opponents/decks"), Main, Extra);
		}
	}

	// Puzzle boards are fixed scenarios, not 40-card constructed decks.  They
	// are still checked for known ids, copy/limit legality and a legal win
	// condition, then actually constructed through StartScenario.
	{
		const FString PuzzleDir = FPaths::ProjectContentDir() / TEXT("Data/Puzzles");
		TArray<FString> Files;
		IFileManager::Get().FindFiles(Files, *PuzzleDir, TEXT("P*.json"));
		Files.Sort();
		FDuelEngine PuzzleProbe(Database, 1);
		PuzzleProbe.SetBannedList(GateBanned);
		PuzzleProbe.SetAutoAnswerAllChoices(true);
		for (const FString& File : Files)
		{
			++PuzzleTotal;
			TSharedPtr<FJsonObject> Root;
			FString LoadError;
			TArray<FString> Errors;
			if (!SelfTestLoadJsonObject(PuzzleDir / File, Root, LoadError))
			{
				Errors.Add(LoadError);
			}
			else
			{
				const FDuelScenario Scenario = SelfTestBuildPuzzleScenario(Root);
				TArray<int32> PlayerIds = Scenario.PlayerHand;
				PlayerIds.Append(Scenario.PlayerDeck);
				PlayerIds.Append(Scenario.PlayerGraveyard);
				PlayerIds.Append(Scenario.PlayerExtra);
				for (const FDuelScenarioCard& Spec : Scenario.PlayerField)
				{
					PlayerIds.Add(Spec.CardId);
				}
				TArray<int32> AllIds = PlayerIds;
				AllIds.Append(Scenario.OpponentHand);
				AllIds.Append(Scenario.OpponentDeck);
				AllIds.Append(Scenario.OpponentGraveyard);
				AllIds.Append(Scenario.OpponentExtra);
				for (const FDuelScenarioCard& Spec : Scenario.OpponentField)
				{
					AllIds.Add(Spec.CardId);
				}

				TMap<int32, int32> Counts;
				for (int32 CardId : AllIds)
				{
					if (CardId <= 0)
					{
						Errors.Add(TEXT("board contains an invalid card id"));
						continue;
					}
					if (!Database->FindCard(CardId))
					{
						Errors.Add(FString::Printf(TEXT("unknown card %d"), CardId));
					}
					++Counts.FindOrAdd(CardId);
				}
				for (const TPair<int32, int32>& Pair : Counts)
				{
					const int32 Limit = FMath::Min(GateBanned.GetLimit(Pair.Key), GateBanned.MaxCopies);
					if (Limit == 0)
					{
						Errors.Add(FString::Printf(TEXT("banned card %d"), Pair.Key));
					}
					else if (Pair.Value > Limit)
					{
						Errors.Add(FString::Printf(TEXT("card %d has %d copies; limit %d"), Pair.Key, Pair.Value, Limit));
					}
				}
				if (Scenario.PlayerExtra.Num() > GateBanned.MaxExtra)
				{
					Errors.Add(FString::Printf(TEXT("player Extra Deck has %d cards; limit %d"),
						Scenario.PlayerExtra.Num(), GateBanned.MaxExtra));
				}
				if (Scenario.OpponentExtra.Num() > GateBanned.MaxExtra)
				{
					Errors.Add(FString::Printf(TEXT("opponent Extra Deck has %d cards; limit %d"),
						Scenario.OpponentExtra.Num(), GateBanned.MaxExtra));
				}
				// Fixed puzzle boards may win through the opponent's Graveyard
				// (Autonomous Action Unit, Premature Burial, etc.), so the
				// player-only win-condition heuristic is not meaningful here.
				// A07's PuzzleSelfTest replays every authored solution instead.
				if (Errors.Num() == 0)
				{
					FString StartError;
					if (!PuzzleProbe.StartScenario(Scenario, StartError))
					{
						Errors.Add(FString::Printf(TEXT("StartScenario failed: %s"), *StartError));
					}
					else
					{
						TArray<FString> StateErrors;
						PuzzleProbe.CheckDuelStateInvariants(-1, -1, StateErrors);
						Errors.Append(StateErrors);
					}
				}
			}

			if (Errors.Num() == 0)
			{
				++PuzzlePass;
				UE_LOG(LogDuelAcademyIsland, Log, TEXT("[PuzzleLegality] PASS %s"), *File);
			}
			else
			{
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[PuzzleLegality] FAIL %s: %s"),
					*File, *SelfTestJoinErrors(Errors));
			}
		}
	}

	const TCHAR* Starters[] = { TEXT("fire"), TEXT("water"), TEXT("wind") };
	int32 PlayerWins = 0;
	int32 OpponentWins = 0;
	int32 Stalls = 0;
	int32 TotalTurns = 0;
	int32 GamesWithErrors = 0;
	int32 DeckGameFailures = 0;
	TArray<FString> FailureDetails;

	for (int32 Iteration = 0; Iteration < RequestedIterations; ++Iteration)
	{
		const int32 Seed = 1200 + Iteration * 37;
		const FString PlayerDeckId = Starters[Iteration % 3];
		FDuelEngine Duel(Database, Seed);
		Duel.SetBannedList(GateBanned);
		Duel.SetAutoAnswerAllChoices(true);

		TArray<FString> Errors;
		const FStarterDeckDef* PlayerDeck = Database->FindDeck(PlayerDeckId);
		const FStarterDeckDef* OpponentDeck = Database->FindDeck(TEXT("jaden"));
		if (!PlayerDeck || !OpponentDeck)
		{
			Errors.Add(TEXT("gate starter deck is missing from the card database"));
		}
		else
		{
			const FDuelDeckValidationResult PlayerValid = Duel.ValidateDeck(PlayerDeck->Cards, PlayerDeck->Extra);
			const FDuelDeckValidationResult OpponentValid = Duel.ValidateDeck(OpponentDeck->Cards, OpponentDeck->Extra);
			if (!PlayerValid.bValid || !OpponentValid.bValid)
			{
				++DeckGameFailures;
				if (!PlayerValid.bValid)
				{
					Errors.Add(FString::Printf(TEXT("player deck '%s': %s"), *PlayerDeckId,
						*SelfTestJoinErrors(PlayerValid.Errors)));
				}
				if (!OpponentValid.bValid)
				{
					Errors.Add(FString::Printf(TEXT("opponent deck 'jaden': %s"),
						*SelfTestJoinErrors(OpponentValid.Errors)));
				}
			}
		}

		Duel.Start(PlayerDeckId, TEXT("jaden"));
		if (!Duel.IsStarted())
		{
			Errors.Add(TEXT("duel did not start"));
		}

		const int32 InitialPlayerCards = SelfTestCountOwnedCards(
			Duel.GetSide(EDuelOwner::Player), Duel.GetSide(EDuelOwner::Opponent), EDuelOwner::Player);
		const int32 InitialOpponentCards = SelfTestCountOwnedCards(
			Duel.GetSide(EDuelOwner::Player), Duel.GetSide(EDuelOwner::Opponent), EDuelOwner::Opponent);

		EDuelPhase LastPhase = Duel.GetPhase();
		int32 LastTurn = Duel.GetTurnNumber();
		auto PhaseName = [](EDuelPhase InPhase) -> FString
		{
			switch (InPhase)
			{
			case EDuelPhase::Main1: return TEXT("Main1");
			case EDuelPhase::Battle: return TEXT("Battle");
			case EDuelPhase::Main2: return TEXT("Main2");
			case EDuelPhase::Over: return TEXT("Over");
			default: return TEXT("Unknown");
			}
		};
		auto ObservePhase = [&]()
		{
			const EDuelPhase CurrentPhase = Duel.GetPhase();
			const int32 CurrentTurn = Duel.GetTurnNumber();
			const bool bTurnAdvanced = CurrentTurn > LastTurn;
			bool bLegal = false;
			if (CurrentPhase == LastPhase && CurrentTurn == LastTurn)
			{
				bLegal = true;
			}
			else if (Duel.IsOver() && CurrentPhase == EDuelPhase::Over)
			{
				bLegal = true;
			}
			else if (bTurnAdvanced)
			{
				bLegal = CurrentPhase == EDuelPhase::Main1;
			}
			else
			{
				switch (LastPhase)
				{
				case EDuelPhase::Main1:
					bLegal = CurrentPhase == EDuelPhase::Battle || CurrentPhase == EDuelPhase::Main2;
					break;
				case EDuelPhase::Battle:
					bLegal = CurrentPhase == EDuelPhase::Main2;
					break;
				default:
					bLegal = false;
					break;
				}
			}
			if (!bLegal)
			{
				Errors.Add(FString::Printf(TEXT("illegal phase transition turn %d: %s -> %s"),
					CurrentTurn, *PhaseName(LastPhase), *PhaseName(CurrentPhase)));
			}
			LastPhase = CurrentPhase;
			LastTurn = CurrentTurn;
		};

		auto AnswerPending = [&]()
		{
			int32 Guard = 0;
			while (Duel.HasPendingChoice() && Guard++ < 64)
			{
				FString ChoiceError;
				if (!Duel.AutoAnswerPendingChoice(&ChoiceError))
				{
					Errors.Add(FString::Printf(TEXT("could not answer pending choice: %s"), *ChoiceError));
					break;
				}
			}
			if (Duel.HasPendingChoice())
			{
				Errors.Add(TEXT("pending choice remained after auto-answer"));
			}
		};

		auto FlushChain = [&]()
		{
			if (Duel.IsChainOpen())
			{
				Errors.Add(FString::Printf(TEXT("open chain of %d link(s) left after a step"), Duel.GetChainLinks().Num()));
				FString ChainError;
				Duel.ResolveChain(ChainError);
			}
		};

		auto CheckState = [&]()
		{
			TArray<FString> StateErrors;
			Duel.CheckDuelStateInvariants(InitialPlayerCards, InitialOpponentCards, StateErrors);
			Errors.Append(StateErrors);
		};

		CheckState();
		ObservePhase();
		int32 Steps = 0;
		while (!Duel.IsOver() && Steps < SelfTestMaxSteps && Duel.GetTurnNumber() <= SelfTestMaxTurns)
		{
			++Steps;
			if (Duel.GetActiveSide() == EDuelOwner::Player)
			{
				Duel.AiPlayMainPhase();
				AnswerPending();
				FlushChain();
				ObservePhase();
				CheckState();
				if (!Duel.IsOver())
				{
					Duel.Phase = EDuelPhase::Battle;
					ObservePhase();
					Duel.AiPlayBattlePhase();
					AnswerPending();
					FlushChain();
					ObservePhase();
					CheckState();
				}
				if (Duel.IsOver())
				{
					break;
				}
				Duel.Phase = EDuelPhase::Main2;
				ObservePhase();
				if (Duel.Player.Hand.Num() > HandLimit)
				{
					Duel.bAwaitingDiscard = true;
					while (Duel.bAwaitingDiscard && Duel.Player.Hand.Num() > HandLimit)
					{
						FString DiscardError;
						if (!Duel.DiscardFromHand(Duel.Player.Hand[0].Uid, DiscardError))
						{
							Errors.Add(FString::Printf(TEXT("hand-limit discard failed: %s"), *DiscardError));
							break;
						}
					}
				}
				Duel.bAiTurnPending = true;
				Duel.RunOpponentTurn();
			}
			else
			{
				Duel.bAiTurnPending = true;
				Duel.RunOpponentTurn();
			}
			AnswerPending();
			FlushChain();
			ObservePhase();
			CheckState();
		}

		TotalTurns += Duel.GetTurnNumber();
		if (!Duel.IsOver())
		{
			++Stalls;
			Errors.Add(FString::Printf(TEXT("stalled after %d step(s), turn %d"), Steps, Duel.GetTurnNumber()));
		}
		else if (Duel.GetWinner() == EDuelOwner::Player)
		{
			++PlayerWins;
		}
		else
		{
			++OpponentWins;
		}

		if (Duel.IsOver())
		{
			if (Duel.GetResultStats().Turns != Duel.GetTurnNumber())
			{
				Errors.Add(TEXT("result stats did not finalize the turn count"));
			}
			if (Duel.GetResultStats().PlayerLp != Duel.GetSide(EDuelOwner::Player).LP
				|| Duel.GetResultStats().OpponentLp != Duel.GetSide(EDuelOwner::Opponent).LP)
			{
				Errors.Add(TEXT("result stats do not match the final Life Points"));
			}
		}
		AnswerPending();
		FlushChain();
		CheckState();

		if (Errors.Num() > 0)
		{
			++GamesWithErrors;
			if (FailureDetails.Num() < 40)
			{
				FailureDetails.Add(FString::Printf(TEXT("game %d (deck %s, seed %d, turn %d): %s"),
					Iteration, *PlayerDeckId, Seed, Duel.GetTurnNumber(), *SelfTestJoinErrors(Errors)));
			}
		}
	}

	for (const FString& Detail : FailureDetails)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[DuelSelfTest] %s"), *Detail);
	}
	if (GamesWithErrors > FailureDetails.Num())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("[DuelSelfTest] %d additional failing game(s) not shown."),
			GamesWithErrors - FailureDetails.Num());
	}

	const double ElapsedSeconds = FPlatformTime::Seconds() - StartSeconds;
	const bool bEnginePass = Stalls == 0 && GamesWithErrors == 0;
	return FString::Printf(
		TEXT("Duel self-test: %d iterations, %d player wins, %d opponent wins, %d stalls, average turns %.1f, ")
		TEXT("invariant failures %d, gate deck failures %d, deck audit %d/%d, puzzle audit %d/%d, elapsed %.1fs, RESULT %s"),
		RequestedIterations, PlayerWins, OpponentWins, Stalls,
		RequestedIterations > 0 ? static_cast<float>(TotalTurns) / RequestedIterations : 0.0f,
		GamesWithErrors, DeckGameFailures, ConstructedPass, ConstructedTotal, PuzzlePass, PuzzleTotal, ElapsedSeconds,
		bEnginePass ? TEXT("PASS") : TEXT("FAIL"));
}


namespace
{
	FAutoConsoleCommandWithWorldAndArgs GDADuelSelfTestCommand(
		TEXT("da.DuelSelfTest"),
		TEXT("Run N AI-vs-AI duels through the card engine and log the result summary. Usage: da.DuelSelfTest [iterations] (1-10000; default 24). Launch switch: -DADuelSelfTest=N"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (!World || !World->GetGameInstance())
			{
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("da.DuelSelfTest: no game instance."));
				return;
			}
			UCardDatabaseSubsystem* Database = World->GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>();
			const int32 Iterations = Args.Num() > 0 ? FMath::Clamp(FCString::Atoi(*Args[0]), 1, 10000) : 24;
			const FString Summary = FDuelEngine::RunSelfTest(Database, Iterations);
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Summary);
		}));
}
