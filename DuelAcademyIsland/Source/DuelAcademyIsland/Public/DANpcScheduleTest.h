// Duel Academy Island - headless NPC schedule/event/spawn self-test.
//
// -DANpcScheduleTest boots the game, validates the 28 generated spawn points
// against Content/Data/World/spawns.json, applies a full Monday-Sunday AM/PM
// schedule week, exercises event overrides and refresh/spawn cycles, logs every
// check, then exits.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DANpcScheduleTest.generated.h"

class ADANpcDirector;
class ADANpcSpawnPoint;

/** One row of Content/Data/World/spawns.json, kept for expected-set checks. */
struct FDANpcSchedulePointData
{
	FString Id;
	FString ScheduleId;
	TArray<FString> ScheduleTags;
	FString EventOverride;
	bool bEnabled = true;
	bool bEventOnly = false;
	bool bSpawnOnBeginPlay = false;
};

UCLASS()
class DUELACADEMYISLAND_API UDANpcScheduleTestSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

private:
	bool Tick(float DeltaTime);
	bool LoadSpawnData();
	void CollectWorld();
	void VerifyRegistration();
	void RunScheduleCases();
	void RunEventCases();
	void RunSpawnDespawnCases();
	void RunRefreshCases();
	void VerifyActiveSet(const FString& CaseName, const FString& ScheduleId, const FString& Weekday,
		const FString& Period, const FString& Event);
	bool ExpectedActive(const FDANpcSchedulePointData& Point, const FString& ScheduleId, const FString& Weekday,
		const FString& Period, const FString& Event) const;
	int32 CountDirectorNpcs() const;
	ADANpcSpawnPoint* FindPoint(const FString& SpawnPointId) const;
	void Check(bool bCondition, const FString& Name);
	void Finish();

	FTSTicker::FDelegateHandle TickerHandle;
	bool bFinished = false;
	bool bDataLoaded = false;
	bool bWorldCollected = false;
	float WaitSeconds = 0.f;

	int32 Passed = 0;
	int32 Failed = 0;

	TWeakObjectPtr<ADANpcDirector> Director;
	TArray<TObjectPtr<ADANpcSpawnPoint>> SpawnPoints;
	TMap<FString, TObjectPtr<ADANpcSpawnPoint>> SpawnPointsById;
	TArray<FDANpcSchedulePointData> SpawnData;
	TArray<FString> RequiredSpawnIds;
};
