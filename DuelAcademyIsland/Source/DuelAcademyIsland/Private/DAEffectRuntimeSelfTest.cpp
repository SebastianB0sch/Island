#include "DAEffectRuntimeSelfTest.h"

#include "DAEffectRuntime.h"
#include "DADuelEngine.h"
#include "DACardRecords.h"
#include "DuelAcademyIsland.h"

#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Containers/Ticker.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
	FDuelScenario MakeScenario(const FString& Id)
	{
		FDuelScenario Scenario;
		Scenario.Id = Id;
		Scenario.Name = Id;
		Scenario.PlayerLp = 8000;
		Scenario.OpponentLp = 8000;
		Scenario.PlayerDeck = TArray<int32>{ 1, 2, 3, 4, 5, 6 };
		Scenario.OpponentDeck = TArray<int32>{ 7, 8, 9, 10, 11, 12 };
		Scenario.bPlayerGoesFirst = true;
		Scenario.bDrawOnFirstTurn = false;
		return Scenario;
	}

	FDuelScenarioCard MakeMonster(int32 CardId, int32 ZoneIndex = 0, bool bDefense = false, bool bFaceDown = false)
	{
		FDuelScenarioCard Card;
		Card.CardId = CardId;
		Card.Zone = EDuelZone::Monster;
		Card.ZoneIndex = ZoneIndex;
		Card.bDefense = bDefense;
		Card.bFaceDown = bFaceDown;
		return Card;
	}

	FDuelScenarioCard MakeSpellTrap(int32 CardId, int32 ZoneIndex = 0, bool bFaceDown = false)
	{
		FDuelScenarioCard Card;
		Card.CardId = CardId;
		Card.Zone = EDuelZone::SpellTrap;
		Card.ZoneIndex = ZoneIndex;
		Card.bFaceDown = bFaceDown;
		return Card;
	}

	FDuelScenarioCard MakeField(int32 CardId)
	{
		FDuelScenarioCard Card;
		Card.CardId = CardId;
		Card.Zone = EDuelZone::Field;
		return Card;
	}

	int32 FindUidInArray(const TArray<FDuelCard>& Cards, int32 CardId)
	{
		for (const FDuelCard& Card : Cards)
		{
			if (Card.IsValid() && Card.Data.Id == CardId)
			{
				return Card.Uid;
			}
		}
		return 0;
	}

	int32 CountCardsInArray(const TArray<FDuelCard>& Cards, int32 CardId)
	{
		int32 Count = 0;
		for (const FDuelCard& Card : Cards)
		{
			if (Card.IsValid() && Card.Data.Id == CardId)
			{
				++Count;
			}
		}
		return Count;
	}

	int32 FindUidInSide(const FDuelSide& Side, int32 CardId)
	{
		int32 Uid = FindUidInArray(Side.Monsters, CardId);
		if (Uid == 0) Uid = FindUidInArray(Side.Spells, CardId);
		if (Uid == 0 && Side.Field.IsValid() && Side.Field.Data.Id == CardId) Uid = Side.Field.Uid;
		if (Uid == 0) Uid = FindUidInArray(Side.Hand, CardId);
		if (Uid == 0) Uid = FindUidInArray(Side.Deck, CardId);
		if (Uid == 0) Uid = FindUidInArray(Side.Graveyard, CardId);
		if (Uid == 0) Uid = FindUidInArray(Side.Banished, CardId);
		if (Uid == 0) Uid = FindUidInArray(Side.Extra, CardId);
		return Uid;
	}

	int32 FindFieldUid(const FDuelSide& Side, int32 CardId)
	{
		int32 Uid = FindUidInArray(Side.Monsters, CardId);
		if (Uid == 0) Uid = FindUidInArray(Side.Spells, CardId);
		if (Uid == 0 && Side.Field.IsValid() && Side.Field.Data.Id == CardId) Uid = Side.Field.Uid;
		return Uid;
	}

	FDEffectEvent MakeSourceEvent(EDEffectTrigger Trigger, const FDuelCard& Card, const FString& SummonType = FString())
	{
		FDEffectEvent Event;
		Event.Trigger = Trigger;
		Event.SourceCard = Card;
		Event.EventCard = Card;
		Event.SourceController = Card.Controller;
		Event.EventController = Card.Controller;
		Event.SummonType = SummonType;
		Event.bFromField = true;
		return Event;
	}

	int32 FindManualScript(const FDAEffectRuntime& Runtime, int32 CardId)
	{
		for (int32 Index = 0; Index < Runtime.GetScriptCount(CardId); ++Index)
		{
			if (Runtime.GetScriptTrigger(CardId, Index) == EDEffectTrigger::Manual)
			{
				return Index;
			}
		}
		return INDEX_NONE;
	}

	bool LoadTestScript(FDAEffectRuntime* Runtime, int32 CardId, const FString& ScriptJson)
	{
		if (!Runtime)
		{
			return false;
		}
		const FString FullJson = FString::Printf(TEXT("{\"card_id\":%d,\"scripts\":[%s]}"), CardId, *ScriptJson);
		FString Error;
		const bool bLoaded = Runtime->LoadScriptJsonText(FullJson, Error);
		if (!bLoaded)
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("Test script %d failed to load: %s"), CardId, *Error);
		}
		return bLoaded;
	}

	FString TestScript(const FString& Id, const FString& Trigger, const FString& Operations,
		const FString& Extra = FString())
	{
		return FString::Printf(
			TEXT("{\"id\":\"%s\",\"trigger\":\"%s\",\"operations\":[%s]%s}"),
			*Id, *Trigger, *Operations, Extra.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(",%s"), *Extra));
	}

	void LogReport(const FDEffectRuntimeSelfTestReport& Report)
	{
		for (const FString& Line : Report.Lines)
		{
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Line);
		}
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Report.ToSummary());
	}
}

