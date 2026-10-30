#include "DADuelRulesSelfTest.h"

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
	TArray<int32> BuildMainDeck(UCardDatabaseSubsystem* Database, int32 Count)
	{
		TArray<int32> Result;
		if (!Database)
		{
			return Result;
		}
		TArray<int32> Ids;
		for (const TPair<int32, FCardRecord>& Pair : Database->GetCards())
		{
			Ids.Add(Pair.Key);
		}
		Ids.Sort();
		for (int32 CardId : Ids)
		{
			if (Result.Num() >= Count)
			{
				break;
			}
			const FCardRecord* Record = Database->FindCard(CardId);
			if (!Record || Record->CardType.Contains(TEXT("Fusion")))
			{
				continue;
			}
			Result.Add(CardId);
		}
		return Result;
	}

	int32 FindFusionId(UCardDatabaseSubsystem* Database)
	{
		if (!Database)
		{
			return 0;
		}
		for (const TPair<int32, FCardRecord>& Pair : Database->GetCards())
		{
			if (Pair.Value.CardType.Contains(TEXT("Fusion")))
			{
				return Pair.Key;
			}
		}
		return 0;
	}

	const FCardRecord* FindRecordByPredicate(UCardDatabaseSubsystem* Database,
		TFunctionRef<bool(const FCardRecord&)> Predicate)
	{
		if (!Database)
		{
			return nullptr;
		}
		for (const TPair<int32, FCardRecord>& Pair : Database->GetCards())
		{
			if (Predicate(Pair.Value))
			{
				return &Pair.Value;
			}
		}
		return nullptr;
	}

	void LogReport(const FDuelRulesSelfTestReport& Report)
	{
		for (const FString& Line : Report.Lines)
		{
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Line);
		}
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Report.ToSummary());
	}
}

FDuelRulesSelfTestReport FDuelRulesSelfTest::Run(UCardDatabaseSubsystem* Database)
{
	FDuelRulesSelfTestReport Report;
	Report.Check(Database != nullptr, TEXT("card database is available"));
	if (!Database)
	{
		LogReport(Report);
		return Report;
	}

	// ---- deck validation / banned list -----------------------------------
	const TArray<int32> Main40 = BuildMainDeck(Database, 40);
	const int32 FusionId = FindFusionId(Database);
	TArray<int32> ExtraOne;
	if (FusionId > 0)
	{
		ExtraOne.Add(FusionId);
	}
	Report.Check(Main40.Num() == 40, TEXT("synthetic 40-card Main Deck was built"));
	Report.Check(FusionId > 0, TEXT("synthetic Extra Deck has a Fusion Monster"));

	{
		FDuelEngine Duel(Database, 41);
		const FDuelDeckValidationResult Valid = Duel.ValidateDeck(Main40, ExtraOne);
		Report.Check(Valid.bValid && Valid.MainCount == 40 && Valid.ExtraCount == ExtraOne.Num(),
			TEXT("40-card Main Deck and legal Extra Deck validate"));

		TArray<int32> Main39 = Main40;
		Main39.Pop();
		Report.Check(!Duel.ValidateDeck(Main39, ExtraOne).bValid, TEXT("39-card Main Deck is rejected"));

		TArray<int32> Main61 = BuildMainDeck(Database, 61);
		Report.Check(Main61.Num() == 61, TEXT("synthetic 61-card deck was built"));
		Report.Check(!Duel.ValidateDeck(Main61, ExtraOne).bValid, TEXT("61-card Main Deck is rejected"));

		TArray<int32> FourCopies;
		FourCopies.Add(Main40[0]);
		FourCopies.Add(Main40[0]);
		FourCopies.Add(Main40[0]);
		FourCopies.Add(Main40[0]);
		for (int32 I = 1; I < Main40.Num(); ++I)
		{
			FourCopies.Add(Main40[I]);
		}
		Report.Check(!Duel.ValidateDeck(FourCopies, ExtraOne).bValid, TEXT("four copies of one card are rejected"));

		if (FusionId > 0)
		{
			TArray<int32> Extra21;
			for (int32 I = 0; I < 21; ++I)
			{
				Extra21.Add(FusionId);
			}
			Report.Check(!Duel.ValidateDeck(Main40, Extra21).bValid, TEXT("21-card Extra Deck is rejected"));
		}

		FDuelBannedListRuleset Banned;
		Banned.SetLimit(Main40[0], 0, TEXT("self-test ban"));
		Duel.SetBannedList(Banned);
		Report.Check(!Duel.ValidateDeck(Main40, ExtraOne).bValid, TEXT("banned card is rejected"));

		FDuelBannedListRuleset Limited;
		Limited.SetLimit(Main40[1], 1, TEXT("self-test limit"));
		Duel.SetBannedList(Limited);
		TArray<int32> TwoLimited = Main40;
		TwoLimited.Pop();
		TwoLimited.Add(Main40[1]);
		Report.Check(!Duel.ValidateDeck(TwoLimited, ExtraOne).bValid, TEXT("two copies of a limited card are rejected"));

		Duel.SetBannedList(FDuelBannedListRuleset());
		FString JsonError;
		const bool bJsonLoaded = Duel.LoadBannedListFromJson(
			TEXT("{\"ruleset_id\":\"self_test\",\"cards\":[{\"id\":1,\"limit\":0,\"reason\":\"test\"}]}"),
			JsonError);
		Report.Check(bJsonLoaded && Duel.GetBannedList().IsBanned(1), TEXT("banned-list JSON injection works"));
		Duel.SetBannedList(FDuelBannedListRuleset());
	}

	// ---- choices / targeting ---------------------------------------------
	{
		FDuelEngine Duel(Database, 42);
		Duel.Start(TEXT("fire"), TEXT("jaden"));
		Report.Check(Duel.IsStarted() && Duel.GetSide(EDuelOwner::Player).Hand.Num() >= 3,
			TEXT("choice test duel started with a hand"));

		const TArray<FDuelCard>& Hand = Duel.GetSide(EDuelOwner::Player).Hand;
		if (Duel.IsStarted() && Hand.Num() >= 3)
		{
			FDuelChoiceRequest Request;
			Request.Type = EDuelChoiceType::SelectCard;
			Request.Prompt = TEXT("Choose a target");
			Request.Side = EDuelOwner::Player;
			Request.MinSelections = 1;
			Request.MaxSelections = 1;
			Request.SourceCardUid = Hand[0].Uid;
			Request.SourceCardId = Hand[0].Data.Id;
			Request.TargetZone = EDuelZone::Monster;

			FDuelChoiceOption First;
			First.Id = 1;
			First.Label = Hand[0].Data.Name;
			First.CardUid = Hand[0].Uid;
			First.CardId = Hand[0].Data.Id;
			First.Zone = EDuelZone::Hand;
			Request.Options.Add(First);

			FDuelChoiceOption Second;
			Second.Id = 2;
			Second.Label = Hand[1].Data.Name;
			Second.CardUid = Hand[1].Uid;
			Second.CardId = Hand[1].Data.Id;
			Second.Zone = EDuelZone::Hand;
			Second.bEnabled = false;
			Second.DisabledReason = TEXT("not a legal target");
			Request.Options.Add(Second);
			Request.DefaultOptionIds.Add(1);

			bool bResolverCalled = false;
			TArray<int32> ResolvedIds;
			const int32 RequestId = Duel.RequestChoice(Request, [&](const FDuelChoiceRequest&, const TArray<int32>& Ids)
			{
				bResolverCalled = true;
				ResolvedIds = Ids;
			});
			Report.Check(RequestId > 0 && Duel.HasPendingChoice() && Duel.GetPendingChoice()->RequestId == RequestId,
				TEXT("choice is queued and inspectable"));

			FString AnswerError;
			TArray<int32> DisabledAnswer;
			DisabledAnswer.Add(2);
			Report.Check(!Duel.AnswerChoice(RequestId, DisabledAnswer, AnswerError),
				TEXT("disabled choice option is rejected"));

			TArray<int32> LegalAnswer;
			LegalAnswer.Add(1);
			Report.Check(Duel.AnswerChoice(RequestId, LegalAnswer, AnswerError),
				TEXT("legal choice option is accepted"));
			Report.Check(bResolverCalled && ResolvedIds.Num() == 1 && ResolvedIds[0] == 1,
				TEXT("choice resolver received the selection"));
			Report.Check(!Duel.HasPendingChoice(), TEXT("choice queue drains after answering"));

			FDuelChoiceRequest AutoRequest = Request;
			AutoRequest.RequestId = 0;
			AutoRequest.Prompt = TEXT("Auto target");
			Duel.RequestChoice(AutoRequest, nullptr);
			FString AutoError;
			Report.Check(Duel.AutoAnswerPendingChoice(&AutoError), TEXT("AI/default auto-answer resolves a choice"));
			Report.Check(!Duel.HasPendingChoice(), TEXT("auto-answer removes the pending choice"));

			FDuelChoiceRequest AiRequest = Request;
			AiRequest.RequestId = 0;
			AiRequest.Side = EDuelOwner::Opponent;
			AiRequest.Prompt = TEXT("AI target");
			Duel.RequestChoice(AiRequest, nullptr);
			Report.Check(!Duel.HasPendingChoiceFor(EDuelOwner::Opponent),
				TEXT("opponent choices are auto-answered immediately"));

			bool bOptionalAnswered = false;
			Duel.RequestOptionalTrigger(Hand[0], TEXT("Optional test"), true,
				[&bOptionalAnswered](bool bActivate)
				{
					bOptionalAnswered = bActivate;
				});
			FString OptionalError;
			Report.Check(Duel.HasPendingChoice() && Duel.AutoAnswerPendingChoice(&OptionalError) && bOptionalAnswered,
				TEXT("optional trigger convenience prompt auto-answers yes"));
		}
	}

	// ---- chain order ------------------------------------------------------
	{
		FDuelEngine Duel(Database, 43);
		Duel.Start(TEXT("fire"), TEXT("jaden"));
		const TArray<FDuelCard>& Hand = Duel.GetSide(EDuelOwner::Player).Hand;
		Report.Check(Duel.IsStarted() && Hand.Num() >= 3, TEXT("chain test duel started with a hand"));
		if (Duel.IsStarted() && Hand.Num() >= 3)
		{
			FString ChainError;
			TArray<int32> ResolvedEffects;
			Duel.SetChainEffectResolver([&ResolvedEffects](const FDuelChainLink& Link)
			{
				ResolvedEffects.Add(Link.EffectId);
			});
			FDuelChainLink Link1;
			Link1.CardUid = Hand[0].Uid;
			Link1.Controller = EDuelOwner::Player;
			Link1.Speed = EDuelSpellSpeed::Speed1;
			Link1.EffectId = 101;
			Link1.bCardEffect = false;
			Link1.Label = TEXT("Link1");
			Report.Check(Duel.StartChain(Link1, ChainError) == 1, TEXT("chain starts with link 1"));

			FDuelChainLink Link2;
			Link2.CardUid = Hand[1].Uid;
			Link2.Controller = EDuelOwner::Player;
			Link2.Speed = EDuelSpellSpeed::Speed2;
			Link2.EffectId = 102;
			Link2.bCardEffect = false;
			Link2.Label = TEXT("Link2");
			Report.Check(Duel.AddChainLink(Link2, ChainError) == 2, TEXT("Spell Speed 2 responds to Spell Speed 1"));

			FDuelChainLink Link3;
			Link3.CardUid = Hand[2].Uid;
			Link3.Controller = EDuelOwner::Player;
			Link3.Speed = EDuelSpellSpeed::Speed2;
			Link3.EffectId = 103;
			Link3.bCardEffect = false;
			Link3.Label = TEXT("Link3");
			Report.Check(Duel.AddChainLink(Link3, ChainError) == 3, TEXT("second Spell Speed 2 response is accepted"));

			FDuelChainLink TooSlow = Link1;
			TooSlow.Label = TEXT("TooSlow");
			Report.Check(Duel.AddChainLink(TooSlow, ChainError) == 0,
				TEXT("slower link cannot respond to a faster link"));

			const int32 ResolvedCount = Duel.ResolveChain(ChainError);
			Report.Check(ResolvedCount == 3, TEXT("all three chain links resolve"));
			Report.Check(Duel.GetLastResolvedChain().Num() == 3, TEXT("resolved chain history has three links"));
			Report.Check(Duel.GetResolvedChainOrder().Num() == 3
				&& Duel.GetResolvedChainOrder()[0] == Hand[2].Uid
				&& Duel.GetResolvedChainOrder()[1] == Hand[1].Uid
				&& Duel.GetResolvedChainOrder()[2] == Hand[0].Uid,
				TEXT("chain resolves in reverse link order"));
			Report.Check(ResolvedEffects.Num() == 3 && ResolvedEffects[0] == 103
				&& ResolvedEffects[1] == 102 && ResolvedEffects[2] == 101,
				TEXT("A05 chain effect resolver fires in reverse link order"));
			Report.Check(!Duel.IsChainOpen(), TEXT("chain stack is empty after resolution"));
		}
	}

	// ---- timing / quick-play / counter trap ------------------------------
	{
		FDuelEngine Duel(Database, 44);
		Duel.Start(TEXT("fire"), TEXT("jaden"));

		const FCardRecord* QuickPlay = FindRecordByPredicate(Database, [](const FCardRecord& Card)
		{
			return Card.CardType == TEXT("Spell") && Card.Subtype == TEXT("Quick-Play");
		});
		const FCardRecord* NormalSpell = FindRecordByPredicate(Database, [](const FCardRecord& Card)
		{
			return Card.CardType == TEXT("Spell") && Card.Subtype == TEXT("Normal");
		});
		const FCardRecord* CounterTrap = FindRecordByPredicate(Database, [](const FCardRecord& Card)
		{
			return Card.CardType == TEXT("Trap") && Card.Subtype == TEXT("Counter");
		});

		Report.Check(QuickPlay != nullptr && NormalSpell != nullptr && CounterTrap != nullptr,
			TEXT("timing test cards were found"));
		if (QuickPlay && NormalSpell && CounterTrap)
		{
			FDuelCard QuickCard;
			QuickCard.Data = *QuickPlay;
			QuickCard.Controller = EDuelOwner::Player;
			Report.Check(Duel.IsActivationLegal(QuickCard, EDuelTimingWindow::Battle),
				TEXT("Quick-Play Spell is legal during the Battle Phase"));
			Report.Check(Duel.GetSpellSpeed(QuickCard) == EDuelSpellSpeed::Speed2,
				TEXT("Quick-Play Spell is Spell Speed 2"));

			FDuelCard NormalCard;
			NormalCard.Data = *NormalSpell;
			NormalCard.Controller = EDuelOwner::Player;
			Report.Check(Duel.IsActivationLegal(NormalCard, EDuelTimingWindow::Main1),
				TEXT("Normal Spell is legal during Main Phase 1"));
			Report.Check(!Duel.IsActivationLegal(NormalCard, EDuelTimingWindow::Battle),
				TEXT("Normal Spell is illegal during the Battle Phase"));

			FDuelCard CounterCard;
			CounterCard.Data = *CounterTrap;
			CounterCard.Controller = EDuelOwner::Player;
			Report.Check(Duel.IsActivationLegal(CounterCard, EDuelTimingWindow::ResponseToActivation),
				TEXT("Counter Trap is legal in a response window"));
			Report.Check(!Duel.IsActivationLegal(CounterCard, EDuelTimingWindow::Main1),
				TEXT("Counter Trap is illegal in Main Phase 1"));
			Report.Check(Duel.GetSpellSpeed(CounterCard) == EDuelSpellSpeed::Speed3,
				TEXT("Counter Trap is Spell Speed 3"));
		}
	}

	// ---- ante -------------------------------------------------------------
	{
		FDuelEngine Duel(Database, 45);
		Duel.Start(TEXT("fire"), TEXT("jaden"));
		const TArray<FDuelCard>& PlayerDeck = Duel.GetSide(EDuelOwner::Player).Deck;
		const TArray<FDuelCard>& OpponentDeck = Duel.GetSide(EDuelOwner::Opponent).Deck;
		Report.Check(PlayerDeck.Num() > 0 && OpponentDeck.Num() > 0, TEXT("ante test decks were built"));
		if (PlayerDeck.Num() > 0 && OpponentDeck.Num() > 0)
		{
			Duel.ConfigureAnte(true);
			FString AnteError;
			const int32 PlayerAnteId = PlayerDeck[0].Data.Id;
			const int32 OpponentAnteId = OpponentDeck[0].Data.Id;
			Report.Check(Duel.SelectAnteCard(EDuelOwner::Player, PlayerAnteId, AnteError),
				TEXT("player ante card is selected"));
			Report.Check(Duel.SelectAnteCard(EDuelOwner::Opponent, OpponentAnteId, AnteError),
				TEXT("opponent ante card is selected"));
			Report.Check(Duel.FinalizeAnteSelection(AnteError), TEXT("ante selection finalizes"));

			bool bAnteHookCalled = false;
			Duel.SetAnteResultHook([&bAnteHookCalled](const FDuelAnteState&)
			{
				bAnteHookCalled = true;
			});
			Duel.DebugFinishDuel(true);
			Report.Check(bAnteHookCalled, TEXT("ante result hook fires"));
			const FDuelAnteState& Ante = Duel.GetAnteState();
			Report.Check(Ante.bTransferred && Ante.WinnerCardId == OpponentAnteId,
				TEXT("ante transfers the loser's card to the winner"));

			const FDuelResultStats& Stats = Duel.GetResultStats();
			Report.Check(Stats.bPlayerWon && Stats.Turns > 0 && Stats.OpponentLp == 0,
				TEXT("result statistics are populated on duel end"));
		}
	}

	// ---- puzzle / exam scenario ------------------------------------------
	{
		const TArray<int32> ScenarioCards = BuildMainDeck(Database, 8);
		if (ScenarioCards.Num() >= 8)
		{
			FDuelScenario Scenario;
			Scenario.Id = TEXT("SELFTEST_01");
			Scenario.Name = TEXT("Self-test puzzle");
			Scenario.Objective = TEXT("Summon a monster");
			Scenario.PlayerLp = 4000;
			Scenario.OpponentLp = 4000;
			Scenario.PlayerHand = TArray<int32>{ ScenarioCards[0], ScenarioCards[1], ScenarioCards[2] };
			Scenario.PlayerDeck = TArray<int32>{ ScenarioCards[3], ScenarioCards[4] };
			Scenario.PlayerGraveyard = TArray<int32>{ ScenarioCards[5] };
			Scenario.PlayerExtra = TArray<int32>{ ScenarioCards[6] };
			Scenario.OpponentHand = TArray<int32>{ ScenarioCards[7] };
			Scenario.OpponentDeck = TArray<int32>{ ScenarioCards[3] };
			const FCardRecord* FieldMonsterRecord = Database->FindCard(1);
			if (!FieldMonsterRecord)
			{
				FieldMonsterRecord = FindRecordByPredicate(Database, [](const FCardRecord& Card)
				{
					return Card.CardType.Contains(TEXT("Normal Monster"));
				});
			}
			if (FieldMonsterRecord)
			{
				FDuelScenarioCard FieldCard;
				FieldCard.CardId = FieldMonsterRecord->Id;
				FieldCard.Zone = EDuelZone::Monster;
				FieldCard.ZoneIndex = 0;
				FieldCard.bFaceDown = false;
				FieldCard.bDefense = false;
				Scenario.PlayerField.Add(FieldCard);
			}
			Scenario.TurnLimit = 3;
			Scenario.TimeLimitSeconds = 60.f;
			Scenario.bPlayerGoesFirst = true;
			Scenario.bDrawOnFirstTurn = false;

			FDuelEngine ScenarioDuel(Database, 46);
			FString ScenarioError;
			Report.Check(ScenarioDuel.StartScenario(Scenario, ScenarioError), TEXT("puzzle scenario starts"));
			Report.Check(ScenarioDuel.IsScenarioActive(), TEXT("scenario mode is active"));
			Report.Check(ScenarioDuel.GetSide(EDuelOwner::Player).LP == 4000
				&& ScenarioDuel.GetSide(EDuelOwner::Opponent).LP == 4000,
				TEXT("scenario applies fixed Life Points"));
			Report.Check(ScenarioDuel.GetSide(EDuelOwner::Player).Hand.Num() == 3,
				TEXT("scenario applies a fixed hand without a first-turn draw"));
			Report.Check(ScenarioDuel.GetSide(EDuelOwner::Player).Monsters[0].IsValid(),
				TEXT("scenario places fixed field monsters"));
			Report.Check(ScenarioDuel.GetScenarioPlayerTurnsTaken() == 1 && ScenarioDuel.GetScenarioTurnsRemaining() == 2,
				TEXT("scenario turn limit is tracked"));
			Report.Check(!ScenarioDuel.CheckScenarioTimeout(30.f), TEXT("scenario timeout does not fire early"));
			Report.Check(ScenarioDuel.CheckScenarioTimeout(61.f) && ScenarioDuel.IsOver()
				&& ScenarioDuel.GetWinner() == EDuelOwner::Opponent,
				TEXT("scenario timeout ends the duel as a loss"));

			FDuelEngine TimeoutDuel(Database, 47);
			Report.Check(TimeoutDuel.StartScenario(Scenario, ScenarioError), TEXT("second scenario instance starts"));
			Report.Check(TimeoutDuel.GetScenarioTurnsRemaining() == 2, TEXT("scenario turn remaining is repeatable"));
		}
		else
		{
			Report.Check(false, TEXT("puzzle scenario test cards were built"));
		}
	}

	// ---- existing 137-card regression smoke ------------------------------
	{
		const FString Baseline = FDuelEngine::RunSelfTest(Database, 2);
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Baseline);
		Report.Check(!Baseline.Contains(TEXT("missing")) && Baseline.Contains(TEXT(" 0 stalls,")),
			TEXT("existing AI-vs-AI duel self-test still completes without stalls"));
	}

	LogReport(Report);
	return Report;
}

void UDADuelRulesSelfTestSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	if (FParse::Param(FCommandLine::Get(), TEXT("DADuelRulesSelfTest")))
	{
		TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateUObject(this, &UDADuelRulesSelfTestSubsystem::Tick), 2.0f);
	}
}

void UDADuelRulesSelfTestSubsystem::Deinitialize()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}
	Super::Deinitialize();
}

bool UDADuelRulesSelfTestSubsystem::Tick(float DeltaTime)
{
	if (bFinished)
	{
		return false;
	}
	WaitSeconds += DeltaTime;
	if (WaitSeconds > 30.f)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("DADuelRulesSelfTest: timed out waiting for the world/card database."));
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

	const FDuelRulesSelfTestReport Report = FDuelRulesSelfTest::Run(Database);
	(void)Report;
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
	FAutoConsoleCommandWithWorldAndArgs GDADuelRulesSelfTestCommand(
		TEXT("da.DuelRulesSelfTest"),
		TEXT("Run the duel-rules self-test (choices, chain, timing, deck validation, ante, scenario)."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			(void)Args;
			if (!World || !World->GetGameInstance())
			{
				UE_LOG(LogDuelAcademyIsland, Warning, TEXT("da.DuelRulesSelfTest: no game instance."));
				return;
			}
			UCardDatabaseSubsystem* Database = World->GetGameInstance()->GetSubsystem<UCardDatabaseSubsystem>();
			const FDuelRulesSelfTestReport Report = FDuelRulesSelfTest::Run(Database);
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Report.ToSummary());
		}));
}
