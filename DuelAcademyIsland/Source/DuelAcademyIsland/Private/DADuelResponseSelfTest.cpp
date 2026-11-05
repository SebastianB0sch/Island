// Duel Academy Island - player response window and player-target checks.
//
// Scripted duels that pin down the interactive rules flow: the player's Set
// Traps / Quick-Play Spells are offered in response windows instead of firing
// on an AI heuristic, the opponent's turn suspends while a window is open,
// and legacy card handlers let the player choose targets and discards.  Run
// from -DADuelRulesSelfTest (FDuelRulesSelfTest::Run).

#include "DADuelResponseSelfTest.h"

#include "DADuelEngine.h"
#include "DACardRecords.h"

namespace
{
	using FCheck = TFunctionRef<void(bool, const FString&)>;

	FDuelScenario MakeScenario(const TCHAR* Id)
	{
		FDuelScenario S;
		S.Id = Id;
		S.Name = Id;
		S.PlayerLp = 8000;
		S.OpponentLp = 8000;
		S.PlayerDeck = TArray<int32> { 2, 3, 4, 5, 6, 7 };
		S.OpponentDeck = TArray<int32> { 7, 7, 7, 7, 7, 7 };
		S.bPlayerGoesFirst = true;
		S.bDrawOnFirstTurn = false;
		return S;
	}

	FDuelScenarioCard Mon(int32 Id, int32 Zone, bool bDef = false, bool bDown = false)
	{
		FDuelScenarioCard C;
		C.CardId = Id;
		C.Zone = EDuelZone::Monster;
		C.ZoneIndex = Zone;
		C.bDefense = bDef;
		C.bFaceDown = bDown;
		return C;
	}

	FDuelScenarioCard SetST(int32 Id, int32 Zone, bool bDown = true)
	{
		FDuelScenarioCard C;
		C.CardId = Id;
		C.Zone = EDuelZone::SpellTrap;
		C.ZoneIndex = Zone;
		C.bFaceDown = bDown;
		return C;
	}

	int32 UidIn(const TArray<FDuelCard>& Cards, int32 Id)
	{
		for (const FDuelCard& C : Cards)
		{
			if (C.IsValid() && C.Data.Id == Id)
			{
				return C.Uid;
			}
		}
		return 0;
	}

	bool InGrave(const FDuelEngine& D, EDuelOwner S, int32 Uid)
	{
		return D.GetSide(S).Graveyard.ContainsByPredicate([Uid](const FDuelCard& C) { return C.Uid == Uid; });
	}

	int32 OptionFor(const FDuelChoiceRequest* R, int32 CardUid)
	{
		if (!R)
		{
			return 0;
		}
		for (const FDuelChoiceOption& O : R->Options)
		{
			if (O.CardUid == CardUid)
			{
				return O.Id;
			}
		}
		return 0;
	}

	bool Answer(FDuelEngine& D, const TArray<int32>& Ids)
	{
		const FDuelChoiceRequest* R = D.GetPendingChoice();
		FString E;
		return R && D.AnswerChoice(R->RequestId, Ids, E);
	}

	bool IsResponse(const FDuelEngine& D)
	{
		const FDuelChoiceRequest* R = D.GetPendingChoice();
		return R && R->Side == EDuelOwner::Player && R->Type == EDuelChoiceType::ChainResponse;
	}

	int32 CountMonsters(const FDuelEngine& D, EDuelOwner Side)
	{
		int32 Count = 0;
		for (const FDuelCard& C : D.GetSide(Side).Monsters)
		{
			if (C.IsValid())
				++Count;
		}
		return Count;
	}

	int32 CountSpells(const FDuelEngine& D, EDuelOwner Side)
	{
		int32 Count = 0;
		for (const FDuelCard& C : D.GetSide(Side).Spells)
		{
			if (C.IsValid())
				++Count;
		}
		return Count;
	}