FDEffectRuntimeSelfTestReport FDAEffectRuntimeSelfTest::Run(UCardDatabaseSubsystem* Database)
{
	FDEffectRuntimeSelfTestReport Report;
	Report.Check(Database != nullptr, TEXT("card database is available"));
	if (!Database)
	{
		LogReport(Report);
		return Report;
	}

	// ---- script loading ---------------------------------------------------
	{
		FDuelEngine Duel(Database, 71);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		Report.Check(Runtime != nullptr, TEXT("effect runtime is attached to the engine"));
		if (!Runtime)
		{
			LogReport(Report);
			return Report;
		}
		Report.Check(Runtime->GetLoadedCardCount() >= 10, TEXT("ten example card scripts were loaded"));
		Report.Check(Runtime->GetLoadedScriptCount() >= 12, TEXT("all example scripts were loaded"));
		Report.Check(Runtime->GetLoadedCardCount() >= 253, TEXT("all 253 shipped effect scripts are loaded"));
		Report.Check(Runtime->GetLoadedScriptCount() >= 312, TEXT("all 312 shipped script entries are loaded"));
		Report.Check(Runtime->HasScript(29) && Runtime->HasScript(259) && Runtime->HasScript(787),
			TEXT("Sangan, Morphing Jar and Breaker scripts are present"));
		Report.Check(Runtime->GetScriptCount(787) == 3, TEXT("Breaker has its three scripts"));
	}

	// ---- Sangan: sent-from-field search ----------------------------------
	{
		FDuelEngine Duel(Database, 72);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_SANGAN"));
		Scenario.PlayerGraveyard = TArray<int32>{ 29 };
		Scenario.PlayerDeck = TArray<int32>{ 2 };
		FString Error;
		Report.Check(Duel.StartScenario(Scenario, Error), TEXT("Sangan scenario starts"));
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 SanganUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 29);
		const FDuelCard* Sangan = Duel.FindCard(SanganUid);
		Report.Check(Sangan != nullptr && Runtime != nullptr, TEXT("Sangan is in the Graveyard"));
		if (Sangan && Runtime)
		{
			FDEffectEvent Event = MakeSourceEvent(EDEffectTrigger::OnSentToGraveyard, *Sangan);
			Event.Reason = TEXT("battle");
			const int32 Started = Runtime->FireEvent(Event);
			const int32 SearchedUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 2);
			Report.Check(Started > 0 && SearchedUid != 0 && Duel.GetSide(EDuelOwner::Player).Hand.ContainsByPredicate(
				[SearchedUid](const FDuelCard& Card) { return Card.Uid == SearchedUid; }),
				TEXT("Sangan searches a <=1500 ATK monster into the hand"));
			Report.Check(Runtime->GetPromptCount() > 0, TEXT("Sangan target search prompted for a choice"));
		}
	}

	// ---- self trigger binds to the event source uid, not the card name ----
	{
		FDuelEngine Duel(Database, 83);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_SELF_TRIGGER_TWO_COPIES"));
		Scenario.PlayerField.Add(MakeMonster(1032, 0));
		Scenario.PlayerHand = TArray<int32>{ 1032 };
		Scenario.PlayerDeck = TArray<int32>{ 1034, 1034 };
		FString Error;
		Report.Check(Duel.StartScenario(Scenario, Error),
			TEXT("two-copy Green Gadget scenario starts"));
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 HandGadgetUid = FindUidInArray(Duel.GetSide(EDuelOwner::Player).Hand, 1032);
		const int32 FieldGadgetUid = FindUidInArray(Duel.GetSide(EDuelOwner::Player).Monsters, 1032);
		Report.Check(Runtime != nullptr && HandGadgetUid != 0 && FieldGadgetUid != 0,
			TEXT("two copies of Green Gadget are in hand and on the field"));
		if (Runtime && HandGadgetUid != 0 && FieldGadgetUid != 0)
		{
			Runtime->ResetTestStats();
			FString SummonError;
			const bool bSummoned = Duel.NormalSummon(HandGadgetUid, TArray<int32>(), false, SummonError);
			Report.Check(bSummoned && Duel.FindMonster(HandGadgetUid) != nullptr,
				TEXT("the hand copy of Green Gadget is Normal Summoned"));
			Report.Check(Runtime->GetExecutedScriptCount() == 1,
				TEXT("only the summoned copy's on_summon script executes"));
			Report.Check(CountCardsInArray(Duel.GetSide(EDuelOwner::Player).Hand, 1034) == 1,
				TEXT("the other Green Gadget copy does not search a second Red Gadget"));
		}
	}

	// ---- destroyed copy is the only on_sent_to_graveyard source -----------
	{
		FDuelEngine Duel(Database, 84);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_SENT_TWO_COPIES"));
		Scenario.PlayerField.Add(MakeMonster(29, 0));
		Scenario.PlayerGraveyard = TArray<int32>{ 29 };
		Scenario.PlayerDeck = TArray<int32>{ 2, 2 };
		FString Error;
		Report.Check(Duel.StartScenario(Scenario, Error),
			TEXT("two-copy Sangan scenario starts"));
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 GraveSanganUid = FindUidInArray(Duel.GetSide(EDuelOwner::Player).Graveyard, 29);
		const FDuelCard* GraveSangan = Duel.FindCard(GraveSanganUid);
		Report.Check(Runtime != nullptr && GraveSangan != nullptr
			&& FindUidInArray(Duel.GetSide(EDuelOwner::Player).Monsters, 29) != 0,
			TEXT("two copies of Sangan are in the Graveyard and on the field"));
		if (Runtime && GraveSangan)
		{
			Runtime->ResetTestStats();
			FDEffectEvent Event = MakeSourceEvent(EDEffectTrigger::OnSentToGraveyard, *GraveSangan);
			Event.Reason = TEXT("battle");
			Runtime->FireEvent(Event);
			Report.Check(Runtime->GetExecutedScriptCount() == 1,
				TEXT("only the sent copy's on_sent_to_graveyard script executes"));
			Report.Check(CountCardsInArray(Duel.GetSide(EDuelOwner::Player).Hand, 2) == 1,
				TEXT("the field Sangan copy does not search a second target"));
		}
	}

	// ---- self triggers ignore other cards and other copies ---------------
	{
		FDuelEngine Duel(Database, 85);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_SELF_TRIGGER_SOURCE"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.PlayerField.Add(MakeMonster(1, 1));
		Scenario.OpponentField.Add(MakeMonster(3, 0));
		FString Error;
		Report.Check(Duel.StartScenario(Scenario, Error), TEXT("self-trigger source-binding scenario starts"));
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const TArray<FDuelCard>& PlayerMonsters = Duel.GetSide(EDuelOwner::Player).Monsters;
		const int32 FirstCopyUid = PlayerMonsters.IsValidIndex(0) ? PlayerMonsters[0].Uid : 0;
		const int32 SecondCopyUid = PlayerMonsters.IsValidIndex(1) ? PlayerMonsters[1].Uid : 0;
		const int32 OtherUid = FindUidInSide(Duel.GetSide(EDuelOwner::Opponent), 3);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_self_battle_destroy","trigger":"on_battle_destroy","operations":[{"op":"gain_lp","player":"self","amount":10}]})JSON"));
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_self_sent_grave","trigger":"on_sent_to_graveyard","operations":[{"op":"gain_lp","player":"self","amount":20}]})JSON"));
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_self_tribute","trigger":"on_tribute_summon","operations":[{"op":"gain_lp","player":"self","amount":40}]})JSON"));
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_self_position","trigger":"on_position_change","operations":[{"op":"gain_lp","player":"self","amount":80}]})JSON"));
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_self_summon","trigger":"on_summon","operations":[{"op":"gain_lp","player":"self","amount":160}]})JSON"));
		if (Runtime && FirstCopyUid != 0 && SecondCopyUid != 0 && OtherUid != 0)
		{
			const FDuelCard* OtherCard = Duel.FindMonster(OtherUid);
			const EDuelOwner Opponent = EDuelOwner::Opponent;
			Runtime->ResetTestStats();
			if (OtherCard)
			{
				FDEffectEvent Event = MakeSourceEvent(EDEffectTrigger::OnBattleDestroy, *OtherCard);
				Event.SourceController = Opponent;
				Runtime->FireEvent(Event);
				Event = MakeSourceEvent(EDEffectTrigger::OnSentToGraveyard, *OtherCard);
				Event.SourceController = Opponent;
				Runtime->FireEvent(Event);
				Event = MakeSourceEvent(EDEffectTrigger::OnTributeSummon, *OtherCard);
				Event.SourceController = Opponent;
				Event.TributeCount = 1;
				Runtime->FireEvent(Event);
				Event = MakeSourceEvent(EDEffectTrigger::OnPositionChange, *OtherCard);
				Event.SourceController = Opponent;
				Runtime->FireEvent(Event);
				Event = MakeSourceEvent(EDEffectTrigger::OnSummon, *OtherCard, TEXT("normal"));
				Event.SourceController = Opponent;
				Runtime->FireEvent(Event);
			}
			Report.Check(Runtime->GetExecutedScriptCount() == 0
				&& Duel.GetSide(EDuelOwner::Player).LP == 8000,
				TEXT("self triggers ignore another card's event"));

			Runtime->ResetTestStats();
			if (const FDuelCard* FirstCopy = Duel.FindMonster(FirstCopyUid))
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnBattleDestroy, *FirstCopy));
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnSentToGraveyard, *FirstCopy));
				FDEffectEvent TributeEvent = MakeSourceEvent(EDEffectTrigger::OnTributeSummon, *FirstCopy);
				TributeEvent.TributeCount = 1;
				Runtime->FireEvent(TributeEvent);
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnPositionChange, *FirstCopy));
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnSummon, *FirstCopy, TEXT("normal")));
			}
			Report.Check(Runtime->GetExecutedScriptCount() == 5,
				TEXT("only the event's own copy runs for each self trigger"));
			Report.Check(Duel.GetSide(EDuelOwner::Player).LP == 8310,
				TEXT("two copies do not double the self-trigger rewards"));
			Report.Check(Runtime->GetFailedScriptCount() == 0,
				TEXT("source-bound self triggers resolve without failures"));
		}
	}

	// ---- explicit field-scan opt-in --------------------------------------
	{
		FDuelEngine Duel(Database, 86);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_SELF_TRIGGER_FIELD_SCAN"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.OpponentField.Add(MakeMonster(3, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 OtherUid = FindUidInSide(Duel.GetSide(EDuelOwner::Opponent), 3);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_field_scan","trigger":"on_battle_destroy","condition":{"field_scan":true},"operations":[{"op":"gain_lp","player":"self","amount":50}]})JSON"));
		if (Runtime && OtherUid != 0)
		{
			if (const FDuelCard* OtherCard = Duel.FindMonster(OtherUid))
			{
				FDEffectEvent Event = MakeSourceEvent(EDEffectTrigger::OnBattleDestroy, *OtherCard);
				Event.SourceController = EDuelOwner::Opponent;
				Runtime->FireEvent(Event);
			}
			Report.Check(Duel.GetSide(EDuelOwner::Player).LP == 8050,
				TEXT("field_scan:true explicitly opts a self trigger into other-card events"));
		}
	}


	{
		FDuelEngine Duel(Database, 73);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_MORPHING"));
		Scenario.PlayerField.Add(MakeMonster(259));
		Scenario.PlayerHand = TArray<int32>{ 1, 2 };
		Scenario.OpponentHand = TArray<int32>{ 3, 4 };
		Scenario.PlayerDeck = TArray<int32>{ 5, 6, 7, 8, 9, 10 };
		Scenario.OpponentDeck = TArray<int32>{ 11, 12, 13, 14, 15, 16 };
		FString Error;
		Report.Check(Duel.StartScenario(Scenario, Error), TEXT("Morphing Jar scenario starts"));
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 JarUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 259);
		const FDuelCard* Jar = Duel.FindCard(JarUid);
		Report.Check(Jar != nullptr && Runtime != nullptr, TEXT("Morphing Jar is on the field"));
		if (Jar && Runtime)
		{
			const int32 Started = Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnFlip, *Jar));
			Report.Check(Started > 0, TEXT("Morphing Jar FLIP script executed"));
			Report.Check(Duel.GetSide(EDuelOwner::Player).Hand.Num() == 5
				&& Duel.GetSide(EDuelOwner::Opponent).Hand.Num() == 5,
				TEXT("Morphing Jar makes both players discard and draw five"));
			Report.Check(Duel.GetSide(EDuelOwner::Player).Graveyard.Num() >= 2
				&& Duel.GetSide(EDuelOwner::Opponent).Graveyard.Num() >= 2,
				TEXT("Morphing Jar discarded both hands before drawing"));
		}
	}

	// ---- Breaker: trigger, counter, continuous ATK, manual cost ----------
	{
		FDuelEngine Duel(Database, 74);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_BREAKER"));
		Scenario.PlayerField.Add(MakeMonster(787));
		Scenario.OpponentField.Add(MakeSpellTrap(849, 0, true));
		FString Error;
		Report.Check(Duel.StartScenario(Scenario, Error), TEXT("Breaker scenario starts"));
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BreakerUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 787);
		const FDuelCard* Breaker = Duel.FindCard(BreakerUid);
		Report.Check(Breaker != nullptr && Runtime != nullptr, TEXT("Breaker is on the field"));
		if (Breaker && Runtime)
		{
			const int32 BaseAtk = Breaker->Data.Atk;
			Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnNormalSummon, *Breaker, TEXT("normal")));
			Report.Check(Runtime->GetCounterCount(BreakerUid, TEXT("spell")) == 1,
				TEXT("Breaker places one Spell Counter on Normal Summon"));
			Runtime->RecomputeContinuous();
			const FDuelCard* BreakerNow = Duel.FindCard(BreakerUid);
			Report.Check(BreakerNow != nullptr && Duel.GetAtk(*BreakerNow) >= BaseAtk + 300,
				TEXT("Breaker's continuous effect adds 300 ATK per Spell Counter"));

			const int32 ScriptIndex = FindManualScript(*Runtime, 787);
			Report.Check(ScriptIndex != INDEX_NONE, TEXT("Breaker manual effect is exposed"));
			if (ScriptIndex != INDEX_NONE)
			{
				FString ManualError;
				Report.Check(Runtime->ActivateManualScript(BreakerUid, ScriptIndex, ManualError),
					TEXT("Breaker manual effect activates"));
				Report.Check(Runtime->GetCounterCount(BreakerUid, TEXT("spell")) == 0,
					TEXT("Breaker removes its Spell Counter as a cost"));
				Report.Check(FindFieldUid(Duel.GetSide(EDuelOwner::Opponent), 849) == 0,
					TEXT("Breaker destroys a Spell/Trap target"));
			}
		}
	}

	// ---- Exiled Force: self-tribute cost + once-per-turn ------------------
	{
		FDuelEngine Duel(Database, 75);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_EXILED"));
		Scenario.PlayerField.Add(MakeMonster(651));
		Scenario.OpponentField.Add(MakeMonster(1));
		FString Error;
		Report.Check(Duel.StartScenario(Scenario, Error), TEXT("Exiled Force scenario starts"));
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 ExiledUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 651);
		const int32 ScriptIndex = Runtime ? FindManualScript(*Runtime, 651) : INDEX_NONE;
		Report.Check(ExiledUid != 0 && ScriptIndex != INDEX_NONE, TEXT("Exiled Force manual script is available"));
		if (Runtime && ExiledUid != 0 && ScriptIndex != INDEX_NONE)
		{
			FString ManualError;
			const bool bFirst = Runtime->ActivateManualScript(ExiledUid, ScriptIndex, ManualError);
			const bool bSecond = Runtime->ActivateManualScript(ExiledUid, ScriptIndex, ManualError);
			Report.Check(bFirst, TEXT("Exiled Force activates"));
			Report.Check(!bSecond, TEXT("Exiled Force cannot activate twice"));
			Report.Check(FindFieldUid(Duel.GetSide(EDuelOwner::Player), 651) == 0,
				TEXT("Exiled Force pays its self-tribute cost"));
			Report.Check(FindFieldUid(Duel.GetSide(EDuelOwner::Opponent), 1) == 0,
				TEXT("Exiled Force destroys its target"));
		}
	}

	// ---- Mystical Space Typhoon: Quick-Play prompt and destroy ------------
	{
		FDuelEngine Duel(Database, 76);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_MST"));
		Scenario.PlayerHand = TArray<int32>{ 436 };
		Scenario.OpponentField.Add(MakeSpellTrap(849, 0, true));
		Scenario.OpponentField.Add(MakeSpellTrap(686, 1, true));
		FString Error;
		Report.Check(Duel.StartScenario(Scenario, Error), TEXT("MST scenario starts"));
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 MstUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 436);
		Report.Check(MstUid != 0 && Runtime != nullptr, TEXT("MST is in hand"));
		if (MstUid != 0 && Runtime)
		{
			Runtime->ResetTestStats();
			FString ActivateError;
			Report.Check(Duel.ActivateQuickPlayFromHand(MstUid, ActivateError),
				TEXT("MST activates as a Quick-Play Spell"));
			Report.Check(Runtime->GetPromptCount() > 0,
				TEXT("MST asks for a target when multiple Spell/Trap cards are legal"));
			Report.Check(FindFieldUid(Duel.GetSide(EDuelOwner::Opponent), 849) == 0
				|| FindFieldUid(Duel.GetSide(EDuelOwner::Opponent), 686) == 0,
				TEXT("MST destroys a Spell/Trap card"));
		}
	}

	// ---- Bottomless Trap Hole: summon condition and destroy->banish ------
	{
		FDuelEngine Duel(Database, 77);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_BOTTOMLESS"));
		Scenario.PlayerField.Add(MakeSpellTrap(686, 0, true));
		Scenario.OpponentField.Add(MakeMonster(1));
		FString Error;
		Report.Check(Duel.StartScenario(Scenario, Error), TEXT("Bottomless scenario starts"));
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Opponent), 1);
		const FDuelCard* BlueEyes = Duel.FindCard(BlueEyesUid);
		Report.Check(BlueEyes != nullptr && Runtime != nullptr, TEXT("Bottomless summon source exists"));
		if (BlueEyes && Runtime)
		{
			FDEffectEvent Event = MakeSourceEvent(EDEffectTrigger::OnSummon, *BlueEyes, TEXT("normal"));
			Event.SourceController = EDuelOwner::Opponent;
			Event.EventController = EDuelOwner::Opponent;
			const int32 Started = Runtime->FireEvent(Event);
			Report.Check(Started > 0, TEXT("Bottomless Trap Hole responds to a >=1500 ATK Summon"));
			Report.Check(FindFieldUid(Duel.GetSide(EDuelOwner::Opponent), 1) == 0
				&& Duel.GetSide(EDuelOwner::Opponent).Banished.ContainsByPredicate(
					[](const FDuelCard& Card) { return Card.Data.Id == 1; }),
				TEXT("Bottomless destroys then banishes the summoned monster"));
			Report.Check(FindFieldUid(Duel.GetSide(EDuelOwner::Player), 686) == 0,
				TEXT("Bottomless Trap Hole leaves the field after resolving"));
		}
	}

	// ---- Bottomless negative condition -----------------------------------
	{
		FDuelEngine Duel(Database, 78);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_BOTTOMLESS_NEG"));
		Scenario.PlayerField.Add(MakeSpellTrap(686, 0, true));
		Scenario.OpponentField.Add(MakeMonster(2));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 ElfUid = FindUidInSide(Duel.GetSide(EDuelOwner::Opponent), 2);
		const FDuelCard* Elf = Duel.FindCard(ElfUid);
		if (Runtime && Elf)
		{
			FDEffectEvent Event = MakeSourceEvent(EDEffectTrigger::OnSummon, *Elf, TEXT("normal"));
			Event.SourceController = EDuelOwner::Opponent;
			Event.EventController = EDuelOwner::Opponent;
			Report.Check(Runtime->FireEvent(Event) == 0 && Duel.FindCard(ElfUid) != nullptr,
				TEXT("Bottomless does not trigger below 1500 ATK"));
		}
	}

	// ---- Sakuretsu Armor: attack-declared trap ---------------------------
	{
		FDuelEngine Duel(Database, 79);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_SAKURETSU"));
		Scenario.PlayerField.Add(MakeSpellTrap(849, 0, true));
		Scenario.OpponentField.Add(MakeMonster(1));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 AttackerUid = FindUidInSide(Duel.GetSide(EDuelOwner::Opponent), 1);
		const FDuelCard* Attacker = Duel.FindCard(AttackerUid);
		if (Runtime && Attacker)
		{
			FDEffectEvent Event = MakeSourceEvent(EDEffectTrigger::OnAttackDeclared, *Attacker);
			Event.SourceController = EDuelOwner::Opponent;
			Event.EventController = EDuelOwner::Opponent;
			Event.AttackerUid = AttackerUid;
			const int32 Started = Runtime->FireEvent(Event);
			Report.Check(Started > 0 && FindFieldUid(Duel.GetSide(EDuelOwner::Opponent), 1) == 0,
				TEXT("Sakuretsu Armor destroys the attacking monster"));
		}
	}

	// ---- Jinzo continuous trap lock --------------------------------------
	{
		FDuelEngine Duel(Database, 80);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_JINZO"));
		Scenario.PlayerField.Add(MakeMonster(348));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		if (Runtime)
		{
			Runtime->RecomputeContinuous();
			Report.Check(Runtime->IsTrapActivationLocked(), TEXT("Jinzo locks Trap activation while face-up"));
		}
	}

	// ---- Fusion Gate continuous procedure --------------------------------
	{
		FDuelEngine Duel(Database, 81);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_FUSION_GATE"));
		Scenario.PlayerField.Add(MakeField(637));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		if (Runtime)
		{
			Runtime->RecomputeContinuous();
			Report.Check(Runtime->IsFusionAllowed(TEXT("Fusion Gate")),
				TEXT("Fusion Gate registers the Fusion Gate procedure"));
		}
	}

	// ---- Amazoness Swords Woman damage redirect --------------------------
	{
		FDuelEngine Duel(Database, 82);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_AMAZONESS"));
		Scenario.PlayerField.Add(MakeMonster(639));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 AmazonessUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 639);
		if (Runtime && AmazonessUid != 0)
		{
			Runtime->RecomputeContinuous();
			EDuelOwner Redirect = EDuelOwner::Player;
			Report.Check(Runtime->ShouldRedirectBattleDamage(AmazonessUid, EDuelOwner::Player, Redirect)
				&& Redirect == EDuelOwner::Opponent,
				TEXT("Amazoness Swords Woman redirects battle damage to the opponent"));
		}
	}

	// ---- generic equip stat bonus (continuous recalculation + cleanup) ----
	{
		FDuelEngine Duel(Database, 91);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_EQUIP_STAT"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.PlayerField.Add(MakeSpellTrap(107, 0, false));
		FString Error;
		Report.Check(Duel.StartScenario(Scenario, Error), TEXT("generic equip scenario starts"));
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		const int32 EquipUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 107);
		LoadTestScript(Runtime, 107, TEXT(R"JSON({"id":"test_equip_stats","trigger":"equip_continuous","operations":[{"op":"modify_atk","target":"$self","amount":700,"mode":"flat"},{"op":"modify_def","target":"$self","amount":300,"mode":"flat"}]})JSON"));
		if (Runtime && BlueEyesUid != 0 && EquipUid != 0)
		{
			FDuelCard* Equip = Duel.FindSpellTrap(EquipUid);
			FDuelCard* Target = Duel.FindMonster(BlueEyesUid);
			Report.Check(Equip && Target, TEXT("generic equip and its target are on the field"));
			if (Equip && Target)
			{
				Equip->EquippedToUid = Target->Uid;
				Runtime->RecomputeContinuous();
				Report.Check(Duel.GetAtk(*Target) == Target->Data.Atk + 700,
					TEXT("generic equip applies its continuous ATK bonus"));
				Report.Check(Duel.GetDef(*Target) == Target->Data.Def + 300,
					TEXT("generic equip applies its continuous DEF bonus"));
				Equip->EquippedToUid = 0;
				Runtime->RecomputeContinuous();
				Report.Check(Duel.GetAtk(*Target) == Target->Data.Atk,
					TEXT("detaching the equip removes its ATK bonus"));
			}
		}
	}

	// ---- dynamic and team-wide continuous stats --------------------------
	{
		FDuelEngine Duel(Database, 92);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_DYNAMIC_STAT"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.PlayerField.Add(MakeMonster(2, 1));
		Scenario.PlayerField.Add(MakeMonster(3, 2));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_dynamic_atk","trigger":"continuous","operations":[{"op":"modify_atk","target":"$self","amount":100,"mode":"per_card","count_zone":"all_monsters"}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			Runtime->RecomputeContinuous();
			const FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid);
			Report.Check(BlueEyes && Duel.GetAtk(*BlueEyes) == BlueEyes->Data.Atk + 300,
				TEXT("per-card dynamic ATK counts all face-up monsters"));
		}
	}
	{
		FDuelEngine Duel(Database, 93);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_TEAM_STAT"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.PlayerField.Add(MakeMonster(2, 1));
		Scenario.OpponentField.Add(MakeMonster(3, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		const int32 ElfUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 2);
		const int32 OpponentUid = FindUidInSide(Duel.GetSide(EDuelOwner::Opponent), 3);
		LoadTestScript(Runtime, 2, TEXT(R"JSON({"id":"test_team_atk","trigger":"continuous","operations":[{"op":"modify_atk","target":{"zone":"all_monsters","filter":{"controller":"self"}},"amount":200,"mode":"flat"}]})JSON"));
		if (Runtime && BlueEyesUid != 0 && ElfUid != 0 && OpponentUid != 0)
		{
			Runtime->RecomputeContinuous();
			const FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid);
			const FDuelCard* Elf = Duel.FindMonster(ElfUid);
			const FDuelCard* OpponentCard = Duel.FindMonster(OpponentUid);
			Report.Check(BlueEyes && Duel.GetAtk(*BlueEyes) == BlueEyes->Data.Atk + 200
				&& Elf && Duel.GetAtk(*Elf) == Elf->Data.Atk + 200,
				TEXT("team continuous ATK bonus reaches every friendly monster"));
			Report.Check(OpponentCard && Duel.GetAtk(*OpponentCard) == OpponentCard->Data.Atk,
				TEXT("team continuous ATK bonus does not reach the opponent"));
		}
	}
	{
		FDuelEngine Duel(Database, 94);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_FIELD_STAT"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.PlayerField.Add(MakeField(135));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 135, TEXT(R"JSON({"id":"test_field_atk","trigger":"field_continuous","operations":[{"op":"modify_atk","target":{"zone":"all_monsters"},"amount":300,"mode":"flat"}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			Runtime->RecomputeContinuous();
			const FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid);
			Report.Check(BlueEyes && Duel.GetAtk(*BlueEyes) == BlueEyes->Data.Atk + 300,
				TEXT("field-continuous ATK bonus reaches monsters on the field"));
		}
	}

	// ---- per-player Standby gating and count conditions ------------------
	{
		FDuelEngine Duel(Database, 95);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_STANDBY_SIDE"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_standby_side","trigger":"on_standby","condition":{"controller":"self","zone":"self_monster","turn":"self","count_zone":"self_monster","count_min":1},"operations":[{"op":"gain_lp","player":"self","amount":500}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			Runtime->OnStandby(EDuelOwner::Player);
			Report.Check(Duel.GetSide(EDuelOwner::Player).LP == 8500,
				TEXT("self-gated Standby effect fires on the controller's turn"));
			const int32 AfterOwn = Duel.GetSide(EDuelOwner::Player).LP;
			Runtime->OnStandby(EDuelOwner::Opponent);
			Report.Check(Duel.GetSide(EDuelOwner::Player).LP == AfterOwn,
				TEXT("self-gated Standby effect does not fire on the opponent's turn"));
		}
	}

	// ---- Special Summon position parameter --------------------------------
	{
		FDuelEngine Duel(Database, 96);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_SPECIAL_DEFENSE"));
		Scenario.PlayerHand = TArray<int32>{ 1 };
		Scenario.PlayerDeck = TArray<int32>{ 7, 8, 9 };
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 HandUid = FindUidInArray(Duel.GetSide(EDuelOwner::Player).Hand, 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_special_defense","trigger":"on_activate","target":{"zone":"self_hand","count":1,"filter":{"name":"Blue-Eyes White Dragon"}},"operations":[{"op":"special_summon","target":"$target","position":"defense"}]})JSON"));
		if (Runtime && HandUid != 0)
		{
			FDuelCard* HandCard = Duel.FindCard(HandUid);
			if (HandCard)
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *HandCard));
				Report.Check(FindFieldUid(Duel.GetSide(EDuelOwner::Player), 1) != 0,
					TEXT("special_summon with a position still places the monster"));
				const FDuelCard* Placed = Duel.FindMonster(FindFieldUid(Duel.GetSide(EDuelOwner::Player), 1));
				Report.Check(Placed && Placed->Position == EDuelPosition::Defense && Placed->bFaceUp,
					TEXT("special_summon position=defense places face-up Defense Position"));
			}
		}
	}
	{
		FDuelEngine Duel(Database, 97);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_SPECIAL_FACEDOWN"));
		Scenario.PlayerHand = TArray<int32>{ 1 };
		Scenario.PlayerDeck = TArray<int32>{ 7, 8, 9 };
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 HandUid = FindUidInArray(Duel.GetSide(EDuelOwner::Player).Hand, 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_special_facedown","trigger":"on_activate","target":{"zone":"self_hand","count":1,"filter":{"name":"Blue-Eyes White Dragon"}},"operations":[{"op":"special_summon","target":"$target","position":"face_down"}]})JSON"));
		if (Runtime && HandUid != 0)
		{
			FDuelCard* HandCard = Duel.FindCard(HandUid);
			if (HandCard)
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *HandCard));
				const FDuelCard* Placed = Duel.FindMonster(FindFieldUid(Duel.GetSide(EDuelOwner::Player), 1));
				Report.Check(Placed && !Placed->bFaceUp && Placed->Position == EDuelPosition::Defense,
					TEXT("special_summon position=face_down places a Set monster"));
			}
		}
	}

	// ---- attack locks, direct permission and maximum attackers -----------
	{
		FDuelEngine Duel(Database, 98);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_ATTACK_LOCK"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.OpponentField.Add(MakeMonster(2, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		const int32 ElfUid = FindUidInSide(Duel.GetSide(EDuelOwner::Opponent), 2);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_attack_lock","trigger":"continuous","operations":[{"op":"attack_lock","target":{"zone":"opponent_monster"},"mode":"cannot_attack"},{"op":"attack_directly","target":"$self"},{"op":"attack_lock","target":{"zone":"all_monsters"},"mode":"max_attackers","player":"both","side_wide":true}]})JSON"));
		if (Runtime && BlueEyesUid != 0 && ElfUid != 0)
		{
			Runtime->RecomputeContinuous();
			const FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid);
			const FDuelCard* Elf = Duel.FindMonster(ElfUid);
			Report.Check(Elf && !Runtime->CanCardAttack(*Elf),
				TEXT("continuous attack_lock blocks the filtered monster"));
			Report.Check(BlueEyes && Runtime->CanAttackDirectly(*BlueEyes)
				&& Runtime->CanDeclareAttack(*BlueEyes, true),
				TEXT("attack_directly grants a direct attack permission"));
			Report.Check(Runtime->GetMaxAttackers(EDuelOwner::Player) == 1
				&& Runtime->GetMaxAttackers(EDuelOwner::Opponent) == 1,
				TEXT("max_attackers side lock caps each player to one attacker"));
		}
	}

	// ---- battle damage, damage-step and attacker-destroy triggers --------
	{
		FDuelEngine Duel(Database, 99);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_BATTLE_TRIGGERS"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.OpponentField.Add(MakeMonster(2, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		const int32 ElfUid = FindUidInSide(Duel.GetSide(EDuelOwner::Opponent), 2);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_damage_step","trigger":"on_damage_step","operations":[{"op":"gain_lp","player":"self","amount":100}]})JSON"));
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_battle_damage","trigger":"on_battle_damage","operations":[{"op":"inflict_damage","player":"opponent","amount":300}]})JSON"));
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_attacker_destroy","trigger":"on_battle_destroy_by_attacker","operations":[{"op":"inflict_damage","player":"opponent","amount":500}]})JSON"));
		if (Runtime && BlueEyesUid != 0 && ElfUid != 0)
		{
			Duel.EnterBattlePhase();
			FString AttackError;
			const bool bAttacked = Duel.Attack(BlueEyesUid, ElfUid, AttackError);
			Report.Check(bAttacked, TEXT("battle trigger scenario executes the attack"));
			Report.Check(Duel.GetSide(EDuelOwner::Player).LP == 8100,
				TEXT("on_damage_step fires before damage calculation"));
			Report.Check(Duel.GetSide(EDuelOwner::Opponent).LP == 5000,
				TEXT("on_battle_damage and on_battle_destroy_by_attacker add their damage"));
			Report.Check(FindFieldUid(Duel.GetSide(EDuelOwner::Opponent), 2) == 0,
				TEXT("the battle-destroyed target leaves the field"));
		}
	}

	// ---- deterministic coin/die branches ---------------------------------
	{
		FDuelEngine Duel(Database, 100);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_RANDOM"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_coin","trigger":"on_activate","operations":[{"op":"toss_coin","count":1,"success_min":1,"success_operations":[{"op":"gain_lp","player":"self","amount":700}],"failure_operations":[{"op":"inflict_damage","player":"self","amount":700}]}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid);
			if (BlueEyes)
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *BlueEyes));
				const int32 Result = Runtime->GetLastRandomResult();
				Report.Check(Runtime->GetLastRandomResults().Num() == 1 && (Result == 1 || Result == 2),
					TEXT("toss_coin records exactly one deterministic outcome"));
				const int32 ExpectedLp = Result == 1 ? 8700 : 7300;
				Report.Check(Duel.GetSide(EDuelOwner::Player).LP == ExpectedLp,
					TEXT("toss_coin success/failure branches execute the matching operations"));
			}
		}
	}
	{
		auto RunCoin = [Database](int32 Seed, int32& OutResult)
		{
			FDuelEngine Duel(Database, Seed);
			FDuelScenario Scenario = MakeScenario(TEXT("ERT_RANDOM_SEED"));
			Scenario.PlayerField.Add(MakeMonster(1, 0));
			FString Error;
			Duel.StartScenario(Scenario, Error);
			FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
			const int32 Uid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
			LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_coin_seed","trigger":"on_activate","operations":[{"op":"toss_coin","count":1}]})JSON"));
			OutResult = 0;
			if (Runtime && Uid != 0)
			{
				FDuelCard* Card = Duel.FindMonster(Uid);
				if (Card)
				{
					Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *Card));
					OutResult = Runtime->GetLastRandomResult();
				}
			}
		};
		int32 First = 0;
		int32 Second = 0;
		RunCoin(123, First);
		RunCoin(123, Second);
		Report.Check(First != 0 && First == Second,
			TEXT("the same duel seed produces the same coin outcome"));
	}
	{
		FDuelEngine Duel(Database, 101);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_DIE"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_die","trigger":"on_activate","operations":[{"op":"roll_die","count":1}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid);
			if (BlueEyes)
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *BlueEyes));
				Report.Check(Runtime->GetLastRandomResult() >= 1 && Runtime->GetLastRandomResult() <= 6,
					TEXT("roll_die reports a legal six-sided result"));
			}
		}
	}

	// ---- top-of-Deck placement --------------------------------------------
	{
		FDuelEngine Duel(Database, 102);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_TOP_DECK"));
		Scenario.PlayerHand = TArray<int32>{ 1, 3 };
		Scenario.PlayerDeck = TArray<int32>{ 7, 8, 9 };
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 HandUid = FindUidInArray(Duel.GetSide(EDuelOwner::Player).Hand, 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_top_deck","trigger":"on_activate","target":{"zone":"self_hand","count":1,"filter":{"name":"Baby Dragon"}},"operations":[{"op":"return_to_deck","target":"$target","destination":"deck_top"}]})JSON"));
		if (Runtime && HandUid != 0)
		{
			FDuelCard* HandCard = Duel.FindCard(HandUid);
			if (HandCard)
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *HandCard));
				const FDuelSide& Side = Duel.GetSide(EDuelOwner::Player);
				Report.Check(Side.Deck.Num() > 0 && Side.Deck.Last().Data.Id == 3,
					TEXT("return_to_deck destination=deck_top puts the card on top"));
			}
		}
	}

	// ---- destruction replacement and banish destination ------------------
	{
		FDuelEngine Duel(Database, 103);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_DESTRUCTION_REPLACE"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.PlayerField.Add(MakeMonster(2, 1));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		const int32 ElfUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 2);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_battle_immune","trigger":"continuous","operations":[{"op":"destruction_replacement","target":"$self","mode":"cannot_be_destroyed_by_battle"}]})JSON"));
		LoadTestScript(Runtime, 2, TEXT(R"JSON({"id":"test_effect_destroy","trigger":"on_activate","target":{"zone":"any_monster","count":1,"filter":{"name":"Blue-Eyes White Dragon"}},"operations":[{"op":"destroy","target":"$target"}]})JSON"));
		if (Runtime && BlueEyesUid != 0 && ElfUid != 0)
		{
			Runtime->RecomputeContinuous();
			const FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid);
			Report.Check(BlueEyes && Runtime->ShouldPreventDestruction(*BlueEyes, true, TEXT("battle")),
				TEXT("destruction_replacement registers battle immunity"));
			FDuelCard* Elf = Duel.FindMonster(ElfUid);
			if (Elf)
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *Elf));
			}
			Report.Check(FindFieldUid(Duel.GetSide(EDuelOwner::Player), 1) == 0,
				TEXT("battle-only immunity does not stop effect destruction"));
		}
	}
	{
		FDuelEngine Duel(Database, 104);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_BANISH_DESTINY"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_banish_destiny","trigger":"continuous","operations":[{"op":"destruction_replacement","target":"$self","mode":"banish_instead"}]})JSON"));
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_self_destroy","trigger":"on_activate","target":{"zone":"any_monster","count":1,"filter":{"name":"Blue-Eyes White Dragon"}},"operations":[{"op":"destroy","target":"$target"}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			Runtime->RecomputeContinuous();
			FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid);
			if (BlueEyes)
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *BlueEyes));
			}
			Report.Check(Duel.GetSide(EDuelOwner::Player).Banished.ContainsByPredicate(
				[](const FDuelCard& Card) { return Card.Data.Id == 1; }),
				TEXT("destruction_replacement mode=banish_instead banishes the destroyed card"));
		}
	}

	// ---- Spirit return, inherent summon and Union equip ------------------
	{
		FDuelEngine Duel(Database, 105);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_SPIRIT"));
		Scenario.PlayerField.Add(MakeMonster(677, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		LoadTestScript(Runtime, 677, TEXT(R"JSON({"id":"test_spirit","trigger":"continuous","operations":[{"op":"spirit_return","target":"$self"}]})JSON"));
		if (Runtime)
		{
			Runtime->RecomputeContinuous();
			Runtime->OnEnd(EDuelOwner::Player);
			Report.Check(Duel.GetSide(EDuelOwner::Player).Hand.ContainsByPredicate(
				[](const FDuelCard& Card) { return Card.Data.Id == 677; })
				&& FindFieldUid(Duel.GetSide(EDuelOwner::Player), 677) == 0,
				TEXT("Spirit return sends the monster from the field to its owner's hand"));
		}
	}
	{
		FDuelEngine Duel(Database, 106);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_INHERENT"));
		Scenario.PlayerHand = TArray<int32>{ 1 };
		Scenario.PlayerDeck = TArray<int32>{ 7, 8, 9 };
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 HandUid = FindUidInArray(Duel.GetSide(EDuelOwner::Player).Hand, 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_inherent","trigger":"inherent_summon","condition":{"zone":"self_hand"},"operations":[{"op":"inherent_special_summon","target":"$self"}]})JSON"));
		if (Runtime && HandUid != 0)
		{
			FString SummonError;
			Report.Check(Duel.SpecialSummon(HandUid, SummonError),
				TEXT("inherent_summon activates through the engine's Special Summon path"));
			Report.Check(FindFieldUid(Duel.GetSide(EDuelOwner::Player), 1) != 0,
				TEXT("inherent_special_summon bypasses effect-summon restrictions"));
		}
	}
	{
		FDuelEngine Duel(Database, 107);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_UNION"));
		Scenario.PlayerField.Add(MakeMonster(744, 0));
		Scenario.PlayerField.Add(MakeMonster(1, 1));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 UnionUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 744);
		LoadTestScript(Runtime, 744, TEXT(R"JSON({"id":"test_union_equip","trigger":"on_activate","condition":{"controller":"self","zone":"self_monster"},"operations":[{"op":"union_equip","target":{"zone":"any_monster","count":1,"filter":{"name":"Blue-Eyes White Dragon"}}}]})JSON"));
		if (Runtime && UnionUid != 0)
		{
			FDuelCard* Union = Duel.FindMonster(UnionUid);
			if (Union)
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *Union));
			}
			FDuelCard* Equipped = Duel.FindSpellTrap(UnionUid);
			Report.Check(Equipped && Equipped->EquippedToUid != 0,
				TEXT("union_equip moves the Union monster into the Spell/Trap zone"));
			LoadTestScript(Runtime, 744, TEXT(R"JSON({"id":"test_union_unequip","trigger":"on_activate","condition":{"controller":"self","zone":"self_spell_trap"},"operations":[{"op":"union_unequip","target":"$self","position":"attack"}]})JSON"));
			if (Equipped)
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *Equipped));
			}
			Report.Check(Duel.FindMonster(UnionUid) != nullptr && Duel.FindSpellTrap(UnionUid) == nullptr,
				TEXT("union_unequip returns the Union monster to a Monster Zone"));
		}
	}

	// ---- piercing, battle-position locks and activation locks ------------
	{
		FDuelEngine Duel(Database, 108);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_PIERCING"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.OpponentField.Add(MakeMonster(2, 0, true));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		const int32 ElfUid = FindUidInSide(Duel.GetSide(EDuelOwner::Opponent), 2);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_piercing","trigger":"continuous","operations":[{"op":"piercing","target":"$self"}]})JSON"));
		if (Runtime && BlueEyesUid != 0 && ElfUid != 0)
		{
			Runtime->RecomputeContinuous();
			Report.Check(Runtime->HasPiercing(BlueEyesUid),
				TEXT("continuous piercing is registered on the attacker"));
			Duel.EnterBattlePhase();
			FString AttackError;
			Duel.Attack(BlueEyesUid, ElfUid, AttackError);
			Report.Check(Duel.GetSide(EDuelOwner::Opponent).LP == 7000,
				TEXT("piercing battle damage is applied through the engine"));
		}
	}
	{
		FDuelEngine Duel(Database, 109);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_POSITION_LOCK"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_position_lock","trigger":"continuous","operations":[{"op":"battle_position_lock","target":"$self","mode":"cannot_change"}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			Runtime->RecomputeContinuous();
			const FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid);
			Report.Check(BlueEyes && Runtime->IsPositionChangeLocked(*BlueEyes),
				TEXT("battle_position_lock blocks manual position changes"));
		}
	}
	{
		FDuelEngine Duel(Database, 110);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_BATTLE_END_DEFENSE"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_battle_end_defense","trigger":"continuous","operations":[{"op":"battle_position_lock","target":"$self","mode":"defense_at_end"}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			Runtime->RecomputeContinuous();
			Runtime->OnBattleEnd();
			const FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid);
			Report.Check(BlueEyes && BlueEyes->Position == EDuelPosition::Defense,
				TEXT("battle_position_lock mode=defense_at_end changes position after the Battle Phase"));
		}
	}
	{
		FDuelEngine Duel(Database, 111);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_ACTIVATION_LOCK"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.PlayerField.Add(MakeSpellTrap(107, 0, false));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 SpellUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 107);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_spell_lock","trigger":"continuous","operations":[{"op":"lock_activation","target":{"zone":"all_spell_traps"},"mode":"spell_activation"}]})JSON"));
		if (Runtime && SpellUid != 0)
		{
			Runtime->RecomputeContinuous();
			const FDuelCard* Spell = Duel.FindSpellTrap(SpellUid);
			Report.Check(Runtime->IsSpellActivationLocked() && Spell && Runtime->IsCardActivationLocked(*Spell),
				TEXT("lock_activation mode=spell_activation blocks Spell activation"));
		}
	}

	// ---- named field, leave-field, position and tribute triggers ---------
	{
		FDuelEngine Duel(Database, 112);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_NAME_FIELD"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.PlayerField.Add(MakeMonster(2, 1));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_named_field","trigger":"on_activate","condition":{"name_on_field":"Blue-Eyes White Dragon"},"operations":[{"op":"gain_lp","player":"self","amount":100}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid);
			if (BlueEyes)
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *BlueEyes));
			}
			Report.Check(Duel.GetSide(EDuelOwner::Player).LP == 8100,
				TEXT("name_on_field condition finds a named face-up card"));
		}
	}
	{
		FDuelEngine Duel(Database, 113);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_LEAVE_FIELD"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_leave_field","trigger":"on_removed_from_field","operations":[{"op":"gain_lp","player":"self","amount":300}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			if (const FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid))
			{
				const FDuelCard Snapshot = *BlueEyes;
				Duel.GetSideMutable(EDuelOwner::Player).Monsters[0] = FDuelCard();
				Runtime->OnCardLeftField(Snapshot);
			}
			Report.Check(Duel.GetSide(EDuelOwner::Player).LP == 8300,
				TEXT("on_removed_from_field fires after the source has left its zone"));
		}
	}
	{
		FDuelEngine Duel(Database, 114);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_POSITION_TRIGGER"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_position_trigger","trigger":"on_position_change","operations":[{"op":"gain_lp","player":"self","amount":250}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			if (FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid))
			{
				Runtime->OnPositionChanged(*BlueEyes, EDuelPosition::Attack);
			}
			Report.Check(Duel.GetSide(EDuelOwner::Player).LP == 8250,
				TEXT("on_position_change fires with the previous position"));
		}
	}
	{
		FDuelEngine Duel(Database, 115);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_TRIBUTE_TRIGGER"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_tribute_trigger","trigger":"on_tribute_summon","operations":[{"op":"gain_lp","player":"self","amount":350}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			if (const FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid))
			{
				FDEffectEvent Event = MakeSourceEvent(EDEffectTrigger::OnTributeSummon, *BlueEyes);
				Event.TributeCount = 1;
				Runtime->FireEvent(Event);
			}
			Report.Check(Duel.GetSide(EDuelOwner::Player).LP == 8350,
				TEXT("on_tribute_summon carries the tribute count"));
		}
	}
	{
		FDuelEngine Duel(Database, 116);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_SUMMON_LOCK"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_summon_lock","trigger":"continuous","operations":[{"op":"summon_lock","player":"both","mode":"both"}]})JSON"));
		if (Runtime)
		{
			Runtime->RecomputeContinuous();
			Report.Check(Runtime->IsSummonLocked(EDuelOwner::Player, false)
				&& Runtime->IsSummonLocked(EDuelOwner::Player, true)
				&& Runtime->IsSummonLocked(EDuelOwner::Opponent, true),
				TEXT("summon_lock blocks Normal and Special Summons for both players"));
		}
	}

	// ---- attack negation and dynamic damage ------------------------------
	{
		FDuelEngine Duel(Database, 117);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_ATTACK_NEGATE"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_negate_attack","trigger":"on_attack_target","operations":[{"op":"negate_attack"}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			if (FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid))
			{
				Runtime->OnAttackTarget(*BlueEyes, nullptr);
			}
			Report.Check(Runtime->ConsumeAttackNegated(),
				TEXT("negate_attack marks the current attack as negated"));
			Report.Check(!Runtime->ConsumeAttackNegated(),
				TEXT("the attack-negation flag is consumed once"));
		}
	}
	{
		FDuelEngine Duel(Database, 118);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_DYNAMIC_DAMAGE"));
		Scenario.PlayerField.Add(MakeMonster(1, 0));
		Scenario.OpponentField.Add(MakeMonster(2, 0));
		Scenario.OpponentField.Add(MakeMonster(3, 1));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 BlueEyesUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 1);
		LoadTestScript(Runtime, 1, TEXT(R"JSON({"id":"test_dynamic_damage","trigger":"on_activate","operations":[{"op":"inflict_damage","player":"opponent","amount":200,"mode":"per_card","count_zone":"opponent_monster"}]})JSON"));
		if (Runtime && BlueEyesUid != 0)
		{
			if (FDuelCard* BlueEyes = Duel.FindMonster(BlueEyesUid))
			{
				Runtime->FireEvent(MakeSourceEvent(EDEffectTrigger::OnActivate, *BlueEyes));
			}
			Report.Check(Duel.GetSide(EDuelOwner::Opponent).LP == 7600,
				TEXT("dynamic damage scales with the selected zone count"));
		}
	}

	// ---- activation negation through a Counter Trap response -------------
	{
		FDuelEngine Duel(Database, 119);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_NEGATE_ACTIVATION"));
		Scenario.PlayerField.Add(MakeSpellTrap(927, 0, true));
		Scenario.OpponentField.Add(MakeMonster(2, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 TrapUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 927);
		const int32 TargetUid = FindUidInSide(Duel.GetSide(EDuelOwner::Opponent), 2);
		LoadTestScript(Runtime, 927, TEXT(R"JSON({"id":"test_counter_negate","trigger":"on_activate","target":{"zone":"chain_link"},"operations":[{"op":"negate","target":"$target"}]})JSON"));
		if (Runtime && TrapUid != 0 && TargetUid != 0)
		{
			FDuelCard* Trap = Duel.FindSpellTrap(TrapUid);
			FDuelCard* Target = Duel.FindMonster(TargetUid);
			if (Trap && Target)
			{
				Trap->SetTurn = 0;
				FDuelChainLink Link;
				Link.CardUid = Target->Uid;
				Link.CardId = Target->Data.Id;
				Link.Controller = EDuelOwner::Opponent;
				Link.Speed = EDuelSpellSpeed::Speed1;
				Link.bCardEffect = false;
				const int32 ChainLink = Duel.StartChain(Link, Error);
				FString TrapError;
				Report.Check(ChainLink == 1 && Duel.ActivateCounterTrapResponse(TrapUid, 1, TrapError),
					TEXT("a set Counter Trap can respond to an activation"));
				const TArray<FDuelChainLink>& Links = Duel.GetChainLinks();
				Report.Check(Links.Num() > 0 && Links[0].bNegated,
					TEXT("negate operation marks the responding chain link negated"));
			}
		}
	}

	// ---- activation persistence from subtype and data scripts ------------
	{
		FDuelEngine Duel(Database, 121);
		Duel.SetAutoAnswerAllChoices(true);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_EQUIP_ACTIVATION"));
		Scenario.PlayerHand = TArray<int32>{ 107 };
		Scenario.PlayerDeck = TArray<int32>{ 7, 8, 9 };
		Scenario.PlayerField.Add(MakeMonster(9, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 SpellUid = FindUidInArray(Duel.GetSide(EDuelOwner::Player).Hand, 107);
		const int32 WarriorUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 9);
		if (Runtime && SpellUid != 0 && WarriorUid != 0)
		{
			FString ActivateError;
			Report.Check(Duel.ActivateSpell(SpellUid, ActivateError),
				TEXT("generic Equip Spell activates through the data script"));
			const FDuelCard* Equip = Duel.FindSpellTrap(SpellUid);
			Report.Check(Equip && Equip->bFaceUp && Equip->EquippedToUid == WarriorUid,
				TEXT("generic Equip Spell stays face-up and attaches to its target"));
			const FDuelCard* Warrior = Duel.FindMonster(WarriorUid);
			Report.Check(Warrior && Duel.GetAtk(*Warrior) == Warrior->Data.Atk + 300,
				TEXT("generic Equip Spell's continuous stat script is recalculated"));
		}
	}
	{
		FDuelEngine Duel(Database, 1211);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_EQUIP_TARGET_CHOICE"));
		Scenario.PlayerHand = TArray<int32>{ 107 };
		Scenario.PlayerDeck = TArray<int32>{ 7, 8, 9 };
		Scenario.PlayerField.Add(MakeMonster(9, 0));
		Scenario.PlayerField.Add(MakeMonster(9, 1));
		Scenario.OpponentField.Add(MakeMonster(9, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		const FDuelSide& PlayerSide = Duel.GetSide(EDuelOwner::Player);
		const int32 SpellUid = FindUidInArray(PlayerSide.Hand, 107);
		const int32 FirstUid = PlayerSide.Monsters.IsValidIndex(0) ? PlayerSide.Monsters[0].Uid : 0;
		const int32 SecondUid = PlayerSide.Monsters.IsValidIndex(1) ? PlayerSide.Monsters[1].Uid : 0;
		if (SpellUid != 0 && FirstUid != 0 && SecondUid != 0)
		{
			FString ActivateError;
			Report.Check(Duel.ActivateSpell(SpellUid, ActivateError),
				TEXT("Equip Spell with several legal targets activates"));
			const FDuelChoiceRequest* Choice = Duel.GetPendingChoice();
			Report.Check(Choice && Choice->Options.Num() == 2,
				TEXT("equip target choice offers both own monsters and excludes the opponent"));
			const bool bOffersSecond = Choice && Choice->Options.ContainsByPredicate(
				[SecondUid](const FDuelChoiceOption& Option) { return Option.CardUid == SecondUid; });
			Report.Check(bOffersSecond, TEXT("the exact second monster is a selectable equip target"));
			FString AnswerError;
			Report.Check(Choice && Duel.AnswerChoice(Choice->RequestId, TArray<int32>{ SecondUid }, AnswerError),
				TEXT("the equip target choice can be answered"));
			const FDuelCard* Equip = Duel.FindSpellTrap(SpellUid);
			Report.Check(Equip && Equip->EquippedToUid == SecondUid,
				TEXT("the chosen monster receives the Equip Spell"));
			const FDuelCard* First = Duel.FindMonster(FirstUid);
			const FDuelCard* Second = Duel.FindMonster(SecondUid);
			Report.Check(First && Second && Duel.GetAtk(*Second) == Second->Data.Atk + 300
				&& Duel.GetAtk(*First) == First->Data.Atk,
				TEXT("only the chosen monster receives the equip bonus"));
		}
	}
	{
		FDuelEngine Duel(Database, 1212);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_LEGACY_EQUIP_TARGET"));
		Scenario.PlayerHand = TArray<int32>{ 117 };
		Scenario.PlayerDeck = TArray<int32>{ 7, 8, 9 };
		Scenario.PlayerField.Add(MakeMonster(9, 0));
		Scenario.PlayerField.Add(MakeMonster(9, 1));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		const FDuelSide& PlayerSide = Duel.GetSide(EDuelOwner::Player);
		const int32 SpellUid = FindUidInArray(PlayerSide.Hand, 117);
		const int32 SecondUid = PlayerSide.Monsters.IsValidIndex(1) ? PlayerSide.Monsters[1].Uid : 0;
		if (SpellUid != 0 && SecondUid != 0)
		{
			FString ActivateError;
			Report.Check(Duel.ActivateSpell(SpellUid, ActivateError),
				TEXT("legacy Equip Spell activates and asks for its target"));
			const FDuelChoiceRequest* Choice = Duel.GetPendingChoice();
			Report.Check(Choice && Choice->Options.Num() == 2,
				TEXT("legacy equip target choice lists every legal monster"));
			FString AnswerError;
			Report.Check(Choice && Duel.AnswerChoice(Choice->RequestId, TArray<int32>{ SecondUid }, AnswerError),
				TEXT("legacy equip target choice can be answered"));
			const FDuelCard* Equip = Duel.FindSpellTrap(SpellUid);
			Report.Check(Equip && Equip->EquippedToUid == SecondUid,
				TEXT("legacy Equip Spell attaches to the chosen monster"));
		}
	}
	{
		FDuelEngine Duel(Database, 122);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_FIELD_ACTIVATION"));
		Scenario.PlayerHand = TArray<int32>{ 135 };
		Scenario.PlayerDeck = TArray<int32>{ 7, 8, 9 };
		Scenario.PlayerField.Add(MakeMonster(34, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 SpellUid = FindUidInArray(Duel.GetSide(EDuelOwner::Player).Hand, 135);
		const int32 BeastUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 34);
		if (Runtime && SpellUid != 0 && BeastUid != 0)
		{
			FString ActivateError;
			Report.Check(Duel.ActivateSpell(SpellUid, ActivateError),
				TEXT("generic Field Spell activates through the data script"));
			const FDuelCard* Beast = Duel.FindMonster(BeastUid);
			Report.Check(Duel.GetSide(EDuelOwner::Player).Field.Data.Id == 135,
				TEXT("generic Field Spell remains in the Field Zone"));
			Report.Check(Beast && Duel.GetAtk(*Beast) == Beast->Data.Atk + 200,
				TEXT("generic Field Spell's continuous stat script is recalculated"));
		}
	}
	{
		FDuelEngine Duel(Database, 123);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_CONTINUOUS_SPELL_ACTIVATION"));
		Scenario.PlayerHand = TArray<int32>{ 378 };
		Scenario.PlayerDeck = TArray<int32>{ 7, 8, 9 };
		Scenario.OpponentField.Add(MakeMonster(30, 0));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 SpellUid = FindUidInArray(Duel.GetSide(EDuelOwner::Player).Hand, 378);
		const int32 InsectUid = FindUidInSide(Duel.GetSide(EDuelOwner::Opponent), 30);
		if (Runtime && SpellUid != 0 && InsectUid != 0)
		{
			FString ActivateError;
			Report.Check(Duel.ActivateSpell(SpellUid, ActivateError),
				TEXT("generic Continuous Spell activates through the data script"));
			Report.Check(Duel.FindSpellTrap(SpellUid) != nullptr,
				TEXT("generic Continuous Spell remains face-up after activation"));
			const FDuelCard* Insect = Duel.FindMonster(InsectUid);
			Report.Check(Insect && !Runtime->CanCardAttack(*Insect),
				TEXT("generic Continuous Spell registers its continuous lock"));
		}
	}
	{
		FDuelEngine Duel(Database, 124);
		FDuelScenario Scenario = MakeScenario(TEXT("ERT_CONTINUOUS_TRAP_ACTIVATION"));
		Scenario.PlayerField.Add(MakeSpellTrap(405, 0, true));
		FString Error;
		Duel.StartScenario(Scenario, Error);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		const int32 TrapUid = FindUidInSide(Duel.GetSide(EDuelOwner::Player), 405);
		if (Runtime && TrapUid != 0)
		{
			if (FDuelCard* Trap = Duel.FindSpellTrap(TrapUid))
			{
				Trap->SetTurn = 0;
			}
			FString ActivateError;
			Report.Check(Duel.ActivateSetTrap(TrapUid, ActivateError),
				TEXT("generic Continuous Trap activates from its Set state"));
			const FDuelCard* Trap = Duel.FindSpellTrap(TrapUid);
			Report.Check(Trap && Trap->bFaceUp,
				TEXT("generic Continuous Trap remains face-up after activation"));
			Report.Check(Runtime->IsTrapActivationLocked(),
				TEXT("generic Continuous Trap registers its continuous lock"));
		}
	}

	// ---- unknown operations still fail loudly ----------------------------
	{
		FDuelEngine Duel(Database, 120);
		FDAEffectRuntime* Runtime = Duel.GetEffectRuntime();
		FString Error;
		const bool bUnknown = Runtime
			&& !Runtime->LoadScriptJsonText(TEXT("{\"card_id\":1,\"scripts\":[{\"id\":\"bad_op\",\"trigger\":\"on_activate\",\"operations\":[{\"op\":\"not_a_real_op\"}]}]}"), Error);
		Report.Check(bUnknown && Error.Contains(TEXT("unknown operation")),
			TEXT("unknown operations are rejected at script load"));
		Error.Reset();
		const bool bNestedUnknown = Runtime
			&& !Runtime->LoadScriptJsonText(TEXT("{\"card_id\":1,\"scripts\":[{\"id\":\"bad_nested\",\"trigger\":\"on_activate\",\"operations\":[{\"op\":\"toss_coin\",\"success_operations\":[{\"op\":\"not_a_real_op\"}]}]}]}"), Error);
		Report.Check(bNestedUnknown && Error.Contains(TEXT("unknown operation")),
			TEXT("unknown operations inside random branches are rejected"));
	}

	LogReport(Report);
	return Report;
}

void UDAEffectRuntimeSelfTestSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	if (FParse::Param(FCommandLine::Get(), TEXT("DAEffectRuntimeSelfTest")))
	{
		TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateUObject(this, &UDAEffectRuntimeSelfTestSubsystem::Tick), 2.0f);
	}
}

void UDAEffectRuntimeSelfTestSubsystem::Deinitialize()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}
	Super::Deinitialize();
}

