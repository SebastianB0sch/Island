// Duel Academy Island - duel-rules self-test entry points.
//
// -DADuelRulesSelfTest boots the game, waits for the card database, runs the
// rules checks and exits.  da.DuelRulesSelfTest runs the same checks on demand
// from the console.  -DADuelSelfTest=N runs the release-gate duel batch from
// this subsystem because the legacy HUD switch only recognises a bare
// -DADuelSelfTest token.  da.DuelSelfTest remains the console entry point.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DADuelRulesSelfTest.generated.h"

class UCardDatabaseSubsystem;

/**
 * Single owner for the -DADuelSelfTest=N launch argument.  The diagnostics
 * batch and the rules-self-test subsystem both need the same clamped count;
 * keeping the parse here avoids the two drifting apart.
 */
namespace DADuelSelfTestArgs
{
	/**
	 * Iteration count from -DADuelSelfTest=N, clamped to [1, MaxIterations].
	 * DefaultIterations is used when the switch is absent or its value is not
	 * positive.  OutRequested (optional) reports whether the switch was present.
	 */
	DUELACADEMYISLAND_API int32 ParseRequestedIterations(int32 DefaultIterations, int32 MaxIterations,
		bool* OutRequested = nullptr);
}

struct FDuelRulesSelfTestReport
{
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

	FString ToSummary() const
	{
		return FString::Printf(TEXT("Duel rules self-test: %d passed, %d failed.%s"),
			Passed, Failed, Failed == 0 ? TEXT(" ALL PASS") : TEXT(" FAILURES PRESENT"));
	}
};

class DUELACADEMYISLAND_API FDuelRulesSelfTest
{
public:
	/** Runs every rules check and writes PASS/FAIL lines to the log. */
	static FDuelRulesSelfTestReport Run(UCardDatabaseSubsystem* Database);
};

UCLASS()
class DUELACADEMYISLAND_API UDADuelRulesSelfTestSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

private:
	bool Tick(float DeltaTime);

	FTSTicker::FDelegateHandle TickerHandle;
	bool bFinished = false;
	bool bRunDuelGate = false;
	int32 DuelGateIterations = 24;
	float WaitSeconds = 0.f;
};
