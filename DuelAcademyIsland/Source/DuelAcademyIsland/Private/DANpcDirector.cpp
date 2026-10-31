// Duel Academy Island - minimal schedule-driven NPC director implementation.

#include "DANpcDirector.h"

#include "Components/SceneComponent.h"
#include "DANpcSpawnPoint.h"
#include "DAStudentNPC.h"
#include "DuelAcademyIsland.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"

ADANpcDirector::ADANpcDirector()
{
	PrimaryActorTick.bCanEverTick = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	DefaultNpcClass = ADAStudentNPC::StaticClass();
}

void ADANpcDirector::BeginPlay()
{
	Super::BeginPlay();

	if (bAutoRegisterSpawnPoints)
	{
		RefreshSpawnPoints();
	}

	if (bAutoApplyOnBeginPlay)
	{
		ApplySchedule(InitialScheduleId, InitialWeekday, InitialPeriod);
	}
}

void ADANpcDirector::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	SpawnPoints.Reset();
	ActiveNpcs.Reset();
	ExternalNpcs.Reset();
	Super::EndPlay(EndPlayReason);
}

ADANpcDirector* ADANpcDirector::Get(const UObject* WorldContext)
{
	if (!WorldContext)
	{
		return nullptr;
	}
	UWorld* World = WorldContext->GetWorld();
	if (!World)
	{
		return nullptr;
	}
	for (TActorIterator<ADANpcDirector> It(World); It; ++It)
	{
		return *It;
	}
	return nullptr;
}

void ADANpcDirector::RegisterSpawnPoint(ADANpcSpawnPoint* SpawnPoint)
{
	if (!SpawnPoint || SpawnPoint->SpawnPointId.IsEmpty())
	{
		return;
	}

	SpawnPoints.Add(SpawnPoint->SpawnPointId, SpawnPoint);

	if (SpawnPoint->bSpawnOnBeginPlay && !SpawnPoint->IsOccupied())
	{
		SpawnAtPoint(SpawnPoint->SpawnPointId);
	}
}

void ADANpcDirector::UnregisterSpawnPoint(ADANpcSpawnPoint* SpawnPoint)
{
	if (!SpawnPoint)
	{
		return;
	}
	DespawnAtPoint(SpawnPoint->SpawnPointId);
	SpawnPoints.Remove(SpawnPoint->SpawnPointId);
}

int32 ADANpcDirector::RefreshSpawnPoints()
{
	const TMap<FString, TWeakObjectPtr<ADANpcSpawnPoint>> PreviousPoints = SpawnPoints;
	const TMap<FString, TWeakObjectPtr<AActor>> PreviousActive = ActiveNpcs;

	SpawnPoints.Reset();

	TArray<ADANpcSpawnPoint*> Points;
	for (TActorIterator<ADANpcSpawnPoint> It(GetWorld()); It; ++It)
	{
		if (ADANpcSpawnPoint* Point = *It)
		{
			Points.Add(Point);
		}
	}

	for (ADANpcSpawnPoint* Point : Points)
	{
		if (Point && !Point->SpawnPointId.IsEmpty())
		{
			const TWeakObjectPtr<ADANpcSpawnPoint>* Existing = SpawnPoints.Find(Point->SpawnPointId);
			if (Existing && Existing->IsValid())
			{
				UE_LOG(LogDuelAcademyIsland, Warning,
					TEXT("Duplicate NPC spawn point id '%s'; keeping the first registration."), *Point->SpawnPointId);
				continue;
			}
			SpawnPoints.Add(Point->SpawnPointId, Point);
		}
	}

	// Points removed from the level release their NPC before the active map is rebuilt.
	for (const TPair<FString, TWeakObjectPtr<ADANpcSpawnPoint>>& Pair : PreviousPoints)
	{
		if (SpawnPoints.Contains(Pair.Key))
		{
			continue;
		}
		if (ADANpcSpawnPoint* OldPoint = Pair.Value.Get())
		{
			OldPoint->DespawnNpc();
		}
	}

	// Rebuild the active map from the points that survived; any NPC that can no
	// longer be reached through a registered point becomes an orphan and is destroyed.
	ActiveNpcs.Reset();
	TSet<AActor*> KeptNpcs;
	for (const TPair<FString, TWeakObjectPtr<ADANpcSpawnPoint>>& Pair : SpawnPoints)
	{
		ADANpcSpawnPoint* Point = Pair.Value.Get();
		AActor* Npc = Point ? Point->GetSpawnedNpc() : nullptr;
		if (IsValid(Npc))
		{
			ActiveNpcs.Add(Pair.Key, Npc);
			KeptNpcs.Add(Npc);
		}
	}

	for (const TPair<FString, TWeakObjectPtr<AActor>>& Pair : PreviousActive)
	{
		AActor* Npc = Pair.Value.Get();
		if (IsValid(Npc) && !KeptNpcs.Contains(Npc))
		{
			OnNpcDespawned.Broadcast(Pair.Key, Npc);
			Npc->Destroy();
		}
	}

	if (bHasAppliedSchedule)
	{
		// Preserve the current week/event filter; this also despawns stale NPCs
		// that no longer match after a rebuild.
		ApplySchedule(CurrentScheduleId, CurrentWeekday, CurrentPeriod);
	}
	else
	{
		for (ADANpcSpawnPoint* Point : Points)
		{
			if (Point && Point->bSpawnOnBeginPlay && !Point->IsOccupied())
			{
				SpawnAtPoint(Point->SpawnPointId);
			}
		}
	}

	return SpawnPoints.Num();
}

