// Duel Academy Island - A07 puzzle/exam self-test entry points.
//
// Command line:
//   -DAPuzzleSelfTest       run all 100 authored puzzle replays and exit
//   -DAExamSelfTest        run the 12-cycle exam lifecycle and exit
//   -DAPuzzleExamSelfTest  run both suites in one process and exit
//
// Console:
//   da.PuzzleSelfTest, da.ExamSelfTest, da.PuzzleExamSelfTest
//
// The suites use a transient UDAExamSubsystem and never touch UI, save or the
// live game profile.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DAPuzzleSelfTest.generated.h"

class UCardDatabaseSubsystem;

/** Shared PASS/FAIL accumulator for the A07 suites. */
struct FDASelfTestReport
{
	FString Suite;
	int32 Passed = 0;
	int32 Failed = 0;
	TArray<FString> Lines;

	bool AllPassed() const { return Failed == 0; }

	void Check(bool bCondition, const FString& Name)
	{
		if (bCondition)
		{
			++Passed;
			Lines.Add(FString::Printf(TEXT("PASS: %s"), *Name));
		}
		else
		{
			++Failed;
			Lines.Add(FString::Printf(TEXT("FAIL: %s"), *Name));
		}
	}

	void Info(const FString& Message)
	{
		Lines.Add(FString::Printf(TEXT("INFO: %s"), *Message));
	}

	FString ToSummary() const
	{
		return FString::Printf(TEXT("%s: %d passed, %d failed.%s"),
			*Suite, Passed, Failed, Failed == 0 ? TEXT(" ALL PASS") : TEXT(" FAILURES PRESENT"));
	}
};

class DUELACADEMYISLAND_API FDAPuzzleSelfTest
{
public:
	/** Loads all 100 puzzles, replays every authored line and returns per-puzzle lines. */
	static FDASelfTestReport Run(UCardDatabaseSubsystem* Database);
};

UCLASS()
class DUELACADEMYISLAND_API UDAPuzzleExamSelfTestSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

private:
	bool Tick(float DeltaTime);

	FTSTicker::FDelegateHandle TickerHandle;
	bool bRunPuzzles = false;
	bool bRunExams = false;
	bool bFinished = false;
	float WaitSeconds = 0.f;
};
