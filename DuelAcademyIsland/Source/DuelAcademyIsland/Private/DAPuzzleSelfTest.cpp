// Duel Academy Island - in-engine 100-puzzle self-test.

#include "DAPuzzleSelfTest.h"

#include "DACardRecords.h"
#include "DADuelEngine.h"
#include "DAExamSelfTest.h"
#include "DAPuzzleRuntime.h"
#include "DuelAcademyIsland.h"

#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "Misc/Parse.h"

namespace
{
	FString DetailOr(const FString& Error, const FString& Fallback)
	{
		return Error.IsEmpty() ? Fallback : Error;
	}

	bool ProbeTimeout(UCardDatabaseSubsystem* Database, const FDAPuzzleDefinition& Puzzle, FString& OutError)
	{
		FDuelScenario Scenario;
		if (!FDAPuzzleRuntime::BuildScenario(Puzzle, Scenario, OutError))
		{
			return false;
		}
		FDuelEngine Duel(Database, Puzzle.Seed);
		if (!Duel.StartScenario(Scenario, OutError))
		{
			OutError = FString::Printf(TEXT("timer probe could not start: %s"), *OutError);
			return false;
		}
		const float BeforeLimit = FMath::Max(0.f, static_cast<float>(Puzzle.TimeLimitSeconds) - 0.5f);
		if (Duel.CheckScenarioTimeout(BeforeLimit) || Duel.IsOver())
		{
			OutError = TEXT("timer fired before the authored time limit.");
			return false;
		}
		const float PastLimit = static_cast<float>(Puzzle.TimeLimitSeconds) + 0.01f;
		if (!Duel.CheckScenarioTimeout(PastLimit))
		{
			OutError = TEXT("timer did not fire after the authored time limit.");
			return false;
		}
		if (!Duel.IsOver() || Duel.GetWinner() != EDuelOwner::Opponent)
		{
			OutError = TEXT("timer expiry did not end the duel as an opponent win.");
			return false;
		}
		return true;
	}

	void LogReport(const FDASelfTestReport& Report)
	{
		for (const FString& Line : Report.Lines)
		{
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Line);
		}
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("%s"), *Report.ToSummary());
	}
}

FDASelfTestReport FDAPuzzleSelfTest::Run(UCardDatabaseSubsystem* Database)
{
	FDASelfTestReport Report;
	Report.Suite = TEXT("PuzzleSelfTest");
	if (!Database)
	{
		Report.Check(false, TEXT("card database is available"));
		return Report;
	}

	const FString PuzzleDirectory = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Puzzles"));
	TArray<FDAPuzzleDefinition> Puzzles;
	FString LoadError;
	if (!FDAPuzzleRuntime::LoadPuzzleDirectory(PuzzleDirectory, Puzzles, LoadError))
	{
		Report.Check(false, FString::Printf(TEXT("puzzle directory loads: %s"), *DetailOr(LoadError, TEXT("unknown error"))));
		return Report;
	}

	Report.Check(Puzzles.Num() == 100, FString::Printf(TEXT("100 puzzle files load (found %d)"), Puzzles.Num()));
	TSet<FString> SeenIds;
	int32 Wins = 0;
	for (const FDAPuzzleDefinition& Puzzle : Puzzles)
	{
		FString Error;
		bool bPass = true;
		FString Failure;

		auto Fail = [&bPass, &Failure](const FString& Message)
		{
			if (bPass)
			{
				bPass = false;
				Failure = Message;
			}
		};

		if (Puzzle.Id.IsEmpty() || SeenIds.Contains(Puzzle.Id))
		{
			Fail(TEXT("duplicate or empty puzzle id"));
		}
		SeenIds.Add(Puzzle.Id);
		if (Puzzle.Objective != TEXT("win_this_turn"))
		{
			Fail(FString::Printf(TEXT("unsupported objective '%s'"), *Puzzle.Objective));
		}
		if (Puzzle.TurnLimit != 1)
		{
			Fail(FString::Printf(TEXT("expected a one-turn puzzle, found turn_limit %d"), Puzzle.TurnLimit));
		}
		if (Puzzle.TimeLimitSeconds < 10)
		{
			Fail(FString::Printf(TEXT("time_limit %d is below 10 seconds"), Puzzle.TimeLimitSeconds));
		}
		if (Puzzle.Seed <= 0)
		{
			Fail(FString::Printf(TEXT("seed %d is not positive"), Puzzle.Seed));
		}
		if (Puzzle.RewardDp <= 0)
		{
			Fail(FString::Printf(TEXT("reward DP %d is not positive"), Puzzle.RewardDp));
		}
		if (!Puzzle.bEngineReady)
		{
			Fail(TEXT("engine_ready is false"));
		}
		if (Puzzle.Solution.Num() == 0)
		{
			Fail(TEXT("solution is empty"));
		}

		if (bPass)
		{
			if (!ProbeTimeout(Database, Puzzle, Error))
			{
				Fail(DetailOr(Error, TEXT("timer probe failed")));
			}
		}

		FDAPuzzleReplayResult Replay;
		if (bPass)
		{
			if (!FDAPuzzleRuntime::Replay(Database, Puzzle, Replay, Error))
			{
				Fail(DetailOr(Error, TEXT("replay failed")));
			}
			else if (!Replay.bWon || Replay.OpponentLp > 0 || Replay.PlayerLp <= 0)
			{
				Fail(FString::Printf(TEXT("replay did not end in a player win (player %d LP, opponent %d LP)"),
					Replay.PlayerLp, Replay.OpponentLp));
			}
			else if (Replay.StepsExecuted != Puzzle.Solution.Num())
			{
				Fail(FString::Printf(TEXT("executed %d of %d authored steps"),
					Replay.StepsExecuted, Puzzle.Solution.Num()));
			}
			else if (Replay.PlayerTurns > Puzzle.TurnLimit)
			{
				Fail(FString::Printf(TEXT("used %d player turns (limit %d)"),
					Replay.PlayerTurns, Puzzle.TurnLimit));
			}
		}

		if (bPass)
		{
			++Wins;
			Report.Check(true, FString::Printf(TEXT("%s %s: win in %d step(s), %dms budget"),
				*Puzzle.Id, *Puzzle.Title, Replay.StepsExecuted, Puzzle.TimeLimitSeconds));
		}
		else
		{
			Report.Check(false, FString::Printf(TEXT("%s %s: %s"), *Puzzle.Id, *Puzzle.Title, *Failure));
		}
	}

	Report.Info(FString::Printf(TEXT("%d/%d authored puzzles won in the engine"), Wins, Puzzles.Num()));
	Report.Check(SeenIds.Num() == 100, FString::Printf(TEXT("P001-P100 puzzle ids are unique (found %d)"), SeenIds.Num()));
	return Report;
}

void UDAPuzzleExamSelfTestSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	const TCHAR* CommandLine = FCommandLine::Get();
	bRunPuzzles = FParse::Param(CommandLine, TEXT("DAPuzzleSelfTest"))
		|| FParse::Param(CommandLine, TEXT("DAPuzzleExamSelfTest"));
	bRunExams = FParse::Param(CommandLine, TEXT("DAExamSelfTest"))
		|| FParse::Param(CommandLine, TEXT("DAPuzzleExamSelfTest"));
	if (bRunPuzzles || bRunExams)
	{
		TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateUObject(this, &UDAPuzzleExamSelfTestSubsystem::Tick), 2.0f);
	}
}

void UDAPuzzleExamSelfTestSubsystem::Deinitialize()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}
	Super::Deinitialize();
}

bool UDAPuzzleExamSelfTestSubsystem::Tick(float DeltaTime)
{
	if (bFinished)
	{
		return false;
	}
	WaitSeconds += DeltaTime;
	if (WaitSeconds > 30.f)
	{
		UE_LOG(LogDuelAcademyIsland, Error, TEXT("A07 self-test: timed out waiting for the world/card database."));
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

	bool bAllPassed = true;
	if (bRunPuzzles)
	{
		const FDASelfTestReport Report = FDAPuzzleSelfTest::Run(Database);
		LogReport(Report);
		bAllPassed = bAllPassed && Report.AllPassed();
	}
	if (bRunExams)
	{
		const FDASelfTestReport Report = FDAExamSelfTest::Run(Database);
		LogReport(Report);
		bAllPassed = bAllPassed && Report.AllPassed();
	}
	if (bRunPuzzles && bRunExams)
	{
		UE_LOG(LogDuelAcademyIsland, Log, TEXT("A07SelfTest: %s"),
			bAllPassed ? TEXT("BOTH SUITES PASS") : TEXT("FAILURES PRESENT"));
	}

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
	void RunConsoleSuites(UWorld* World, bool bPuzzles, bool bExams)
	{
		UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
		UCardDatabaseSubsystem* Database = GameInstance ? GameInstance->GetSubsystem<UCardDatabaseSubsystem>() : nullptr;
		if (!Database || !Database->IsLoaded())
		{
			UE_LOG(LogDuelAcademyIsland, Warning, TEXT("A07 self-test: card database is not loaded."));
			return;
		}
		bool bAllPassed = true;
		if (bPuzzles)
		{
			const FDASelfTestReport Report = FDAPuzzleSelfTest::Run(Database);
			LogReport(Report);
			bAllPassed = bAllPassed && Report.AllPassed();
		}
		if (bExams)
		{
			const FDASelfTestReport Report = FDAExamSelfTest::Run(Database);
			LogReport(Report);
			bAllPassed = bAllPassed && Report.AllPassed();
		}
		if (bPuzzles && bExams)
		{
			UE_LOG(LogDuelAcademyIsland, Log, TEXT("A07SelfTest: %s"),
				bAllPassed ? TEXT("BOTH SUITES PASS") : TEXT("FAILURES PRESENT"));
		}
	}

	FAutoConsoleCommandWithWorldAndArgs GDAPuzzleSelfTestCommand(
		TEXT("da.PuzzleSelfTest"),
		TEXT("Replay all 100 authored puzzles through the duel engine and log PASS/FAIL."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			(void)Args;
			RunConsoleSuites(World, true, false);
		}));

	FAutoConsoleCommandWithWorldAndArgs GDAExamSelfTestCommand(
		TEXT("da.ExamSelfTest"),
		TEXT("Run all 12 exam cycles through UDAExamSubsystem and log PASS/FAIL."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			(void)Args;
			RunConsoleSuites(World, false, true);
		}));

	FAutoConsoleCommandWithWorldAndArgs GDAPuzzleExamSelfTestCommand(
		TEXT("da.PuzzleExamSelfTest"),
		TEXT("Run the puzzle and exam A07 self-tests in one process."),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			(void)Args;
			RunConsoleSuites(World, true, true);
		}));
}
