// Duel Academy Island - schedule-driven NPC spawn point.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DATypes.h"
#include "DAStudentNPC.h"
#include "DANpcSpawnPoint.generated.h"

class USceneComponent;
class UBillboardComponent;
class UTextRenderComponent;
class ADANpcSpawnPoint;
class ADANpcDirector;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDANpcSpawnedSignature, ADANpcSpawnPoint*, SpawnPoint, AActor*, Npc);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDANpcDespawnedSignature, ADANpcSpawnPoint*, SpawnPoint, AActor*, Npc);

/**
 * A mark where a scheduled NPC can stand.
 *
 * ScheduleTags are deliberately free-form. The director queries with a
 * (schedule id, weekday, period) triple and a spawn point matches if any tag
 * equals any query value. This keeps the stub A03 schedule data readable while
 * the final schedule schema is still being frozen.
 */
UCLASS(Blueprintable)
class DUELACADEMYISLAND_API ADANpcSpawnPoint : public AActor
{
	GENERATED_BODY()

public:
	ADANpcSpawnPoint();

	virtual void OnConstruction(const FTransform& Transform) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	FString SpawnPointId = TEXT("spawn");

	/** Optional canonical schedule row id ("banner_office", "class_teacher", ...). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	FString ScheduleId;

	/** Free-form tags: "breakfast", "Monday", "AM", "weekday", "cafeteria". */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	TArray<FString> ScheduleTags;

	/** Story/roster role ("student", "teacher", "headmaster", "shopkeeper", "chancellor", ...). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	FString SpawnRole = TEXT("student");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	EDADorm Dorm = EDADorm::Slifer;

	/** Wander radius in cm. 0 = stand still. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	float WanderRadius = 500.f;

	/** Only active while this event id is the director's active event. Empty = always. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	FString EventOverride;

	/** If true and EventOverride is empty, only active while an event is running. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	bool bEventOnly = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	bool bEnabled = true;

	/** If true, the director spawns this point as soon as it registers. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	bool bSpawnOnBeginPlay = false;

	/** Optional per-point class override. Empty = director's DefaultNpcClass. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	TSubclassOf<ADAStudentNPC> NpcClass;

	/** NPC capsule half-height offset (cm); anchors store floor level. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	float SpawnZOffset = 90.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Spawn")
	FString DisplayName;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Spawn")
	FDANpcSpawnedSignature OnNpcSpawned;

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Spawn")
	FDANpcDespawnedSignature OnNpcDespawned;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Spawn")
	bool MatchesSchedule(const FString& InScheduleId, const FString& InWeekday, const FString& InPeriod,
		const FString& InActiveEvent) const;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Spawn")
	AActor* SpawnNpc(ADANpcDirector* Director);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Spawn")
	void DespawnNpc();

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Spawn")
	AActor* GetSpawnedNpc() const { return SpawnedNpc.Get(); }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Spawn")
	bool IsOccupied() const { return SpawnedNpc.IsValid(); }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Spawn")
	FVector GetSpawnLocation() const { return GetActorLocation() + FVector(0.f, 0.f, SpawnZOffset); }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Spawn")
	FRotator GetSpawnRotation() const { return GetActorRotation(); }

	/** Used by the director when the spawn is applied or released. */
	void SetSpawnedNpc(AActor* Npc) { SpawnedNpc = Npc; }

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Duel Academy|Spawn")
	void OnNpcSpawnedNative(AActor* Npc);
	virtual void OnNpcSpawnedNative_Implementation(AActor* Npc);

	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Duel Academy|Spawn")
	void OnNpcDespawnedNative(AActor* Npc);
	virtual void OnNpcDespawnedNative_Implementation(AActor* Npc);

#if WITH_EDITORONLY_DATA
	/** Refresh the editor-only label after changing SpawnPointId/SpawnRole from code. */
	void RefreshEditorLabel();
#endif

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Spawn")
	TObjectPtr<USceneComponent> Root;

#if WITH_EDITORONLY_DATA
	UPROPERTY(VisibleAnywhere, Category = "Duel Academy|Spawn")
	TObjectPtr<UBillboardComponent> EditorIcon;

	UPROPERTY(VisibleAnywhere, Category = "Duel Academy|Spawn")
	TObjectPtr<UTextRenderComponent> EditorLabel;
#endif

private:
	TWeakObjectPtr<AActor> SpawnedNpc;
};
