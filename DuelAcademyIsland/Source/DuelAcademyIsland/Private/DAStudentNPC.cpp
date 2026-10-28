// Duel Academy Island - ambient student NPC.

#include "DAStudentNPC.h"

#include "AIController.h"
#include "Components/CapsuleComponent.h"
#include "DAAvatarComponent.h"
#include "DACardDatabase.h"
#include "DAIslandSubsystem.h"
#include "DAStudentCharacter.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"

ADAStudentNPC::ADAStudentNPC()
{
	PrimaryActorTick.bCanEverTick = true;
	GetCapsuleComponent()->InitCapsuleSize(36.f, 92.f);

	bUseControllerRotationYaw = false;
	UCharacterMovementComponent* Move = GetCharacterMovement();
	Move->bOrientRotationToMovement = true;
	Move->RotationRate = FRotator(0.f, 300.f, 0.f);
	Move->MaxWalkSpeed = StrollSpeed;
	Move->BrakingDecelerationWalking = 800.f;
	Move->SetWalkableFloorAngle(40.f);

	AIControllerClass = AAIController::StaticClass();
	AutoPossessAI = EAutoPossessAI::PlacedInWorldOrSpawned;

	Avatar = CreateDefaultSubobject<UDAAvatarComponent>(TEXT("Avatar"));
	Avatar->SetupAttachment(GetCapsuleComponent());
	Avatar->SetRelativeLocation(FVector(0.0, 0.0, -92.0));
	Avatar->StrideSpeed = 300.f;

	GetMesh()->SetVisibility(false);
	GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void ADAStudentNPC::BeginPlay()
{
	Rng.Initialize(static_cast<int32>(GetUniqueID() * 7919u + 17u));
	if (Avatar)
	{
		Avatar->Dorm = Dorm;
		Avatar->BodyScale = Rng.FRandRange(0.93f, 1.05f);
		static const FLinearColor Hair[] = {
			FLinearColor(0.05f, 0.025f, 0.01f), FLinearColor(0.20f, 0.07f, 0.02f), FLinearColor(0.01f, 0.01f, 0.012f),
			FLinearColor(0.55f, 0.35f, 0.08f), FLinearColor(0.02f, 0.05f, 0.25f), FLinearColor(0.45f, 0.05f, 0.03f) };
		Avatar->HairColor = Hair[Rng.RandRange(0, static_cast<int32>(UE_ARRAY_COUNT(Hair)) - 1)];
		Avatar->bShowDuelDisk = Rng.FRand() < 0.6f;
	}
	Super::BeginPlay();

	Home = GetActorLocation();
	Target = Home;
	IdleTime = Rng.FRandRange(0.5f, 4.f);
	LineIndex = Rng.RandRange(0, 100);
	GetCharacterMovement()->MaxWalkSpeed = StrollSpeed;
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		Sub->RegisterInteractable(this);
	}
}

void ADAStudentNPC::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		Sub->UnregisterInteractable(this);
	}
	Super::EndPlay(EndPlayReason);
}

FString ADAStudentNPC::GetInteractName() const
{
	return DuelAcademy::DormName(Dorm) + TEXT(" student");
}

void ADAStudentNPC::Interact(ADAStudentCharacter* By)
{
	const TArray<FString>& Lines = DuelAcademy::NpcLines(Dorm);
	if (Lines.Num() == 0)
	{
		return;
	}
	TalkTime = GetWorld()->GetTimeSeconds();
	FString Line = Lines[LineIndex % Lines.Num()];
	++LineIndex;
	if (By && By->GetDorm() != Dorm && Dorm == EDADorm::Obelisk && By->GetDorm() == EDADorm::Slifer && Rng.FRand() < 0.5f)
	{
		Line = TEXT("A Slifer Slacker talking to an Obelisk? How bold. ...Fine, what do you want?");
	}
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		FDAMessage Msg;
		Msg.Title = GetInteractName();
		Msg.Body = FString::Printf(TEXT("\"%s\""), *Line);
		Msg.Accent = DuelAcademy::DormColor(Dorm) * 1.6f;
		Msg.Accent.A = 1.f;
		Msg.Duration = 7.f;
		Sub->PushMessage(Msg);
		Sub->PlayUISound(TEXT("A_UIClick"), 0.4f);
	}
}

void ADAStudentNPC::PickNewTarget()
{
	const float Angle = Rng.FRandRange(0.f, 2.f * PI);
	const float Dist = Rng.FRandRange(0.25f, 1.f) * WanderRadius;
	Target = Home + FVector(FMath::Cos(Angle) * Dist, FMath::Sin(Angle) * Dist, 0.0);
	IdleTime = 0.f;
	StuckTime = 0.f;
}

bool ADAStudentNPC::IsSafeAhead(const FVector& Dir) const
{
	// Refuse to walk off ledges / into water: probe the ground 1.2 m ahead.
	const FVector Start = GetActorLocation() + Dir * 120.0;
	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(DANpcLedge), false, this);
	const bool bHit = GetWorld()->LineTraceSingleByChannel(Hit, Start, Start - FVector(0.0, 0.0, 260.0), ECC_Visibility, Params);
	if (!bHit)
	{
		return false;
	}
	if (const UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		if (Hit.ImpactPoint.Z < Sub->GetWaterSurfaceZ(Hit.ImpactPoint) + 20.f)
		{
			return false;
		}
	}
	return true;
}

void ADAStudentNPC::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	// Face the player while talking / when they come close.
	const APlayerController* PC = World->GetFirstPlayerController();
	const APawn* Player = PC ? PC->GetPawn() : nullptr;
	const bool bTalking = World->GetTimeSeconds() - TalkTime < 6.f;
	if (Player && (bTalking || FVector::Dist(Player->GetActorLocation(), GetActorLocation()) < 260.f))
	{
		const FVector To = Player->GetActorLocation() - GetActorLocation();
		const FRotator Want(0.f, FMath::RadiansToDegrees(FMath::Atan2(To.Y, To.X)), 0.f);
		SetActorRotation(FMath::RInterpTo(GetActorRotation(), Want, DeltaSeconds, 5.f));
		return;
	}

	if (WanderRadius <= 1.f)
	{
		return;
	}

	if (IdleTime > 0.f)
	{
		IdleTime -= DeltaSeconds;
		if (IdleTime <= 0.f)
		{
			PickNewTarget();
		}
		return;
	}

	FVector To = Target - GetActorLocation();
	To.Z = 0.0;
	if (To.Size() < 60.0)
	{
		IdleTime = Rng.FRandRange(2.f, 7.f);
		return;
	}
	const FVector Dir = To.GetSafeNormal();
	if (!IsSafeAhead(Dir))
	{
		IdleTime = Rng.FRandRange(0.5f, 2.f);
		return;
	}
	AddMovementInput(Dir, 1.f);

	// Got stuck against something? Pick another spot.
	if (GetVelocity().Size2D() < 20.f)
	{
		StuckTime += DeltaSeconds;
		if (StuckTime > 1.5f)
		{
			IdleTime = Rng.FRandRange(0.5f, 2.f);
		}
	}
	else
	{
		StuckTime = 0.f;
	}
}
