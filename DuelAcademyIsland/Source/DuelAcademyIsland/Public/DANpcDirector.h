// Duel Academy Island - minimal schedule-driven NPC director.
//
// The director is an actor (not a ticking subsystem): it holds registered spawn
// points, applies a schedule id/weekday/period filter, spawns missing NPCs and
// despawns NPCs whose point is no longer active. It never ticks; work happens
// only when a schedule is applied or an event starts/ends.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Templates/SubclassOf.h"
#include "DAStudentNPC.h"
#include "DANpcDirector.generated.h"

class USceneComponent;
class ADANpcSpawnPoint;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FDAScheduleAppliedSignature, FString, ScheduleId, FString, Weekday, FString, Period);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDADirectorNpcSignature, FString, NpcId, AActor*, Npc);

/**
 * Minimal NPC schedule director.
 *
 * Usage from A03/A02:
 *   Director->ApplySchedule(TEXT("banner_office"), TEXT("Monday"), TEXT("AM"));
 *   Director->SetActiveEvent(TEXT("E14"));
 *
 * Spawn points are registered automatically from the level when
 * bAutoRegisterSpawnPoints is true, or explicitly by the editor build script.
 */
UCLASS(Blueprintable)
class DUELACADEMYISLAND_API ADANpcDirector : public AActor
{
	GENERATED_BODY()

public:
	ADANpcDirector();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	static ADANpcDirector* Get(const UObject* WorldContext);

	/** Class used by spawn points that do not override NpcClass. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Director")
	TSubclassOf<ADAStudentNPC> DefaultNpcClass;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Director")
	bool bAutoRegisterSpawnPoints = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Director")
	bool bAutoApplyOnBeginPlay = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Director")
	FString InitialScheduleId = TEXT("default");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Director")
	FString InitialWeekday = TEXT("Monday");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Director")
	FString InitialPeriod = TEXT("AM");

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Director")
	FDAScheduleAppliedSignature OnScheduleApplied;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Director")
	FDADirectorNpcSignature OnNpcSpawned;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Director")
	FDADirectorNpcSignature OnNpcDespawned;

	// ---------------------------------------------------------------- registration
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Director")
	void RegisterSpawnPoint(ADANpcSpawnPoint* SpawnPoint);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Director")
	void UnregisterSpawnPoint(ADANpcSpawnPoint* SpawnPoint);

	/** Scan the level for ADANpcSpawnPoint actors. Returns the number registered. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Director")
	int32 RefreshSpawnPoints();

	// ---------------------------------------------------------------- schedule
	/**
	 * Resolve every registered spawn point against the filter and spawn/despawn
	 * as needed. Empty values are wildcards.
	 */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Director")
	void ApplySchedule(const FString& ScheduleId, const FString& Weekday, const FString& Period);

	/** Event overrides: empty means no event. Re-applies the current schedule. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Director")
	void SetActiveEvent(const FString& EventId);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Director")
	FString GetActiveEvent() const { return ActiveEvent; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Director")
	FString GetCurrentScheduleId() const { return CurrentScheduleId; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Director")
	FString GetCurrentWeekday() const { return CurrentWeekday; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Director")
	FString GetCurrentPeriod() const { return CurrentPeriod; }

	// ---------------------------------------------------------------- NPC control
	/** Spawn (or return) the NPC assigned to a spawn point id. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Director")
	AActor* SpawnAtPoint(const FString& SpawnPointId);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Director")
	void DespawnAtPoint(const FString& SpawnPointId);

	/** Register an NPC placed by another system so it can be moved by schedule. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Director")
	void RegisterNpc(const FString& NpcId, AActor* Npc);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Director")
	void UnregisterNpc(const FString& NpcId);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Director")
	AActor* FindNpc(const FString& NpcId) const;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Director")
	bool TeleportNpcToPoint(const FString& NpcId, const FString& SpawnPointId);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Director")
	bool MoveNpcToLocation(const FString& NpcId, FVector Location, float Yaw);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Director")
	ADANpcSpawnPoint* FindSpawnPoint(const FString& SpawnPointId) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Director")
	int32 GetRegisteredSpawnPointCount() const { return SpawnPoints.Num(); }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Director")
	UClass* GetDefaultNpcClass() const;

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Director")
	TObjectPtr<USceneComponent> Root;

private:
	TMap<FString, TWeakObjectPtr<ADANpcSpawnPoint>> SpawnPoints;
	TMap<FString, TWeakObjectPtr<AActor>> ActiveNpcs;
	TMap<FString, TWeakObjectPtr<AActor>> ExternalNpcs;

	FString CurrentScheduleId;
	FString CurrentWeekday;
	FString CurrentPeriod;
	FString ActiveEvent;
};