void ADANpcDirector::ApplySchedule(const FString& ScheduleId, const FString& Weekday, const FString& Period)
{
	bHasAppliedSchedule = true;
	CurrentScheduleId = ScheduleId;
	CurrentWeekday = Weekday;
	CurrentPeriod = Period;

	OnScheduleApplied.Broadcast(ScheduleId, Weekday, Period);

	TArray<FString> Ids;
	SpawnPoints.GetKeys(Ids);

	for (const FString& Id : Ids)
	{
		ADANpcSpawnPoint* Point = SpawnPoints.FindRef(Id).Get();
		if (!Point)
		{
			SpawnPoints.Remove(Id);
			ActiveNpcs.Remove(Id);
			continue;
		}

		const bool bShouldBeActive = Point->MatchesSchedule(CurrentScheduleId, CurrentWeekday, CurrentPeriod, ActiveEvent);
		const bool bHasNpc = ActiveNpcs.Contains(Id) && ActiveNpcs.FindRef(Id).IsValid();

		if (bShouldBeActive && !bHasNpc)
		{
			SpawnAtPoint(Id);
		}
		else if (!bShouldBeActive && bHasNpc)
		{
			DespawnAtPoint(Id);
		}
	}
}

void ADANpcDirector::SetActiveEvent(const FString& EventId)
{
	if (ActiveEvent == EventId)
	{
		return;
	}
	ActiveEvent = EventId;

	// Event overrides are evaluated by the spawn point; re-run the current filter.
	ApplySchedule(CurrentScheduleId, CurrentWeekday, CurrentPeriod);
}

AActor* ADANpcDirector::SpawnAtPoint(const FString& SpawnPointId)
{
	if (AActor* Existing = FindNpc(SpawnPointId))
	{
		return Existing;
	}

	ADANpcSpawnPoint* Point = FindSpawnPoint(SpawnPointId);
	if (!Point)
	{
		return nullptr;
	}

	AActor* Npc = Point->SpawnNpc(this);
	if (Npc)
	{
		ActiveNpcs.Add(SpawnPointId, Npc);
		OnNpcSpawned.Broadcast(SpawnPointId, Npc);
	}
	return Npc;
}

void ADANpcDirector::DespawnAtPoint(const FString& SpawnPointId)
{
	ADANpcSpawnPoint* Point = FindSpawnPoint(SpawnPointId);
	AActor* Npc = nullptr;
	if (const TWeakObjectPtr<AActor>* Found = ActiveNpcs.Find(SpawnPointId))
	{
		Npc = Found->Get();
	}
	ActiveNpcs.Remove(SpawnPointId);

	if (Npc)
	{
		OnNpcDespawned.Broadcast(SpawnPointId, Npc);
	}

	if (Point)
	{
		Point->DespawnNpc();
	}
	else if (Npc)
	{
		Npc->Destroy();
	}
}

void ADANpcDirector::RegisterNpc(const FString& NpcId, AActor* Npc)
{
	if (!NpcId.IsEmpty() && Npc)
	{
		ExternalNpcs.Add(NpcId, Npc);
	}
}

void ADANpcDirector::UnregisterNpc(const FString& NpcId)
{
	ExternalNpcs.Remove(NpcId);
}

AActor* ADANpcDirector::FindNpc(const FString& NpcId) const
{
	if (const TWeakObjectPtr<AActor>* Found = ExternalNpcs.Find(NpcId))
	{
		if (AActor* Npc = Found->Get())
		{
			return Npc;
		}
	}
	if (const TWeakObjectPtr<AActor>* Found = ActiveNpcs.Find(NpcId))
	{
		return Found->Get();
	}
	return nullptr;
}

bool ADANpcDirector::TeleportNpcToPoint(const FString& NpcId, const FString& SpawnPointId)
{
	AActor* Npc = FindNpc(NpcId);
	ADANpcSpawnPoint* Point = FindSpawnPoint(SpawnPointId);
	if (!Npc || !Point)
	{
		return false;
	}

	if (ACharacter* Character = Cast<ACharacter>(Npc))
	{
		if (UCharacterMovementComponent* Movement = Character->GetCharacterMovement())
		{
			Movement->StopMovementImmediately();
		}
	}

	Npc->SetActorLocationAndRotation(Point->GetSpawnLocation(), Point->GetSpawnRotation(), false, nullptr,
		ETeleportType::TeleportPhysics);
	return true;
}

bool ADANpcDirector::MoveNpcToLocation(const FString& NpcId, FVector Location, float Yaw)
{
	AActor* Npc = FindNpc(NpcId);
	if (!Npc)
	{
		return false;
	}

	if (ACharacter* Character = Cast<ACharacter>(Npc))
	{
		if (UCharacterMovementComponent* Movement = Character->GetCharacterMovement())
		{
			Movement->StopMovementImmediately();
		}
	}

	Npc->SetActorLocationAndRotation(Location, FRotator(0.f, Yaw, 0.f), false, nullptr,
		ETeleportType::TeleportPhysics);
	return true;
}

ADANpcSpawnPoint* ADANpcDirector::FindSpawnPoint(const FString& SpawnPointId) const
{
	if (const TWeakObjectPtr<ADANpcSpawnPoint>* Found = SpawnPoints.Find(SpawnPointId))
	{
		return Found->Get();
	}
	return nullptr;
}

UClass* ADANpcDirector::GetDefaultNpcClass() const
{
	return DefaultNpcClass.Get();
}
