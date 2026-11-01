// Duel Academy Island - minimal schedule-driven NPC director implementation.

#include "DANpcDirector.h"

#include "Components/SceneComponent.h"
#include "DAIslandSubsystem.h"
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

	// Keep the first registration of an id. Overwriting it would orphan the NPC
	// that the previous point already spawned (and made deterministic ordering
	// depend on the caller).
	if (const TWeakObjectPtr<ADANpcSpawnPoint>* Existing = SpawnPoints.Find(SpawnPoint->SpawnPointId))
	{
		if (Existing->IsValid() && Existing->Get() != SpawnPoint)
		{
			UE_LOG(LogDuelAcademyIsland, Warning,
				TEXT("Duplicate NPC spawn point id '%s'; keeping the first registration."), *SpawnPoint->SpawnPointId);
			return;
		}
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
	// Only the registered owner of an id may remove it; a rejected duplicate
	// must not despawn the surviving point's NPC.
	const TWeakObjectPtr<ADANpcSpawnPoint>* Registered = SpawnPoints.Find(SpawnPoint->SpawnPointId);
	if (!Registered || Registered->Get() != SpawnPoint)
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
	// Keep duplicate-id resolution independent of actor iteration order.
	Points.Sort([](const ADANpcSpawnPoint& A, const ADANpcSpawnPoint& B)
	{
		if (A.SpawnPointId != B.SpawnPointId)
		{
			return A.SpawnPointId < B.SpawnPointId;
		}
		return A.GetName() < B.GetName();
	});

	for (ADANpcSpawnPoint* Point : Points)
	{
		if (Point && !Point->SpawnPointId.IsEmpty())
		{
			const TWeakObjectPtr<ADANpcSpawnPoint>* Existing = SpawnPoints.Find(Point->SpawnPointId);
			if (Existing && Existing->IsValid() && Existing->Get() != Point)
			{
				UE_LOG(LogDuelAcademyIsland, Warning,
					TEXT("Duplicate NPC spawn point id '%s'; keeping the first registration."), *Point->SpawnPointId);
				// Release anything the losing point still holds so it cannot
				// survive as an unregistered orphan.
				Point->DespawnNpc();
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

	if (UWorld* World = GetWorld())
	{
		if (UDAIslandSubsystem* Island = World->GetSubsystem<UDAIslandSubsystem>())
		{
			Island->NotifyScheduleApplied(CurrentWeekday, CurrentPeriod);
		}
	}

	OnScheduleApplied.Broadcast(ScheduleId, Weekday, Period);

	TArray<FString> Ids;
	SpawnPoints.GetKeys(Ids);
	// TMap key order is not a spawn contract: sort so the same schedule always
	// spawns NPCs in the same order (navigation and save diffs stay stable).
	Ids.Sort();

	for (const FString& Id : Ids)
	{
		ADANpcSpawnPoint* Point = SpawnPoints.FindRef(Id).Get();
		if (!Point)
		{
			// The spawn point was destroyed at runtime. Its NPC is not reachable
			// through a registered point any more, so destroy it instead of
			// leaving an owner-only orphan behind.
			AActor* Orphan = ActiveNpcs.FindRef(Id).Get();
			SpawnPoints.Remove(Id);
			ActiveNpcs.Remove(Id);
			if (IsValid(Orphan))
			{
				OnNpcDespawned.Broadcast(Id, Orphan);
				Orphan->Destroy();
			}
			continue;
		}

		const bool bShouldBeActive = Point->MatchesSchedule(CurrentScheduleId, CurrentWeekday, CurrentPeriod, ActiveEvent);
		AActor* PointNpc = Point->GetSpawnedNpc();
		const bool bHasNpc = IsValid(PointNpc);

		if (bShouldBeActive && !bHasNpc)
		{
			SpawnAtPoint(Id);
		}
		else if (!bShouldBeActive && bHasNpc)
		{
			DespawnAtPoint(Id);
		}
		else if (bShouldBeActive && bHasNpc)
		{
			// Points can be occupied by an NPC spawned outside this map (or the
			// active map can be stale after a level reload); re-adopt it.
			// W6: adopting must not orphan the actor the map currently holds.
			// If it is a different, still-valid NPC from this point's
			// occupant, despawn it the way DespawnAtPoint resolves a mismatch.
			AActor* Previous = ActiveNpcs.FindRef(Id).Get();
			if (IsValid(Previous) && Previous != PointNpc)
			{
				OnNpcDespawned.Broadcast(Id, Previous);
				Previous->Destroy();
			}
			ActiveNpcs.Add(Id, PointNpc);
		}
	}
}

void ADANpcDirector::RestoreScheduleState(bool bInApplied, const FString& InScheduleId,
	const FString& InWeekday, const FString& InPeriod, const FString& InEvent)
{
	// Set the event before the filter so ApplySchedule evaluates the restored
	// event exactly once (calling SetActiveEvent first would re-run the old
	// filter, then the restored one).
	ActiveEvent = InEvent;

	if (!bInApplied)
	{
		const bool bHadSchedule = bHasAppliedSchedule;
		bHasAppliedSchedule = false;
		CurrentScheduleId.Reset();
		CurrentWeekday.Reset();
		CurrentPeriod.Reset();

		if (!bHadSchedule)
		{
			return;
		}

		// The save predates the first schedule application: restore the
		// begin-play baseline instead of leaving the previous session's cast
		// spawned by the schedule that was just cleared.
		TArray<FString> Ids;
		SpawnPoints.GetKeys(Ids);
		Ids.Sort();
		for (const FString& Id : Ids)
		{
			ADANpcSpawnPoint* Point = SpawnPoints.FindRef(Id).Get();
			if (Point && !Point->bSpawnOnBeginPlay && Point->IsOccupied())
			{
				DespawnAtPoint(Id);
			}
		}
		for (const FString& Id : Ids)
		{
			ADANpcSpawnPoint* Point = SpawnPoints.FindRef(Id).Get();
			if (Point && Point->bSpawnOnBeginPlay && !Point->IsOccupied())
			{
				SpawnAtPoint(Id);
			}
		}
		return;
	}

	ApplySchedule(InScheduleId, InWeekday, InPeriod);
}

void ADANpcDirector::SetActiveEvent(const FString& EventId)
{
	if (ActiveEvent == EventId)
	{
		return;
	}
	ActiveEvent = EventId;

	// Before the first ApplySchedule the filter is empty (wildcard). Re-applying
	// it here would spawn every point, so only record the event until the
	// schedule owner applies a real period.
	if (!bHasAppliedSchedule)
	{
		return;
	}

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

	// Adopt an NPC that the point already holds (external spawn or a reloaded
	// active map) instead of broadcasting a second spawn for it.
	if (AActor* Occupant = Point->GetSpawnedNpc(); IsValid(Occupant))
	{
		ActiveNpcs.Add(SpawnPointId, Occupant);
		return Occupant;
	}

	AActor* Npc = Point->SpawnNpc(this);
	// A spawn listener may already have destroyed the NPC; do not publish a
	// dead actor into the active map or the director delegate.
	if (IsValid(Npc))
	{
		ActiveNpcs.Add(SpawnPointId, Npc);
		OnNpcSpawned.Broadcast(SpawnPointId, Npc);
		return IsValid(Npc) ? Npc : nullptr;
	}
	return nullptr;
}

void ADANpcDirector::DespawnAtPoint(const FString& SpawnPointId)
{
	ADANpcSpawnPoint* Point = FindSpawnPoint(SpawnPointId);
	AActor* Npc = nullptr;
	if (const TWeakObjectPtr<AActor>* Found = ActiveNpcs.Find(SpawnPointId))
	{
		Npc = Found->Get();
	}
	AActor* PointNpc = Point ? Point->GetSpawnedNpc() : nullptr;
	ActiveNpcs.Remove(SpawnPointId);

	if (Npc)
	{
		OnNpcDespawned.Broadcast(SpawnPointId, Npc);
	}

	if (Point)
	{
		Point->DespawnNpc();
	}
	// If the active map and the point disagree (external spawn / reload), make
	// sure the bookkeeping NPC does not survive as an orphan.
	if (IsValid(Npc) && Npc != PointNpc)
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

	// W7: the destination ends occupied by the teleported NPC. Release its
	// previous occupant first (missing bookkeeping here let a later
	// ApplySchedule spawn a second NPC at that point). Never route through
	// DespawnAtPoint when the point already holds the teleported NPC itself;
	// it would destroy the actor being moved.
	AActor* PointOccupant = Point->GetSpawnedNpc();
	AActor* MappedOccupant = ActiveNpcs.FindRef(SpawnPointId).Get();
	const bool bDestOccupiedByOther = (IsValid(PointOccupant) && PointOccupant != Npc)
		|| (!IsValid(PointOccupant) && IsValid(MappedOccupant) && MappedOccupant != Npc);
	if (bDestOccupiedByOther)
	{
		DespawnAtPoint(SpawnPointId);
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
	// Wandering is anchored at BeginPlay's location; move the anchor with the
	// NPC or it will stroll back to the old spot.
	if (ADAStudentNPC* Student = Cast<ADAStudentNPC>(Npc))
	{
		Student->SetWanderHome(Npc->GetActorLocation());
	}

	// Release the departure point's claim so the NPC cannot stay double-booked
	// (an ApplySchedule at the old point would otherwise re-adopt it there).
	for (TPair<FString, TWeakObjectPtr<ADANpcSpawnPoint>>& Pair : SpawnPoints)
	{
		if (ADANpcSpawnPoint* OldPoint = Pair.Value.Get(); OldPoint && OldPoint != Point && OldPoint->GetSpawnedNpc() == Npc)
		{
			OldPoint->SetSpawnedNpc(nullptr);
		}
	}
	for (TMap<FString, TWeakObjectPtr<AActor>>::TIterator It = ActiveNpcs.CreateIterator(); It; ++It)
	{
		if (It.Value().Get() == Npc && It.Key() != SpawnPointId)
		{
			It.RemoveCurrent();
		}
	}

	// Record the destination per SpawnAtPoint semantics (point id -> NPC) so
	// the schedule keeps a single, deterministic occupant.
	ActiveNpcs.Add(SpawnPointId, Npc);
	Point->SetSpawnedNpc(Npc);
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
	if (ADAStudentNPC* Student = Cast<ADAStudentNPC>(Npc))
	{
		Student->SetWanderHome(Location);
	}
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
