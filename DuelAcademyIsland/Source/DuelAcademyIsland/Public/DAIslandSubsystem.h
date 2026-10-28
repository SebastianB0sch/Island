// Duel Academy Island - world subsystem: location tracking, discovery, messages, water query.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "DATypes.h"
#include "DAIslandSubsystem.generated.h"

class ADALocationVolume;
class ADAIslandManager;
class USoundBase;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAZoneChangedSignature, ADALocationVolume*, NewZone, bool, bFirstVisit);

UCLASS()
class DUELACADEMYISLAND_API UDAIslandSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;

	static UDAIslandSubsystem* Get(const UObject* WorldContext);

	// ---------------------------------------------------------------- zones
	void RegisterZone(ADALocationVolume* Zone);
	void UnregisterZone(ADALocationVolume* Zone);

	/** All zones sorted by their SortOrder (map / fast travel order). */
	TArray<ADALocationVolume*> GetZones() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	ADALocationVolume* GetCurrentZone() const { return CurrentZone.Get(); }

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	bool IsDiscovered(const ADALocationVolume* Zone) const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	int32 NumDiscovered() const { return Discovered.Num(); }

	/** Time (world seconds) the current zone was entered, and whether it was a first visit. */
	float GetZoneChangeTime() const { return ZoneChangeTime; }
	bool WasFirstVisit() const { return bLastZoneFirstVisit; }

	UPROPERTY(BlueprintAssignable, Category = "Duel Academy")
	FDAZoneChangedSignature OnZoneChanged;

	// ---------------------------------------------------------------- interactables
	/** Actors implementing IDAInteractableInterface (signs, shops, duel fields, NPCs). */
	void RegisterInteractable(AActor* Interactable);
	void UnregisterInteractable(AActor* Interactable);
	const TArray<TWeakObjectPtr<AActor>>& GetInteractables() const { return Interactables; }

	// ---------------------------------------------------------------- messages
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void PushMessage(const FDAMessage& Message);

	/** The message the HUD should display right now (empty title = none). */
	const FDAMessage* GetActiveMessage() const;
	float GetActiveMessageAge() const;
	void DismissMessage();

	// ---------------------------------------------------------------- environment
	ADAIslandManager* GetManager() const;

	/** Water surface height at a location (lake inside the lake ellipse, sea level elsewhere). */
	float GetWaterSurfaceZ(const FVector& WorldLocation) const;

	/** Plays one of the generated UI / ambience sounds (e.g. "A_Discover") as 2D. */
	void PlayUISound(const FName SoundName, float Volume = 1.f) const;

private:
	void UpdateCurrentZone();

	TArray<TWeakObjectPtr<ADALocationVolume>> Zones;
	TArray<TWeakObjectPtr<AActor>> Interactables;
	TWeakObjectPtr<ADALocationVolume> CurrentZone;
	TSet<FString> Discovered;
	float ZoneChangeTime = -100.f;
	bool bLastZoneFirstVisit = false;
	float ZonePollAccumulator = 0.f;

	TArray<FDAMessage> MessageQueue;
	float ActiveMessageStart = 0.f;

	mutable TWeakObjectPtr<ADAIslandManager> CachedManager;
};
