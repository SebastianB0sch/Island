// Duel Academy Island - duel-rules self-test entry points.
//
// -DADuelRulesSelfTest boots the game, waits for the card database, runs the
// rules checks and exits.  da.DuelRulesSelfTest runs the same checks on demand
// from the console.  The legacy -DADuelSelfTest / da.DuelSelfTest harness is
// untouched.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DADuelRulesSelfTest.generated.h"

class UCardDatabaseSubsystem;

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
	float WaitSeconds = 0.f;
};
