// Duel Academy Island - interior portal / door trigger implementation.

#include "DAInteriorPortal.h"

#include "Camera/PlayerCameraManager.h"
#include "Components/BoxComponent.h"
#include "DAIslandSubsystem.h"
#include "DATypes.h"
#include "DAStudentCharacter.h"
#include "DuelAcademyIsland.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Controller.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PawnMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "TimerManager.h"

#if WITH_EDITORONLY_DATA
#include "Components/BillboardComponent.h"
#endif

FDAPortalFlagQuery ADAInteriorPortal::FlagQuery;

ADAInteriorPortal::ADAInteriorPortal()
{
	PrimaryActorTick.bCanEverTick = false;

	Trigger = CreateDefaultSubobject<UBoxComponent>(TEXT("Trigger"));
	RootComponent = Trigger;
	Trigger->SetBoxExtent(TriggerExtent, false);
	Trigger->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Trigger->SetCollisionObjectType(ECC_WorldStatic);
	Trigger->SetCollisionResponseToAllChannels(ECR_Ignore);
	Trigger->SetCollisionResponseToChannel(ECC_Pawn, ECR_Overlap);
	Trigger->SetGenerateOverlapEvents(true);
	Trigger->SetCanEverAffectNavigation(false);
	Trigger->ShapeColor = FColor(80, 180, 255);
	Trigger->SetLineThickness(3.f);

#if WITH_EDITORONLY_DATA
	EditorIcon = CreateEditorOnlyDefaultSubobject<UBillboardComponent>(TEXT("EditorIcon"));
	if (EditorIcon)
	{
		EditorIcon->SetupAttachment(Trigger);
		EditorIcon->bIsScreenSizeScaled = true;
	}
#endif
}

void ADAInteriorPortal::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

	if (Trigger)
	{
		Trigger->SetBoxExtent(TriggerExtent, false);
	}

#if WITH_EDITORONLY_DATA
	if (EditorIcon)
	{
		EditorIcon->SetRelativeLocation(FVector(0.f, 0.f, TriggerExtent.Z + 40.f));
	}
#endif
}

void ADAInteriorPortal::BeginPlay()
{
	Super::BeginPlay();

	if (Trigger)
	{
		Trigger->OnComponentBeginOverlap.AddDynamic(this, &ADAInteriorPortal::HandleBeginOverlap);
		Trigger->OnComponentEndOverlap.AddDynamic(this, &ADAInteriorPortal::HandleEndOverlap);
	}

	ValidatePairing();

	if (bInteractable)
	{
		if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
		{
			Sub->RegisterInteractable(this);
		}
	}
}

void ADAInteriorPortal::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		Sub->UnregisterInteractable(this);
	}

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(TeleportTimer);
		World->GetTimerManager().ClearTimer(SuppressTimer);
		// The pending finish will never run; do not leave the fade-out up.
		if (bTeleportPending)
		{
			if (APlayerController* PC = World->GetFirstPlayerController())
			{
				if (PC->PlayerCameraManager && FadeInSeconds > 0.f)
				{
					PC->PlayerCameraManager->StartCameraFade(1.f, 0.f, FadeInSeconds, FadeColor, false, false);
				}
			}
			bTeleportPending = false;
		}
	}

	Super::EndPlay(EndPlayReason);
}

void ADAInteriorPortal::ValidatePairing() const
{
	if (PortalId.IsEmpty())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Portal %s has an empty PortalId; it cannot be paired or saved."), *GetName());
		return;
	}

	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	int32 SameIdCount = 0;
	for (TActorIterator<ADAInteriorPortal> It(World); It; ++It)
	{
		if (*It && (*It)->PortalId == PortalId)
		{
			++SameIdCount;
		}
	}
	if (SameIdCount > 1)
	{
		UE_LOG(LogDuelAcademyIsland, Warning,
			TEXT("Portal id '%s' is used by %d actors; FindLinkedPortal resolves the first match."),
			*PortalId, SameIdCount);
	}

	if (TargetPortalId.IsEmpty())
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Portal %s has no TargetPortalId and only uses its fallback target."), *PortalId);
		return;
	}
	if (TargetPortalId == PortalId)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Portal %s targets itself; the link is ignored."), *PortalId);
		return;
	}

	const ADAInteriorPortal* Linked = FindLinkedPortal();
	if (!Linked)
	{
		UE_LOG(LogDuelAcademyIsland, Warning,
			TEXT("Portal %s targets missing portal '%s'; the fallback target is used."), *PortalId, *TargetPortalId);
		return;
	}
	if (Linked->TargetPortalId != PortalId)
	{
		UE_LOG(LogDuelAcademyIsland, Warning,
			TEXT("Portal %s links to %s, but %s links back to '%s' instead of '%s'."),
			*PortalId, *Linked->PortalId, *Linked->PortalId, *Linked->TargetPortalId, *PortalId);
	}
}

