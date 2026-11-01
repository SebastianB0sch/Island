// Duel Academy Island - opponent roster/AI automation tests.

#include "Misc/AutomationTest.h"

#include "DAOpponentSubsystem.h"
#include "DADuelistAI.h"
#include "Engine/GameInstance.h"

#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

#if WITH_DEV_AUTOMATION_TESTS

namespace
{
	UDAOpponentSubsystem* MakeOpponentSubsystemForTest()
	{
		// A GameInstanceSubsystem must be outered to a GameInstance; creating
		// it directly in the transient package triggers a ClassWithin ensure.
		UGameInstance* Outer = NewObject<UGameInstance>(GetTransientPackage());
		return NewObject<UDAOpponentSubsystem>(Outer);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDAOpponentRosterTest, "DuelAcademy.Opponents.Roster",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FDAOpponentRosterTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	UDAOpponentSubsystem* Opponents = MakeOpponentSubsystemForTest();
	if (!TestNotNull(TEXT("Opponent subsystem created"), Opponents))
	{
		return false;
	}

	FString Error;
	if (!TestTrue(TEXT("Roster loads"), Opponents->Reload(Error)))
	{
		AddError(Error);
		return false;
	}

	TestTrue(TEXT("At least 25 duelists"), Opponents->GetOpponents().Num() >= 25);
	TestEqual(TEXT("Thirty-two runtime opponent decks"), Opponents->GetDecks().Num(), 32);
	for (const FDAOpponentDeckDef& RuntimeDeck : Opponents->GetDecks())
	{
		TestTrue(FString::Printf(TEXT("Deck %s has a 40-60 main deck"), *RuntimeDeck.Id),
			RuntimeDeck.Cards.Num() >= 40 && RuntimeDeck.Cards.Num() <= 60);
		TestTrue(FString::Printf(TEXT("Deck %s has at most 15 Extra Deck cards"), *RuntimeDeck.Id),
			RuntimeDeck.Extra.Num() <= 15);
	}
	TestTrue(TEXT("At least 20 AI profiles"), Opponents->GetAIProfiles().Num() >= 20);
	TestNotNull(TEXT("Jaden exists"), Opponents->FindOpponent(TEXT("jaden")));
	TestNotNull(TEXT("Chazz exists"), Opponents->FindOpponent(TEXT("chazz")));
	TestNotNull(TEXT("Zane exists"), Opponents->FindOpponent(TEXT("zane")));
	TestNotNull(TEXT("Mimicry exists"), Opponents->FindOpponent(TEXT("mimicry")));
	TestNotNull(TEXT("Shadow Duelist exists"), Opponents->FindOpponent(TEXT("shadow_duelist")));

	const FDAOpponentDef* Jaden = Opponents->FindOpponent(TEXT("jaden"));
	if (Jaden)
	{
		TestEqual(TEXT("Jaden default deck"), Jaden->DefaultDeck, FString(TEXT("jaden_year1")));
		TestNotNull(TEXT("Jaden deck loaded"), Opponents->FindDeck(Jaden->DefaultDeck));
		TestTrue(TEXT("Jaden deck is legal-size"), Opponents->FindDeck(Jaden->DefaultDeck)->Cards.Num() >= 40);
	}

	TSet<FString> Flags;
	Flags.Add(FString(TEXT("met_jaden")));
	FString Reason;
	TestTrue(TEXT("Jaden unlocked after met flag"),
		Opponents->IsDuelistUnlocked(TEXT("jaden"), TEXT(""), TEXT("Slifer"), Flags, 0, Reason));
	TestFalse(TEXT("Jaden locked without met flag"),
		Opponents->IsDuelistUnlocked(TEXT("jaden"), TEXT(""), TEXT("Slifer"), TSet<FString>(), 0, Reason));
	TestTrue(TEXT("Jaden scheduled in arena Monday AM"),
		Opponents->CanDuelAtLocation(TEXT("jaden"), TEXT("academy"), TEXT("academy_arena"), TEXT("Monday"), TEXT("AM"), Reason));
	TestFalse(TEXT("Jaden not scheduled in volcano"),
		Opponents->CanDuelAtLocation(TEXT("jaden"), TEXT("volcano"), TEXT(""), TEXT("Monday"), TEXT("AM"), Reason));

	TestTrue(TEXT("Unlock Jaden email"), Opponents->UnlockEmail(TEXT("jaden"), TEXT("jaden_01")));
	TestTrue(TEXT("Jaden email visible"), Opponents->IsEmailUnlocked(TEXT("jaden"), TEXT("jaden_01")));
	TestTrue(TEXT("Mark Jaden email read"), Opponents->MarkEmailRead(TEXT("jaden"), TEXT("jaden_01")));

	TestTrue(TEXT("Jaden duel request available"), Opponents->CanRequestDuel(TEXT("jaden"), 10, 0, Reason));
	TestTrue(TEXT("Consume Jaden duel request"), Opponents->ConsumeDuelRequest(TEXT("jaden"), 10, 0, Reason));
	TestFalse(TEXT("Only one Jaden request per day"), Opponents->CanRequestDuel(TEXT("jaden"), 10, 0, Reason));

	// Syrus evolves after three wins.
	FDAOpponentDuelOutcome Outcome;
	Outcome = Opponents->RecordDuelResult(TEXT("syrus"), true);
	Outcome = Opponents->RecordDuelResult(TEXT("syrus"), true);
	Outcome = Opponents->RecordDuelResult(TEXT("syrus"), true);
	TestEqual(TEXT("Syrus wins counted"), Outcome.Wins, 3);
	TestEqual(TEXT("Syrus evolution deck"), Outcome.EvolutionDeckId, FString(TEXT("syrus_roids_plus")));
	TestTrue(TEXT("Syrus evolution unlocked"), Outcome.bEvolutionUnlocked);

	TMap<FString, int32> Counters;
	Counters.Add(FString(TEXT("wins_zane")), 8);
	TestEqual(TEXT("Zane resolves Cyber End deck"), Opponents->ResolveDeckFor(TEXT("zane"), Counters),
		FString(TEXT("zane_cyber_end")));

	// AI policy is data-driven and deterministic.
	const FDAIProfileDef* FusionProfile = Opponents->FindAIProfile(TEXT("fusion"));
	if (TestNotNull(TEXT("Fusion profile exists"), FusionProfile))
	{
		FDAIDuelistAI AI;
		AI.Configure(*FusionProfile, 42);
		TestTrue(TEXT("Fusion strategy maps"), AI.GetStrategy() == EDAAIStrategy::Fusion);

		FCardRecord Polymerization;
		Polymerization.Name = TEXT("Polymerization");
		Polymerization.CardType = TEXT("Spell");
		Polymerization.Subtype = TEXT("Normal");
		Polymerization.Atk = 0;
		Polymerization.Def = 0;

		FCardRecord Fissure;
		Fissure.Name = TEXT("Fissure");
		Fissure.CardType = TEXT("Spell");
		Fissure.Subtype = TEXT("Normal");

		TestTrue(TEXT("Fusion profile values Polymerization above Fissure"),
			AI.ScoreCard(Polymerization) > AI.ScoreCard(Fissure));

		FDAAIDuelSnapshot Snapshot;
		Snapshot.bBattlePhase = true;
		Snapshot.bCanAttackDirectly = true;
		Snapshot.OwnMonsterIds.Add(1129);
		const FDAAIDecision Decision = AI.ChooseAction(Snapshot);
		TestTrue(TEXT("Battle policy chooses a direct attack"), Decision.Action == EDAAIAction::DirectAttack);
	}

	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDAOpponentCooldownRealignTest, "DuelAcademy.Opponents.CooldownRealign",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FDAOpponentCooldownRealignTest::RunTest(const FString& Parameters)
{
	(void)Parameters;
	UDAOpponentSubsystem* Opponents = MakeOpponentSubsystemForTest();
	if (!TestNotNull(TEXT("Opponent subsystem created"), Opponents))
	{
		return false;
	}

	FString Error;
	if (!TestTrue(TEXT("Roster loads"), Opponents->Reload(Error)))
	{
		AddError(Error);
		return false;
	}
	const FDAOpponentDef* Jaden = Opponents->FindOpponent(TEXT("jaden"));
	if (!TestNotNull(TEXT("Jaden exists"), Jaden))
	{
		return false;
	}

	// P4-09: a backwards day jump (older save or calendar override) must never
	// wedge the duel-request cooldown. Consume on a later day, then jump back.
	Opponents->ResetRuntimeState();
	FString Reason;
	TestTrue(TEXT("Request accepted on day 10"), Opponents->ConsumeDuelRequest(TEXT("jaden"), 10, 0, Reason));

	FDAOpponentRuntimeState FutureState = Opponents->GetRuntimeState();
	FutureState.RequestDay = 12;
	FutureState.LastRequestDay.Add(TEXT("jaden"), 12);
	Opponents->SetRuntimeState(FutureState);

	TestTrue(TEXT("A backwards jump does not block with a stale future cooldown"),
		Opponents->CanRequestDuel(TEXT("jaden"), 5, 0, Reason));
	TestTrue(TEXT("Consume realigns the request-day bookkeeping"),
		Opponents->ConsumeDuelRequest(TEXT("jaden"), 5, 0, Reason));
	const FDAOpponentRuntimeState& Realigned = Opponents->GetRuntimeState();
	TestEqual(TEXT("Request day realigned to the new day"), Realigned.RequestDay, 5);
	TestEqual(TEXT("Stale future cooldown entry cleared"), Realigned.LastRequestDay.FindRef(TEXT("jaden")), 5);
	TestEqual(TEXT("Stale per-day counter was reset, then counted once"),
		Realigned.RequestsToday.FindRef(TEXT("jaden")), 1);

	// Forward cooldowns must keep blocking exactly as before.
	FDAOpponentRuntimeState NormalState;
	NormalState.RequestDay = 10;
	NormalState.LastRequestDay.Add(TEXT("jaden"), 10);
	Opponents->SetRuntimeState(NormalState);
	const int32 CooldownDays = FMath::Max(1, Jaden->DuelRequest.CooldownDays);
	if (CooldownDays >= 2)
	{
		TestFalse(TEXT("Forward cooldown still blocks mid-window"),
			Opponents->CanRequestDuel(TEXT("jaden"), 10 + CooldownDays - 1, 0, Reason));
	}
	TestTrue(TEXT("Forward cooldown expires on schedule"),
		Opponents->CanRequestDuel(TEXT("jaden"), 10 + CooldownDays, 0, Reason));

	// ValidateSaveSection catches last_request_day entries later than the
	// tracked request day (only possible in a corrupted/tampered save; they
	// would otherwise block every request forever).
	TSharedPtr<FJsonObject> BadSection = MakeShared<FJsonObject>();
	BadSection->SetNumberField(TEXT("version"), 1);
	BadSection->SetNumberField(TEXT("request_day"), 5);
	TSharedPtr<FJsonObject> LastDays = MakeShared<FJsonObject>();
	LastDays->SetNumberField(TEXT("jaden"), 12);
	BadSection->SetObjectField(TEXT("last_request_day"), LastDays);
	FString ValidateError;
	TestFalse(TEXT("Future last_request_day entry is rejected"), Opponents->ValidateSaveSection(BadSection, ValidateError));

	TSharedPtr<FJsonObject> GoodSection = MakeShared<FJsonObject>();
	GoodSection->SetNumberField(TEXT("version"), 1);
	GoodSection->SetNumberField(TEXT("request_day"), 12);
	TSharedPtr<FJsonObject> GoodLastDays = MakeShared<FJsonObject>();
	GoodLastDays->SetNumberField(TEXT("jaden"), 12);
	GoodSection->SetObjectField(TEXT("last_request_day"), GoodLastDays);
	TestTrue(TEXT("Consistent request-day bookkeeping validates"), Opponents->ValidateSaveSection(GoodSection, ValidateError));

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS

