// Duel Academy Island - PIE portal entry/exit self-test.
//
// -DAPortalTest boots the game, verifies the 20 generated portals are paired,
// teleports the player through all ten interior entrances and back out through
// one return portal, captures DAPortalInterior.png, then exits.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DAPortalTest.generated.h"

class ADAInteriorPortal;
class APawn;

UCLASS()
class DUELACADEMYISLAND_API UDAPortalTestSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

private:
	bool Tick(float DeltaTime);
	void CollectPortals(UWorld* World);
	void BeginEntry();
	void VerifyEntry();
	void BeginReturn();
	void VerifyReturn();
	void Finish();

	void Check(bool bCondition, const FString& Name);
	FVector ExpectedArrival(const ADAInteriorPortal* Portal) const;

	FTSTicker::FDelegateHandle TickerHandle;
	bool bFinished = false;
	bool bCollected = false;
	bool bScreenshotTaken = false;
	float WaitSeconds = 0.f;
	float StageSeconds = 0.f;
	int32 Stage = 0;
	int32 EntryIndex = 0;
	int32 Passed = 0;
	int32 Failed = 0;

	TArray<TObjectPtr<ADAInteriorPortal>> Portals;
	TArray<TObjectPtr<ADAInteriorPortal>> Entries;
	TArray<TObjectPtr<ADAInteriorPortal>> Returns;
	TWeakObjectPtr<APawn> PlayerPawn;
	FVector Expected = FVector::ZeroVector;
	FString CurrentPair;
};