// ---------------------------------------------------------------------------- overlap

void ADAInteriorPortal::HandleBeginOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
	UPrimitiveComponent* OtherComp, int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult)
{
	if (!bAutoTrigger || bTeleportPending || !OtherActor)
	{
		return;
	}

	if (OtherActor == SuppressedUser.Get())
	{
		return;
	}

	const APawn* Pawn = Cast<APawn>(OtherActor);
	if (Pawn && Pawn->IsPlayerControlled())
	{
		TryUse(OtherActor);
	}
}

void ADAInteriorPortal::HandleEndOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor,
	UPrimitiveComponent* OtherComp, int32 OtherBodyIndex)
{
	if (OtherActor && OtherActor == SuppressedUser.Get())
	{
		SuppressedUser.Reset();
		if (UWorld* World = GetWorld())
		{
			World->GetTimerManager().ClearTimer(SuppressTimer);
		}
	}
}

// ---------------------------------------------------------------------------- use / teleport

bool ADAInteriorPortal::TryUse(AActor* User)
{
	if (!User || bTeleportPending)
	{
		return false;
	}

	if (!CanUsePortal(User))
	{
		if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
		{
			FDAMessage Message;
			Message.Title = DisplayName;
			Message.Body = LockReason;
			Message.Accent = FLinearColor(0.95f, 0.55f, 0.15f);
			Message.Duration = 4.f;
			Sub->PushMessage(Message);
		}
		return false;
	}

	if (IsOnCooldown())
	{
		return false;
	}

	const UWorld* World = GetWorld();
	if (!World)
	{
		return false;
	}

	// Refuse an unconfigured portal rather than teleporting the player to the
	// world origin (which the fall rescue would then treat as a real arrival).
	if (TargetLocation.IsNearlyZero() && (!bSnapToLinkedPortal || !FindLinkedPortal()))
	{
		UE_LOG(LogDuelAcademyIsland, Warning,
			TEXT("Portal %s has no reachable destination; use cancelled."), *PortalId);
		return false;
	}

	CooldownUntil = World->GetTimeSeconds() + FMath::Max(0.1f, CooldownSeconds);
	bUsed = true;

	if (ADAInteriorPortal* Linked = FindLinkedPortal())
	{
		// The destination must not immediately bounce the player back, and it must
		// not re-trigger while the player is still standing inside its volume.
		Linked->ArmCooldown(CooldownSeconds + FadeOutSeconds + FadeInSeconds);
		Linked->SuppressFor(User);
	}

	BeginTeleport(User);
	return true;
}

void ADAInteriorPortal::BeginTeleport(AActor* User)
{
	bTeleportPending = true;
	PendingUser = User;

	if (bSnapToLinkedPortal)
	{
		if (const ADAInteriorPortal* Linked = FindLinkedPortal())
		{
			PendingLocation = Linked->GetActorLocation() + Linked->GetActorForwardVector() * ArrivalOffset;
			PendingYaw = Linked->GetActorRotation().Yaw;
		}
		else
		{
			PendingLocation = TargetLocation;
			PendingYaw = TargetYaw;
		}
	}
	else
	{
		PendingLocation = TargetLocation;
		PendingYaw = TargetYaw;
	}

	APlayerController* PC = nullptr;
	if (const APawn* Pawn = Cast<APawn>(User))
	{
		PC = Cast<APlayerController>(Pawn->GetController());
	}
	if (!PC && GetWorld())
	{
		PC = GetWorld()->GetFirstPlayerController();
	}

	if (PC && PC->PlayerCameraManager && FadeOutSeconds > 0.f)
	{
		PC->PlayerCameraManager->StartCameraFade(0.f, 1.f, FadeOutSeconds, FadeColor, false, true);
		GetWorldTimerManager().SetTimer(TeleportTimer, this, &ADAInteriorPortal::FinishTeleport,
			FadeOutSeconds, false);
	}
	else
	{
		FinishTeleport();
	}
}