bool UDAEffectRuntimeSelfTestSubsystem::Tick(float DeltaTime)
{
	if (bFinished)
	{
		return false;
	}
	WaitSeconds += DeltaTime;
	if (WaitSeconds > 30.f)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("DAEffectRuntimeSelfTest: timed out waiting for the world/card database."));
		bFinished = true;
		TickerHandle.Reset();
		FPlatformMisc::RequestExit(false);
		return false;
	}
	UGameInstance* GameInstance = GetGameInstance();
	UWorld* World = GameInstance ? GameInstance->GetWorld() : nullptr;
	if (!World || !World->HasBegunPlay())
	{
		return true;
	}
	UCardDatabaseSubsystem* Database = GameInstance->GetSubsystem<UCardDatabaseSubsystem>();
	if (!Database || !Database->IsLoaded())
	{
		return true;
	}

	FDAEffectRuntimeSelfTest::Run(Database);
	bFinished = true;
	if (TickerHandle.IsValid())
	{
		TickerHandle.Reset();
	}
	FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float)
	{
		FPlatformMisc::RequestExit(false);
		return false;
	}), 1.0f);
	return false;
}

namespace
{
	FAutoConsoleCommandWithWorldAndArgs GDAEffectRuntimeSelfTestCommand(
		TEXT("da.EffectRuntimeSelfTest"),
		TEXT("Run the data-driven effect runtime self-test."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			(void)Args;
			if (!World || !World->GetGameInstance())
			{
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("da.EffectRuntimeSelfTest: no game instance."));
				return;
			}
			UCardDatabaseSubsystem* Database = World->GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>();
			const FDEffectRuntimeSelfTestReport Report = FDAEffectRuntimeSelfTest::Run(Database);
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Report.ToSummary());
		}));
}