	void TestMirrorForceWindow(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 501);
		FDuelScenario S = MakeScenario(TEXT("RW_MIRROR"));
		S.PlayerField.Add(SetST(421, 0));
		S.OpponentField.Add(Mon(1, 0));
		S.OpponentField.Add(Mon(5, 1));
		FString E;
		D.StartScenario(S, E);
		const int32 Mf = UidIn(D.GetSide(EDuelOwner::Player).Spells, 421);
		const int32 Bewd = UidIn(D.GetSide(EDuelOwner::Opponent).Monsters, 1);
		D.EndTurn();
		Check(D.IsAwaitingAi(), TEXT("mirror: AI turn queued"));
		D.RunOpponentTurn();
		Check(IsResponse(D), TEXT("mirror: an attack opens a response window"));
		Check(D.IsOpponentTurnSuspended() && D.IsAwaitingAi(), TEXT("mirror: the opponent's turn is suspended"));
		Check(D.GetSide(EDuelOwner::Player).LP == 8000, TEXT("mirror: no damage before the answer"));
		const FDuelCard* MfCard = D.FindSpellTrap(Mf);
		Check(MfCard && !MfCard->bFaceUp, TEXT("mirror: Mirror Force did not auto-activate"));
		D.RunOpponentTurn();
		Check(IsResponse(D), TEXT("mirror: RunOpponentTurn waits while the window is open"));
		Check(OptionFor(D.GetPendingChoice(), Mf) != 0, TEXT("mirror: Mirror Force is offered"));
		Answer(D, { OptionFor(D.GetPendingChoice(), Mf) });
		Check(!D.FindMonster(Bewd), TEXT("mirror: Mirror Force destroys the attacker"));
		Check(CountMonsters(D, EDuelOwner::Opponent) == 0, TEXT("mirror: all attack-position monsters are destroyed"));
		Check(InGrave(D, EDuelOwner::Player, Mf), TEXT("mirror: Mirror Force goes to the Graveyard"));
		int Guard = 0;
		while (D.IsAwaitingAi() && Guard++ < 10)
		{
			D.RunOpponentTurn();
			if (D.HasPendingChoice())
				Answer(D, { FDuelEngine::ResponsePassOptionId });
		}
		Check(D.IsPlayerTurn() && D.GetSide(EDuelOwner::Player).LP == 8000,
			TEXT("mirror: the turn hands back with no damage"));
	}

	void TestPassAndPassTurn(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 502);
		FDuelScenario S = MakeScenario(TEXT("RW_PASS"));
		S.PlayerField.Add(SetST(421, 0));
		S.PlayerField.Add(SetST(552, 1));
		S.OpponentField.Add(Mon(1, 0));
		S.OpponentField.Add(Mon(5, 1));
		S.OpponentField.Add(Mon(3, 2));
		FString E;
		D.StartScenario(S, E);
		D.EndTurn();
		D.RunOpponentTurn();
		Check(IsResponse(D), TEXT("pass: first attack opens a window"));
		Answer(D, { FDuelEngine::ResponsePassOptionId });
		Check(D.GetSide(EDuelOwner::Player).LP == 5000, TEXT("pass: passing lets the 3000 attack through"));
		D.RunOpponentTurn();
		Check(IsResponse(D), TEXT("pass: the second attack opens another window"));
		Answer(D, { FDuelEngine::ResponsePassTurnOptionId });
		Check(D.GetSide(EDuelOwner::Player).LP == 8000 - 3000 - 1300, TEXT("pass: second attack hits"));
		D.RunOpponentTurn();
		Check(!D.HasPendingChoice(), TEXT("pass: 'Don't respond this turn' suppresses the remaining windows"));
		// The opponent also summoned the Shadow Specter it drew (500 ATK).
		Check(D.IsPlayerTurn() && D.GetSide(EDuelOwner::Player).LP == 8000 - 3000 - 1300 - 1200 - 500,
			TEXT("pass: remaining attacks resolve and the turn ends"));
		Check(CountSpells(D, EDuelOwner::Player) == 2, TEXT("pass: both Traps stay Set"));
	}

	void TestTrapHoleSummonWindow(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 503);
		FDuelScenario S = MakeScenario(TEXT("RW_TRAPHOLE"));
		S.PlayerField.Add(SetST(380, 0));
		S.OpponentHand = TArray<int32> { 5 };
		FString E;
		D.StartScenario(S, E);
		const int32 Th = UidIn(D.GetSide(EDuelOwner::Player).Spells, 380);
		D.EndTurn();
		D.RunOpponentTurn();
		Check(IsResponse(D), TEXT("traphole: the opponent's summon opens a window"));
		const int32 Imp = UidIn(D.GetSide(EDuelOwner::Opponent).Monsters, 5);
		Check(Imp != 0, TEXT("traphole: the summoned monster is on the field while the player decides"));
		Answer(D, { OptionFor(D.GetPendingChoice(), Th) });
		Check(!D.FindMonster(Imp) && InGrave(D, EDuelOwner::Player, Th),
			TEXT("traphole: Trap Hole destroys the summoned monster"));
		int Guard = 0;
		while (D.IsAwaitingAi() && Guard++ < 10)
		{
			D.RunOpponentTurn();
			if (D.HasPendingChoice())
				Answer(D, { FDuelEngine::ResponsePassOptionId });
		}
		Check(D.IsPlayerTurn(), TEXT("traphole: the opponent's turn completes"));
	}

	void TestSakuretsuDeferred(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 504);
		FDuelScenario S = MakeScenario(TEXT("RW_SAKURETSU"));
		S.PlayerField.Add(SetST(849, 0));
		S.OpponentField.Add(Mon(1, 0));
		FString E;
		D.StartScenario(S, E);
		const int32 Sak = UidIn(D.GetSide(EDuelOwner::Player).Spells, 849);
		const int32 Bewd = UidIn(D.GetSide(EDuelOwner::Opponent).Monsters, 1);
		D.EndTurn();
		D.RunOpponentTurn();
		Check(IsResponse(D), TEXT("sakuretsu: attack opens a window"));
		Check(D.FindMonster(Bewd) != nullptr, TEXT("sakuretsu: the scripted Trap did not auto-fire"));
		Check(OptionFor(D.GetPendingChoice(), Sak) != 0, TEXT("sakuretsu: the scripted Trap is offered"));
		Answer(D, { OptionFor(D.GetPendingChoice(), Sak) });
		Check(!D.FindMonster(Bewd), TEXT("sakuretsu: Sakuretsu Armor destroys the attacker"));
		Check(D.GetSide(EDuelOwner::Player).LP == 8000, TEXT("sakuretsu: no battle damage"));
		Check(InGrave(D, EDuelOwner::Player, Sak), TEXT("sakuretsu: Sakuretsu Armor is sent to the Graveyard"));
	}

	void TestSakuretsuDeclined(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 505);
		FDuelScenario S = MakeScenario(TEXT("RW_SAKURETSU_PASS"));
		S.PlayerField.Add(SetST(849, 0));
		S.OpponentField.Add(Mon(1, 0));
		FString E;
		D.StartScenario(S, E);
		const int32 Sak = UidIn(D.GetSide(EDuelOwner::Player).Spells, 849);
		D.EndTurn();
		D.RunOpponentTurn();
		Answer(D, { FDuelEngine::ResponsePassOptionId });
		Check(D.GetSide(EDuelOwner::Player).LP == 5000 && D.FindSpellTrap(Sak) && !D.FindSpellTrap(Sak)->bFaceUp,
			TEXT("sakuretsu: declining keeps the Trap Set and the attack resolves"));
		int Guard = 0;
		while (D.IsAwaitingAi() && Guard++ < 10)
		{
			D.RunOpponentTurn();
			if (D.HasPendingChoice())
				Answer(D, { FDuelEngine::ResponsePassOptionId });
		}
		Check(D.IsPlayerTurn() && D.FindSpellTrap(Sak), TEXT("sakuretsu: no stale deferred response fires later"));
	}

	void TestBottomless(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 506);
		FDuelScenario S = MakeScenario(TEXT("RW_BOTTOMLESS"));
		S.PlayerField.Add(SetST(686, 0));
		S.OpponentHand = TArray<int32> { 8 };
		FString E;
		D.StartScenario(S, E);
		const int32 Bt = UidIn(D.GetSide(EDuelOwner::Player).Spells, 686);
		D.EndTurn();
		D.RunOpponentTurn();
		const int32 Dragon = UidIn(D.GetSide(EDuelOwner::Opponent).Monsters, 8);
		Check(IsResponse(D) && OptionFor(D.GetPendingChoice(), Bt) != 0,
			TEXT("bottomless: the 1500 ATK summon offers Bottomless Trap Hole"));
		Answer(D, { OptionFor(D.GetPendingChoice(), Bt) });
		Check(!D.FindMonster(Dragon)
				&& D.GetSide(EDuelOwner::Opponent)
					   .Banished.ContainsByPredicate([Dragon](const FDuelCard& C) { return C.Uid == Dragon; }),
			TEXT("bottomless: the summoned monster is destroyed and banished"));
	}

	void TestMstInBattlePhase(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 507);
		FDuelScenario S = MakeScenario(TEXT("RW_MST"));
		S.PlayerField.Add(Mon(5, 0));
		S.PlayerField.Add(SetST(436, 0));
		S.OpponentField.Add(SetST(421, 0));
		FString E;
		D.StartScenario(S, E);
		const int32 Mst = UidIn(D.GetSide(EDuelOwner::Player).Spells, 436);
		const int32 OppMf = UidIn(D.GetSide(EDuelOwner::Opponent).Spells, 421);
		D.EnterBattlePhase();
		Check(D.GetSpellTrapActions(Mst).Num() == 1, TEXT("mst: a Set Quick-Play is activatable in the Battle Phase"));
		Check(D.ActivateSetTrap(Mst, E), TEXT("mst: the board action activates the Set Quick-Play"));
		const FDuelChoiceRequest* R = D.GetPendingChoice();
		Check(R && OptionFor(R, OppMf) != 0, TEXT("mst: the player chooses MST's target"));
		if (R)
			Answer(D, { OptionFor(R, OppMf) });
		Check(!D.FindSpellTrap(OppMf) && InGrave(D, EDuelOwner::Player, Mst),
			TEXT("mst: the chosen card is destroyed and MST resolves"));
	}

	void TestCompulsoryManual(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 508);
		FDuelScenario S = MakeScenario(TEXT("RW_CED"));
		S.PlayerField.Add(Mon(5, 0));
		S.PlayerField.Add(SetST(920, 0));
		S.OpponentField.Add(Mon(1, 0));
		FString E;
		D.StartScenario(S, E);
		const int32 Ced = UidIn(D.GetSide(EDuelOwner::Player).Spells, 920);
		const int32 Bewd = UidIn(D.GetSide(EDuelOwner::Opponent).Monsters, 1);
		Check(D.GetSpellTrapActions(Ced).Num() == 1, TEXT("ced: a scripted Normal Trap is activatable by the player"));
		Check(D.ActivateSetTrap(Ced, E), TEXT("ced: activation succeeds"));
		const FDuelChoiceRequest* R = D.GetPendingChoice();
		Check(R && OptionFor(R, Bewd) != 0, TEXT("ced: the player picks the monster to bounce"));
		if (R)
			Answer(D, { OptionFor(R, Bewd) });
		Check(!D.FindMonster(Bewd)
				&& D.GetSide(EDuelOwner::Opponent)
					   .Hand.ContainsByPredicate([Bewd](const FDuelCard& C) { return C.Uid == Bewd; }),
			TEXT("ced: the chosen monster returns to the hand"));
		Check(InGrave(D, EDuelOwner::Player, Ced), TEXT("ced: the Trap is sent to the Graveyard"));
	}

	void TestMagicJammer(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 509);
		FDuelScenario S = MakeScenario(TEXT("RW_JAMMER"));
		S.PlayerField.Add(SetST(402, 0));
		S.PlayerHand = TArray<int32> { 2, 3 };
		S.OpponentHand = TArray<int32> { 387 };
		FString E;
		D.StartScenario(S, E);
		const int32 Jam = UidIn(D.GetSide(EDuelOwner::Player).Spells, 402);
		const int32 Discard = UidIn(D.GetSide(EDuelOwner::Player).Hand, 3);
		D.EndTurn();
		D.RunOpponentTurn();
		const int32 HandBefore = D.GetSide(EDuelOwner::Opponent).Hand.Num();
		Check(IsResponse(D) && OptionFor(D.GetPendingChoice(), Jam) != 0,
			TEXT("jammer: the opponent's Spell opens a window with Magic Jammer"));
		Answer(D, { OptionFor(D.GetPendingChoice(), Jam) });
		const FDuelChoiceRequest* R = D.GetPendingChoice();
		Check(R && R->Type == EDuelChoiceType::SelectCard && OptionFor(R, Discard) != 0,
			TEXT("jammer: the player picks the discard"));
		if (R)
			Answer(D, { OptionFor(R, Discard) });
		Check(InGrave(D, EDuelOwner::Player, Discard), TEXT("jammer: the chosen card is discarded"));
		Check(D.GetSide(EDuelOwner::Opponent).Hand.Num() == HandBefore,
			TEXT("jammer: Pot of Greed is negated (no draw)"));
		Check(D.GetSide(EDuelOwner::Opponent)
				  .Graveyard.ContainsByPredicate([](const FDuelCard& C) { return C.Data.Id == 387; }),
			TEXT("jammer: Pot of Greed goes to the Graveyard"));
	}

	void TestSevenToolsOnPlayerAttack(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 510);
		FDuelScenario S = MakeScenario(TEXT("RW_TOOLS"));
		S.OpponentLp = 3000;
		S.PlayerField.Add(Mon(1, 0));
		S.PlayerField.Add(SetST(403, 0));
		S.OpponentField.Add(SetST(421, 0));
		FString E;
		D.StartScenario(S, E);
		const int32 Bewd = UidIn(D.GetSide(EDuelOwner::Player).Monsters, 1);
		const int32 Tools = UidIn(D.GetSide(EDuelOwner::Player).Spells, 403);
		D.EnterBattlePhase();
		Check(D.Attack(Bewd, 0, E), TEXT("tools: player attacks"));
		Check(IsResponse(D) && OptionFor(D.GetPendingChoice(), Tools) != 0,
			TEXT("tools: the opponent's Mirror Force offers Seven Tools"));
		Check(D.FindMonster(Bewd) != nullptr, TEXT("tools: Mirror Force waits for the player's answer"));
		Answer(D, { OptionFor(D.GetPendingChoice(), Tools) });
		Check(D.FindMonster(Bewd) && D.GetSide(EDuelOwner::Player).LP == 7000,
			TEXT("tools: Seven Tools negates Mirror Force for 1000 LP"));
		Check(D.IsOver() && D.GetWinner() == EDuelOwner::Player, TEXT("tools: the attack continues and wins"));
	}

	void TestBookOfMoonTarget(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 511);
		FDuelScenario S = MakeScenario(TEXT("RW_BOOK"));
		S.PlayerHand = TArray<int32> { 702 };
		S.OpponentField.Add(Mon(1, 0));
		S.OpponentField.Add(Mon(5, 1));
		FString E;
		D.StartScenario(S, E);
		const int32 Book = UidIn(D.GetSide(EDuelOwner::Player).Hand, 702);
		const int32 Imp = UidIn(D.GetSide(EDuelOwner::Opponent).Monsters, 5);
		const int32 Bewd = UidIn(D.GetSide(EDuelOwner::Opponent).Monsters, 1);
		Check(D.ActivateSpell(Book, E), TEXT("book: activates"));
		const FDuelChoiceRequest* R = D.GetPendingChoice();
		Check(R && OptionFor(R, Imp) && OptionFor(R, Bewd), TEXT("book: the player picks the target"));
		if (R)
			Answer(D, { OptionFor(R, Imp) });
		Check(D.FindMonster(Imp) && !D.FindMonster(Imp)->bFaceUp && D.FindMonster(Bewd)->bFaceUp,
			TEXT("book: only the chosen monster is flipped"));
		Check(InGrave(D, EDuelOwner::Player, Book), TEXT("book: Book of Moon resolves to the Graveyard"));
	}

	void TestGracefulCharity(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 512);
		FDuelScenario S = MakeScenario(TEXT("RW_CHARITY"));
		S.PlayerHand = TArray<int32> { 370, 1, 2 };
		FString E;
		D.StartScenario(S, E);
		const int32 Gc = UidIn(D.GetSide(EDuelOwner::Player).Hand, 370);
		const int32 Bewd = UidIn(D.GetSide(EDuelOwner::Player).Hand, 1);
		const int32 Elf = UidIn(D.GetSide(EDuelOwner::Player).Hand, 2);
		Check(D.ActivateSpell(Gc, E), TEXT("charity: activates"));
		const FDuelChoiceRequest* R = D.GetPendingChoice();
		Check(R && R->MinSelections == 2 && R->MaxSelections == 2, TEXT("charity: the player chooses 2 discards"));
		if (R)
			Answer(D, { Bewd, Elf });
		Check(InGrave(D, EDuelOwner::Player, Bewd) && InGrave(D, EDuelOwner::Player, Elf),
			TEXT("charity: the chosen cards are discarded"));
		Check(D.GetSide(EDuelOwner::Player).Hand.Num() == 3 && InGrave(D, EDuelOwner::Player, Gc),
			TEXT("charity: hand and Graceful Charity are correct"));
	}

	void TestEquipOpponent(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 513);
		FDuelScenario S = MakeScenario(TEXT("RW_EQUIP"));
		S.PlayerHand = TArray<int32> { 117 };
		S.PlayerField.Add(Mon(5, 0));
		S.OpponentField.Add(Mon(3, 0));
		FString E;
		D.StartScenario(S, E);
		const int32 Pendant = UidIn(D.GetSide(EDuelOwner::Player).Hand, 117);
		const int32 Opp = UidIn(D.GetSide(EDuelOwner::Opponent).Monsters, 3);
		Check(D.ActivateSpell(Pendant, E), TEXT("equip: Black Pendant activates"));
		const FDuelChoiceRequest* R = D.GetPendingChoice();
		Check(R && R->Options.Num() == 2 && OptionFor(R, Opp), TEXT("equip: both sides' monsters are offered"));
		if (R)
			Answer(D, { OptionFor(R, Opp) });
		Check(D.FindMonster(Opp) && D.GetAtk(*D.FindMonster(Opp)) == 1700,
			TEXT("equip: the chosen opponent's monster gains 500 ATK"));
	}

	void TestEndPhaseWindow(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 514);
		FDuelScenario S = MakeScenario(TEXT("RW_JAR"));
		S.PlayerField.Add(SetST(591, 0));
		FString E;
		D.StartScenario(S, E);
		const int32 Jar = UidIn(D.GetSide(EDuelOwner::Player).Spells, 591);
		Check(D.GetSpellTrapActions(Jar).Num() == 1, TEXT("jar: Jar of Greed is activatable on the player's own turn"));
		D.EndTurn();
		D.RunOpponentTurn();
		int Windows = 0;
		int Guard = 0;
		bool bActivated = false;
		while (D.IsAwaitingAi() && Guard++ < 20)
		{
			if (IsResponse(D))
			{
				++Windows;
				const FDuelChoiceRequest* R = D.GetPendingChoice();
				if (R->Prompt.Contains(TEXT("End Phase")))
				{
					const int32 HandBefore = D.GetSide(EDuelOwner::Player).Hand.Num();
					Answer(D, { OptionFor(R, Jar) });
					bActivated = D.GetSide(EDuelOwner::Player).Hand.Num() == HandBefore + 1;
				}
				else
					Answer(D, { FDuelEngine::ResponsePassOptionId });
			}
			D.RunOpponentTurn();
		}
		Check(Windows >= 2, TEXT("jar: Battle Phase and End Phase windows are offered"));
		Check(bActivated, TEXT("jar: Jar of Greed resolves in the opponent's End Phase"));
		Check(D.IsPlayerTurn(), TEXT("jar: the turn completes"));
	}

	void TestHandQuickPlayInBattle(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 515);
		FDuelScenario S = MakeScenario(TEXT("RW_RUSH"));
		S.PlayerHand = TArray<int32> { 702 };
		S.PlayerField.Add(Mon(5, 0));
		S.OpponentField.Add(Mon(1, 0));
		FString E;
		D.StartScenario(S, E);
		const int32 Book = UidIn(D.GetSide(EDuelOwner::Player).Hand, 702);
		D.EnterBattlePhase();
		Check(D.GetHandActions(Book).Num() == 1, TEXT("quickhand: a hand Quick-Play is offered in the Battle Phase"));
		Check(D.ActivateSpell(Book, E), TEXT("quickhand: the hand Quick-Play activates mid-battle"));
		if (D.HasPendingChoice())
			Answer(D, { D.GetPendingChoice()->DefaultOptionIds });
		Check(InGrave(D, EDuelOwner::Player, Book), TEXT("quickhand: the Quick-Play resolves"));
	}

	void TestAutoModeUnchanged(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 516);
		D.SetAutoAnswerAllChoices(true);
		FDuelScenario S = MakeScenario(TEXT("RW_AUTO"));
		S.PlayerField.Add(SetST(421, 0));
		S.OpponentField.Add(Mon(1, 0));
		S.OpponentField.Add(Mon(5, 1));
		FString E;
		D.StartScenario(S, E);
		D.EndTurn();
		D.RunOpponentTurn();
		Check(!D.HasPendingChoice() && D.IsPlayerTurn() && CountMonsters(D, EDuelOwner::Opponent) == 0,
			TEXT("auto: legacy automatic Mirror Force still fires when every choice is auto-answered"));
	}


	void TestBookOfMoonOnAttacker(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 517);
		FDuelScenario S = MakeScenario(TEXT("RW_BOOK_ATTACKER"));
		S.PlayerField.Add(SetST(702, 0));
		S.OpponentField.Add(Mon(1, 0));
		FString E;
		D.StartScenario(S, E);
		const int32 Book = UidIn(D.GetSide(EDuelOwner::Player).Spells, 702);
		const int32 Bewd = UidIn(D.GetSide(EDuelOwner::Opponent).Monsters, 1);
		D.EndTurn();
		D.RunOpponentTurn();
		Check(IsResponse(D) && OptionFor(D.GetPendingChoice(), Book) != 0,
			TEXT("book-attacker: a Set Quick-Play is offered against an attack"));
		Answer(D, { OptionFor(D.GetPendingChoice(), Book) });
		const FDuelChoiceRequest* R = D.GetPendingChoice();
		Check(R && R->Type == EDuelChoiceType::SelectCard && OptionFor(R, Bewd) != 0,
			TEXT("book-attacker: the attack waits while Book of Moon's target is chosen"));
		if (R)
		{
			Answer(D, { OptionFor(R, Bewd) });
		}
		Check(D.FindMonster(Bewd) && !D.FindMonster(Bewd)->bFaceUp && D.GetSide(EDuelOwner::Player).LP == 8000,
			TEXT("book-attacker: a face-down attacker's attack stops"));
	}

	void TestReplayAfterNewDefender(UCardDatabaseSubsystem* Db, FCheck Check)
	{
		FDuelEngine D(Db, 518);
		FDuelScenario S = MakeScenario(TEXT("RW_REPLAY"));
		S.PlayerField.Add(SetST(497, 0));
		S.PlayerGraveyard = TArray<int32>{ 1 };
		S.OpponentField.Add(Mon(5, 0));
		FString E;
		D.StartScenario(S, E);
		const int32 Coth = UidIn(D.GetSide(EDuelOwner::Player).Spells, 497);
		D.EndTurn();
		D.RunOpponentTurn();
		Check(IsResponse(D) && OptionFor(D.GetPendingChoice(), Coth) != 0,
			TEXT("replay: Call of the Haunted is offered against a direct attack"));
		Answer(D, { OptionFor(D.GetPendingChoice(), Coth) });
		Check(CountMonsters(D, EDuelOwner::Player) == 1, TEXT("replay: Call of the Haunted revives a monster"));
		int Guard = 0;
		while (D.IsAwaitingAi() && Guard++ < 10)
		{
			D.RunOpponentTurn();
			if (D.HasPendingChoice())
			{
				Answer(D, { FDuelEngine::ResponsePassOptionId });
			}
		}
		Check(D.IsPlayerTurn() && D.GetSide(EDuelOwner::Player).LP == 8000,
			TEXT("replay: the direct attack is replayed instead of hitting through the new defender"));
	}
} // namespace