void ADAInteriorPortal::FinishTeleport()
{
	AActor* User = PendingUser.Get();
	if (User)
	{
		ApplyArrival(User);
	}

	// Fade back in even if the user disappeared during the fade-out; otherwise
	// the camera would stay black until the next transition.
	APlayerController* PC = nullptr;
	if (const APawn* Pawn = Cast<APawn>(User))
	{
		PC = Cast<APlayerController>(Pawn->GetController());
	}
	if (!PC && GetWorld())
	{
		PC = GetWorld()->GetFirstPlayerController();
	}
	if (PC && PC->PlayerCameraManager && FadeInSeconds > 0.f)
	{
		PC->PlayerCameraManager->StartCameraFade(1.f, 0.f, FadeInSeconds, FadeColor, false, false);
	}

	if (User)
	{
		OnPortalUsed.Broadcast(this, User);
	}

	PendingUser.Reset();
	bTeleportPending = false;
}

void ADAInteriorPortal::ApplyArrival(AActor* User)
{
	if (!User)
	{
		return;
	}

	if (const APawn* Pawn = Cast<APawn>(User))
	{
		if (UPawnMovementComponent* Movement = Pawn->GetMovementComponent())
		{
			Movement->StopMovementImmediately();
		}
	}

	User->SetActorLocationAndRotation(PendingLocation, FRotator(0.f, PendingYaw, 0.f), false, nullptr,
		ETeleportType::TeleportPhysics);

	// Interior cells are generated far below the island; tell the character so
	// its fall-out-of-world rescue and swimming logic do not undo the teleport.
	// Called after the move so leaving a cell can re-anchor the rescue at the
	// arrival point.
	if (ADAStudentCharacter* Character = Cast<ADAStudentCharacter>(User))
	{
		Character->SetInInterior(PendingLocation.Z < -20000.f);
	}

	if (APawn* Pawn = Cast<APawn>(User))
	{
		if (AController* Controller = Pawn->GetController())
		{
			// Keep the player's look pitch; only the yaw belongs to the door.
			const FRotator Current = Controller->GetControlRotation();
			Controller->SetControlRotation(FRotator(Current.Pitch, PendingYaw, 0.f));
		}
	}
}

// ---------------------------------------------------------------------------- lock / cooldown

void ADAInteriorPortal::SetLocked(bool bNewLocked, const FString& InReason)
{
	bLocked = bNewLocked;
	if (!InReason.IsEmpty())
	{
		LockReason = InReason;
	}
}

bool ADAInteriorPortal::IsOnCooldown() const
{
	const UWorld* World = GetWorld();
	return World && World->GetTimeSeconds() < CooldownUntil;
}

void ADAInteriorPortal::ArmCooldown(float Seconds)
{
	if (const UWorld* World = GetWorld())
	{
		CooldownUntil = FMath::Max(CooldownUntil, static_cast<double>(World->GetTimeSeconds()) + FMath::Max(0.f, Seconds));
	}
}

void ADAInteriorPortal::SuppressFor(AActor* User)
{
	SuppressedUser = User;

	if (UWorld* World = GetWorld())
	{
		const float SafetySeconds = FMath::Max(0.75f, CooldownSeconds + FadeOutSeconds + FadeInSeconds + 0.25f);
		// Refresh, don't stack: an old timer must not clear a newer suppression.
		World->GetTimerManager().ClearTimer(SuppressTimer);
		World->GetTimerManager().SetTimer(SuppressTimer, this, &ADAInteriorPortal::ClearSuppression, SafetySeconds, false);
	}
}

void ADAInteriorPortal::ClearSuppression()
{
	SuppressedUser.Reset();
}

bool ADAInteriorPortal::CanUsePortal_Implementation(AActor* User) const
{
	(void)User;

	if (bLocked)
	{
		return false;
	}

	if (!RequiredFlag.IsEmpty())
	{
		if (FlagQuery.IsBound())
		{
			return FlagQuery.Execute(RequiredFlag);
		}
		// Until A02 binds the flag query, do not silently seal every door in the level.
		return !bFailClosedWhenFlagQueryMissing;
	}

	return true;
}

