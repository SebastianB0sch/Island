// Duel Academy Island - world subsystem.

#include "DAIslandSubsystem.h"

#include "DAIslandManager.h"
#include "DALocationVolume.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"

void UDAIslandSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
}

void UDAIslandSubsystem::Deinitialize()
{
	Zones.Reset();
	Interactables.Reset();
	MessageQueue.Reset();
	Super::Deinitialize();
}

TStatId UDAIslandSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UDAIslandSubsystem, STATGROUP_Tickables);
}

UDAIslandSubsystem* UDAIslandSubsystem::Get(const UObject* WorldContext)
{
	if (!WorldContext)
	{
		return nullptr;
	}
	const UWorld* World = WorldContext->GetWorld();
	return World ? World->GetSubsystem<UDAIslandSubsystem>() : nullptr;
}

void UDAIslandSubsystem::Tick(float DeltaTime)
{
	UWorld* World = GetWorld();
	if (!World || !World->IsGameWorld())
	{
		return;
	}

	ZonePollAccumulator += DeltaTime;
	if (ZonePollAccumulator >= 0.25f)
	{
		ZonePollAccumulator = 0.f;
		UpdateCurrentZone();
	}

	// Expire timed messages.
	if (MessageQueue.Num() > 0)
	{
		const FDAMessage& Msg = MessageQueue[0];
		if (Msg.Duration > 0.f && World->GetTimeSeconds() - ActiveMessageStart > Msg.Duration)
		{
			DismissMessage();
		}
	}
}

// ------------------------------------------------------------------------ zones

void UDAIslandSubsystem::RegisterZone(ADALocationVolume* Zone)
{
	if (Zone)
	{
		Zones.AddUnique(Zone);
	}
}

void UDAIslandSubsystem::UnregisterZone(ADALocationVolume* Zone)
{
	Zones.Remove(Zone);
}

TArray<ADALocationVolume*> UDAIslandSubsystem::GetZones() const
{
	TArray<ADALocationVolume*> Out;
	for (const TWeakObjectPtr<ADALocationVolume>& Z : Zones)
	{
		if (Z.IsValid())
		{
			Out.Add(Z.Get());
		}
	}
	Out.Sort([](const ADALocationVolume& A, const ADALocationVolume& B)
	{
		return A.SortOrder < B.SortOrder;
	});
	return Out;
}

bool UDAIslandSubsystem::IsDiscovered(const ADALocationVolume* Zone) const
{
	return Zone && Discovered.Contains(Zone->LocationId);
}

void UDAIslandSubsystem::UpdateCurrentZone()
{
	UWorld* World = GetWorld();
	APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (!Pawn)
	{
		return;
	}
	const FVector P = Pawn->GetActorLocation();

	ADALocationVolume* Best = nullptr;
	double BestVolume = TNumericLimits<double>::Max();
	for (const TWeakObjectPtr<ADALocationVolume>& WeakZone : Zones)
	{
		ADALocationVolume* Zone = WeakZone.Get();
		if (!Zone || !Zone->ContainsPoint(P))
		{
			continue;
		}
		const double Vol = Zone->GetZoneVolume();
		if (Vol < BestVolume)
		{
			BestVolume = Vol;
			Best = Zone;
		}
	}

	if (Best != CurrentZone.Get())
	{
		CurrentZone = Best;
		ZoneChangeTime = World->GetTimeSeconds();
		bLastZoneFirstVisit = false;
		if (Best)
		{
			bool bAlreadyKnown = false;
			Discovered.Add(Best->LocationId, &bAlreadyKnown);
			bLastZoneFirstVisit = !bAlreadyKnown;
			PlayUISound(bLastZoneFirstVisit ? FName(TEXT("A_Discover")) : FName(TEXT("A_UIClick")), bLastZoneFirstVisit ? 0.8f : 0.3f);
		}
		OnZoneChanged.Broadcast(Best, bLastZoneFirstVisit);
	}
}

// ------------------------------------------------------------------------ interactables

void UDAIslandSubsystem::RegisterInteractable(AActor* Interactable)
{
	if (Interactable)
	{
		Interactables.AddUnique(Interactable);
	}
}

void UDAIslandSubsystem::UnregisterInteractable(AActor* Interactable)
{
	Interactables.Remove(Interactable);
}

// ------------------------------------------------------------------------ messages

void UDAIslandSubsystem::PushMessage(const FDAMessage& Message)
{
	// A new message replaces whatever is on screen - interactions should feel immediate.
	MessageQueue.Reset();
	MessageQueue.Add(Message);
	if (const UWorld* World = GetWorld())
	{
		ActiveMessageStart = World->GetTimeSeconds();
	}
}

const FDAMessage* UDAIslandSubsystem::GetActiveMessage() const
{
	return MessageQueue.Num() > 0 ? &MessageQueue[0] : nullptr;
}

float UDAIslandSubsystem::GetActiveMessageAge() const
{
	const UWorld* World = GetWorld();
	return World ? World->GetTimeSeconds() - ActiveMessageStart : 0.f;
}

void UDAIslandSubsystem::DismissMessage()
{
	if (MessageQueue.Num() > 0)
	{
		MessageQueue.RemoveAt(0);
		if (const UWorld* World = GetWorld())
		{
			ActiveMessageStart = World->GetTimeSeconds();
		}
	}
}

// ------------------------------------------------------------------------ environment

ADAIslandManager* UDAIslandSubsystem::GetManager() const
{
	if (!CachedManager.IsValid())
	{
		if (UWorld* World = GetWorld())
		{
			for (TActorIterator<ADAIslandManager> It(World); It; ++It)
			{
				CachedManager = *It;
				break;
			}
		}
	}
	return CachedManager.Get();
}

float UDAIslandSubsystem::GetWaterSurfaceZ(const FVector& WorldLocation) const
{
	if (const ADAIslandManager* M = GetManager())
	{
		return M->GetWaterSurfaceZ(WorldLocation);
	}
	return 0.f;
}

void UDAIslandSubsystem::PlayUISound(const FName SoundName, float Volume) const
{
	const FString Path = FString::Printf(TEXT("%s%s.%s"), DuelAcademy::SoundFolder, *SoundName.ToString(), *SoundName.ToString());
	if (USoundBase* Sound = LoadObject<USoundBase>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet))
	{
		UGameplayStatics::PlaySound2D(this, Sound, Volume);
	}
}
