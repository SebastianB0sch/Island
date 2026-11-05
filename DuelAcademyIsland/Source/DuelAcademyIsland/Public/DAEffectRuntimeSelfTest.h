// Duel Academy Island - data-driven effect runtime self-test.
//
// -DAEffectRuntimeSelfTest boots the game, loads the ten Tier-1 scripts and
// runs a small duel-state suite.  da.EffectRuntimeSelfTest runs it on demand.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DAEffectRuntimeSelfTest.generated.h"

class UCardDatabaseSubsystem;

struct FDEffectRuntimeSelfTestReport
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
		return FString::Printf(TEXT("Effect runtime self-test: %d passed, %d failed.%s"),
			Passed, Failed, Failed == 0 ? TEXT(" ALL PASS") : TEXT(" FAILURES PRESENT"));
	}
};

class DUELACADEMYISLAND_API FDAEffectRuntimeSelfTest
{
public:
	static FDEffectRuntimeSelfTestReport Run(UCardDatabaseSubsystem* Database);
};

UCLASS()
class DUELACADEMYISLAND_API UDAEffectRuntimeSelfTestSubsystem : public UGameInstanceSubsystem
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