ADAInteriorPortal* ADAInteriorPortal::FindLinkedPortal() const
{
	UWorld* World = GetWorld();
	if (!World || TargetPortalId.IsEmpty())
	{
		return nullptr;
	}

	ADAInteriorPortal* Best = nullptr;
	for (TActorIterator<ADAInteriorPortal> It(World); It; ++It)
	{
		ADAInteriorPortal* Other = *It;
		if (!Other || Other == this || Other->PortalId != TargetPortalId)
		{
			continue;
		}
		// Duplicate ids are invalid (logged at BeginPlay), but picking by name
		// keeps the resolution deterministic instead of depending on iteration order.
		if (!Best || Other->GetName() < Best->GetName())
		{
			Best = Other;
		}
	}
	return Best;
}

FDAPortalSaveState ADAInteriorPortal::GetSaveState() const
{
	FDAPortalSaveState State;
	State.PortalId = PortalId;
	State.bLocked = bLocked;
	State.bUsed = bUsed;
	return State;
}

void ADAInteriorPortal::ApplySaveState(const FDAPortalSaveState& State)
{
	// An empty save id is not a wildcard: applying it to every portal would
	// overwrite unrelated door state after a malformed payload.
	if (State.PortalId.IsEmpty() || State.PortalId != PortalId)
	{
		return;
	}
	// Assigning both flags is idempotent, so a retried load cannot toggle state.
	bLocked = State.bLocked;
	bUsed = State.bUsed;
}

void ADAInteriorPortal::CollectSaveStates(UWorld* World, TArray<FDAPortalSaveState>& OutStates)
{
	OutStates.Reset();
	if (!World)
	{
		return;
	}

	TArray<ADAInteriorPortal*> Portals;
	for (TActorIterator<ADAInteriorPortal> It(World); It; ++It)
	{
		ADAInteriorPortal* Portal = *It;
		if (Portal && !Portal->PortalId.IsEmpty())
		{
			Portals.Add(Portal);
		}
	}
	Portals.Sort([](const ADAInteriorPortal& A, const ADAInteriorPortal& B)
	{
		if (A.PortalId != B.PortalId)
		{
			return A.PortalId < B.PortalId;
		}
		return A.GetName() < B.GetName();
	});

	TSet<FString> SeenIds;
	for (ADAInteriorPortal* Portal : Portals)
	{
		if (SeenIds.Contains(Portal->PortalId))
		{
			continue;
		}
		SeenIds.Add(Portal->PortalId);
		OutStates.Add(Portal->GetSaveState());
	}
}

int32 ADAInteriorPortal::ApplySaveStates(UWorld* World, const TArray<FDAPortalSaveState>& States)
{
	if (!World)
	{
		return 0;
	}

	// Resolve each id once, deterministically (duplicate actor ids keep the
	// name-ordered first actor, matching FindLinkedPortal).
	TMap<FString, ADAInteriorPortal*> PortalsById;
	for (TActorIterator<ADAInteriorPortal> It(World); It; ++It)
	{
		ADAInteriorPortal* Portal = *It;
		if (!Portal || Portal->PortalId.IsEmpty())
		{
			continue;
		}
		ADAInteriorPortal*& Existing = PortalsById.FindOrAdd(Portal->PortalId);
		if (!Existing || Portal->GetName() < Existing->GetName())
		{
			Existing = Portal;
		}
	}

	int32 Applied = 0;
	TSet<FString> SeenIds;
	for (const FDAPortalSaveState& State : States)
	{
		// Empty ids are not wildcards, and duplicate entries must not let a
		// later row overwrite the first one.
		if (State.PortalId.IsEmpty() || SeenIds.Contains(State.PortalId))
		{
			continue;
		}
		SeenIds.Add(State.PortalId);

		ADAInteriorPortal* Target = PortalsById.FindRef(State.PortalId);
		if (!Target)
		{
			// Unknown id (actor not loaded, content removed, or a hand-edited
			// save): ignore it rather than failing the whole load.
			continue;
		}
		Target->ApplySaveState(State);
		++Applied;
	}
	return Applied;
}

// ---------------------------------------------------------------------------- interactable

FString ADAInteriorPortal::GetInteractPrompt() const
{
	return CanUsePortal(nullptr) ? Prompt : TEXT("Locked");
}

FString ADAInteriorPortal::GetInteractName() const
{
	return DisplayName;
}

bool ADAInteriorPortal::CanInteract(const ADAStudentCharacter* By) const
{
	(void)By;
	return bInteractable && !bTeleportPending;
}

void ADAInteriorPortal::Interact(ADAStudentCharacter* By)
{
	TryUse(By);
}
