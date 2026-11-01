// Duel Academy Island - world subsystem: location tracking, discovery, messages,
// water query, and the additive "world" save section (portal locks/used flags,
// discovered location ids and the NPC director schedule/event filter).

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "DATypes.h"
#include "DASaveGame.h"
#include "DAIslandSubsystem.generated.h"

class ADALocationVolume;
class ADAIslandManager;
class ADANpcDirector;
class ADAInteriorPortal;
class USoundBase;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAZoneChangedSignature, ADALocationVolume*, NewZone, bool, bFirstVisit);

/** One portal entry queued by the world save section. */
struct FDAWorldPortalSaveEntry
{
	FString PortalId;
	bool bLocked = false;
	bool bUsed = false;
};

/**
 * World state restored from the additive "world" save section.
 *
 * Portal and discovery state can be applied as soon as the world exists. NPC
 * schedule state is reapplied through ADANpcDirector::RestoreScheduleState,
 * which deterministically spawns/despawns from the registered points; spawned
 * actor identity is deliberately not serialized.
 */
struct FDAWorldSaveState
{
	TArray<FDAWorldPortalSaveEntry> Portals;
	bool bHasDiscoveredState = false;
	TArray<FString> Discovered;
	bool bHasNpcSchedule = false;
	bool bNpcScheduleApplied = false;
	FString ScheduleId;
	FString Weekday;
	FString Period;
	FString ActiveEvent;
};

UCLASS()
class DUELACADEMYISLAND_API UDAIslandSubsystem : public UTickableWorldSubsystem, public IDASavePayloadProvider
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

	// ---------------------------------------------------------------- discovery persistence
	/** Discovered location ids, sorted. Survives save/load through the "world" section. */
	TArray<FString> GetDiscoveredLocationIds() const;

	/** Replace the discovered set (used by the world save provider and tests). */
	void RestoreDiscoveredLocationIds(const TArray<FString>& LocationIds);

	// ---------------------------------------------------------------- world save state
	// IDASavePayloadProvider. The section keeps portal locks/used flags, zone
	// discovery and the NPC director filter. It is additive: old saves have no
	// section and keep their live world state.
	virtual FString GetSaveSectionName() const override;
	virtual bool WriteSaveSection(TSharedPtr<FJsonObject>& OutSection) const override;
	virtual bool ValidateSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError) const override;
	virtual bool ReadSaveSection(const TSharedPtr<FJsonObject>& InSection, FString& OutError) override;

	/**
	 * Apply state queued by ReadSaveSection. Idempotent and safe before all
	 * actors exist: portal/discovery state applies immediately, while an NPC
	 * schedule waits for the director. Returns false only while the director is
	 * missing; the tick retries and eventually drops the schedule.
	 */
	bool ApplyPendingWorldState();

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Save")
	bool HasPendingWorldState() const { return bWorldStatePending; }

private:
	void TryRegisterSaveProvider();
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

	FDAWorldSaveState PendingWorldState;
	bool bWorldStatePending = false;
	float PendingWorldStateSeconds = 0.f;
	bool bSaveProviderRegistered = false;
};
