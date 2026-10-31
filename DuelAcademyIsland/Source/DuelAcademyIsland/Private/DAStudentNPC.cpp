// Duel Academy Island - ambient student NPC.

#include "DAStudentNPC.h"

#include "AIController.h"
#include "Components/CapsuleComponent.h"
#include "DAAvatarComponent.h"
#include "DACardDatabase.h"
#include "DAHUD.h"
#include "DAIslandSubsystem.h"
#include "DAStorySubsystem.h"
#include "DAStudentCharacter.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"


namespace
{
	ADAHUD* GetDuelHUD(const AActor* Context)
	{
		if (const UWorld* World = Context ? Context->GetWorld() : nullptr)
		{
			if (APlayerController* PC = World->GetFirstPlayerController())
			{
				return Cast<ADAHUD>(PC->GetHUD());
			}
		}
		return nullptr;
	}

	FString DuelistIdFromName(const FString& Name)
	{
		if (Name.Contains(TEXT("Sheppard"), ESearchCase::IgnoreCase)) return TEXT("sheppard");
		if (Name.Contains(TEXT("Crowler"), ESearchCase::IgnoreCase)) return TEXT("crowler");
		if (Name.Contains(TEXT("Fontaine"), ESearchCase::IgnoreCase)) return TEXT("fontaine");
		if (Name.Contains(TEXT("Shadow Duelist"), ESearchCase::IgnoreCase)) return TEXT("shadow_duelist");
		if (Name.Contains(TEXT("Goblin King"), ESearchCase::IgnoreCase)) return TEXT("topher");
		FString First = Name;
		int32 Space = INDEX_NONE;
		if (Name.FindChar(TEXT(' '), Space))
		{
			First = Name.Left(Space);
		}
		return First.ToLower();
	}
}

ADAStudentNPC::ADAStudentNPC()
{
	PrimaryActorTick.bCanEverTick = true;
	GetCapsuleComponent()->InitCapsuleSize(36.f, 92.f);

	bUseControllerRotationYaw = false;
	UCharacterMovementComponent* Move = GetCharacterMovement();
	Move->bOrientRotationToMovement = true;
	Move->RotationRate = FRotator(0.f, 240.f, 0.f);
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
		Avatar->BodyScale = BodyScale > 0.f ? BodyScale : Rng.FRandRange(0.93f, 1.05f);
		if (!CastMesh.IsEmpty())
		{
			Avatar->CastMesh = CastMesh;
			Avatar->AnimGroup = AnimGroup;
		}
		Avatar->bDormTint = bDormTint;
		static const FLinearColor Hair[] = {
			FLinearColor(0.05f, 0.025f, 0.01f), FLinearColor(0.20f, 0.07f, 0.02f), FLinearColor(0.01f, 0.01f, 0.012f),
			FLinearColor(0.55f, 0.35f, 0.08f), FLinearColor(0.02f, 0.05f, 0.25f), FLinearColor(0.45f, 0.05f, 0.03f) };
		Avatar->HairColor = Hair[Rng.RandRange(0, static_cast<int32>(UE_ARRAY_COUNT(Hair)) - 1)];
		Avatar->bShowDuelDisk = Rng.FRand() < 0.6f;
	}
	Super::BeginPlay();

	if (!DisplayName.IsEmpty())
	{
		const FString Id = DuelistIdFromName(DisplayName);
		static const TMap<FString, FString> DuelistDecks = {
			{ TEXT("jaden"), TEXT("jaden_year1") },
			{ TEXT("syrus"), TEXT("syrus_roids") },
			{ TEXT("chumley"), TEXT("chumley_koala") },
			{ TEXT("bastion"), TEXT("bastion_chem") },
			{ TEXT("chazz"), TEXT("chazz_ojama") },
			{ TEXT("alexis"), TEXT("alexis_cyber") },
			{ TEXT("jasmine"), TEXT("jasmine_amazoness") },
			{ TEXT("mindy"), TEXT("mindy_fairy") },
			{ TEXT("zane"), TEXT("zane_cyber") },
			{ TEXT("crowler"), TEXT("crowler_ancient_gear") },
			{ TEXT("banner"), TEXT("banner_alchemy") },
			{ TEXT("sheppard"), TEXT("sheppard_year1") },
			{ TEXT("brier"), TEXT("brier_quiz") },
			{ TEXT("beauregard"), TEXT("beauregard_rock") },
			{ TEXT("sartyr"), TEXT("sartyr_curry") },
			{ TEXT("fontaine"), TEXT("fontaine_nurse") },
			{ TEXT("topher"), TEXT("topher_goblin") },
			{ TEXT("conklin"), TEXT("conklin_dino") },
			{ TEXT("damon"), TEXT("damon_exodia") },
			{ TEXT("dimitri"), TEXT("dimitri_copycat") },
			{ TEXT("gerard"), TEXT("gerard_quiz") },
			{ TEXT("blair"), TEXT("blair_toon") },
			{ TEXT("torrey"), TEXT("torrey_insect") },
			{ TEXT("shadow_duelist"), TEXT("shadow_duelist_fiend") },
			{ TEXT("titan"), TEXT("shadow_duelist_fiend") },
			{ TEXT("mimicry"), TEXT("mimicry_stall") },
			{ TEXT("pharaoh"), TEXT("pharaoh_guardian") }
		};
		if (const FString* Deck = DuelistDecks.Find(Id))
		{
			bDuelist = true;
			DuelOpponentId = Id.StartsWith(TEXT("dr.")) ? TEXT("crowler") : Id;
			DuelDeckId = *Deck;
		}
	}

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
	return DisplayName.IsEmpty() ? DuelAcademy::DormName(Dorm) + TEXT(" student") : DisplayName;
}

bool ADAStudentNPC::CanInteract(const ADAStudentCharacter* By) const
{
	const ADAHUD* HUD = GetDuelHUD(this);
	return !HUD || !HUD->IsDuelOpen();
}

void ADAStudentNPC::Interact(ADAStudentCharacter* By)
{
	// Talk-triggered story events are deliberately skipped by the auto-start
	// path; this is the world interaction that starts them. A named NPC can be
	// both a story contact and a free duelist, so the story gets first refusal.
	if (UDAStorySubsystem* Story = UDAStorySubsystem::Get(this))
	{
		const FString StoryNpcId = !DuelOpponentId.IsEmpty() ? DuelOpponentId : DisplayName;
		if (Story->NotifyTalkToNPC(StoryNpcId))
		{
			TalkTime = GetWorld()->GetTimeSeconds();
			bHasTalked = true;
			return;
		}
	}

	if (bDuelist && bHasTalked)
	{
		if (ADAHUD* HUD = GetDuelHUD(this))
		{
			HUD->OpenDuelDeckSelect(DuelOpponentId, GetInteractName(), DuelDeckId);
			if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
			{
				Sub->PlayUISound(TEXT("A_DuelStart"), 1.f);
			}
			return;
		}
	}

	const TArray<FString>& Said = Lines.Num() > 0 ? Lines : DuelAcademy::NpcLines(Dorm);
	if (Said.Num() == 0)
	{
		return;
	}
	TalkTime = GetWorld()->GetTimeSeconds();
	bHasTalked = true;
	FString Line = Said[LineIndex % Said.Num()];
	++LineIndex;
	if (Lines.Num() == 0 && By && By->GetDorm() != Dorm && Dorm == EDADorm::Obelisk && By->GetDorm() == EDADorm::Slifer && Rng.FRand() < 0.5f)
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
