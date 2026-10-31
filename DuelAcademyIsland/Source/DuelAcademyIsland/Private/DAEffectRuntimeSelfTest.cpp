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

	// ---- Morphing Jar: FLIP discard then draw ----------------------------
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