namespace DADuelResponseSelfTest
{
	void Run(UCardDatabaseSubsystem* Database, TFunctionRef<void(bool, const FString&)> Check)
	{
		if (!Database || !Database->FindCard(421) || !Database->FindCard(849)
			|| !Database->FindCard(497))
		{
			Check(false, TEXT("response-window checks: the card database is loaded"));
			return;
		}
		TestMirrorForceWindow(Database, Check);
		TestPassAndPassTurn(Database, Check);
		TestTrapHoleSummonWindow(Database, Check);
		TestSakuretsuDeferred(Database, Check);
		TestSakuretsuDeclined(Database, Check);
		TestBottomless(Database, Check);
		TestMstInBattlePhase(Database, Check);
		TestCompulsoryManual(Database, Check);
		TestMagicJammer(Database, Check);
		TestSevenToolsOnPlayerAttack(Database, Check);
		TestBookOfMoonTarget(Database, Check);
		TestGracefulCharity(Database, Check);
		TestEquipOpponent(Database, Check);
		TestEndPhaseWindow(Database, Check);
		TestHandQuickPlayInBattle(Database, Check);
		TestBookOfMoonOnAttacker(Database, Check);
		TestReplayAfterNewDefender(Database, Check);
		TestAutoModeUnchanged(Database, Check);
	}
} // namespace DADuelResponseSelfTest
