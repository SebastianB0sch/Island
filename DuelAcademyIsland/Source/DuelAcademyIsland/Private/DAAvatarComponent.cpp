// Duel Academy Island - procedural student avatar.

#include "DAAvatarComponent.h"

#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace
{
	// Joint layout of the SM_Avatar_* parts (cm, avatar space: +Y forward before the -90 yaw).
	const FVector HipHeight(0.0, 0.0, 93.0);
	const FVector HeadJoint(0.0, 0.0, 56.0);
	const FVector ArmLJoint(-21.0, 0.0, 48.0);
	const FVector ArmRJoint(21.0, 0.0, 48.0);
	const FVector LegLJoint(-9.0, 0.0, 0.0);
	const FVector LegRJoint(9.0, 0.0, 0.0);
	const FVector DiskOnArm(-4.0, 0.0, -40.0);
}

UDAAvatarComponent::UDAAvatarComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
	// The part meshes are authored facing UE +Y (Blender -Y); turn them to face the owner's +X.
	SetRelativeRotation(FRotator(0.f, -90.f, 0.f));
}

UStaticMeshComponent* UDAAvatarComponent::MakePart(const TCHAR* MeshName, USceneComponent* Parent, const FVector& Offset)
{
	const FString Path = FString::Printf(TEXT("%s%s.%s"), DuelAcademy::AvatarFolder, MeshName, MeshName);
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);

	UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(GetOwner(), NAME_None, RF_Transient);
	C->SetupAttachment(Parent);
	C->SetRelativeLocation(Offset);
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	C->SetGenerateOverlapEvents(false);
	C->SetCanEverAffectNavigation(false);
	C->bCastDynamicShadow = true;
	C->CastShadow = true;
	if (Mesh)
	{
		C->SetStaticMesh(Mesh);
	}
	C->RegisterComponent();
	return C;
}

namespace
{
	const TCHAR* CharacterFolder = TEXT("/Game/DuelAcademy/Characters/");

	template <typename T>
	T* LoadCharacterAsset(const FString& Name)
	{
		return LoadObject<T>(nullptr, *FString::Printf(TEXT("%s%s.%s"), CharacterFolder, *Name, *Name), nullptr, LOAD_NoWarn | LOAD_Quiet);
	}
}

void UDAAvatarComponent::FinishSkeletal(USkeletalMesh* Mesh)
{
	SkelComp = NewObject<USkeletalMeshComponent>(GetOwner(), NAME_None, RF_Transient);
	SkelComp->SetupAttachment(this);
	SkelComp->SetSkeletalMeshAsset(Mesh);
	SkelComp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SkelComp->SetGenerateOverlapEvents(false);
	SkelComp->SetCanEverAffectNavigation(false);
	SkelComp->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	SkelComp->RegisterComponent();
	SetRelativeScale3D(FVector(BodyScale));
}

bool UDAAvatarComponent::SetupCast()
{
	if (CastMesh.IsEmpty() || AnimGroup.IsEmpty())
	{
		return false;
	}
	USkeletalMesh* Mesh = LoadCharacterAsset<USkeletalMesh>(CastMesh);
	if (!Mesh)
	{
		return false;
	}
	for (const TCHAR* State : { TEXT("Idle"), TEXT("Walk"), TEXT("Run"), TEXT("Jump"), TEXT("Fall"), TEXT("Land"), TEXT("Swim"),
		TEXT("Wave"), TEXT("Duel"), TEXT("Sit"), TEXT("Yes"), TEXT("No"), TEXT("Clap"), TEXT("Interact") })
	{
		if (UAnimSequence* Seq = LoadCharacterAsset<UAnimSequence>(FString::Printf(TEXT("A_Anime_%s_%s"), *AnimGroup, State)))
		{
			Anims.Add(FName(State), Seq);
		}
	}
	if (!Anims.Contains(TEXT("Idle")))
	{
		Anims.Reset();
		return false;
	}
	FinishSkeletal(Mesh);
	bAnimeCast = true;
	if (bShowDuelDisk)
	{
		if (USkeletalMesh* DiskMesh = LoadCharacterAsset<USkeletalMesh>(FString::Printf(TEXT("SK_Anime_%s_DuelDisk"), *AnimGroup)))
		{
			// same skeleton: the disk follows the body's pose
			DiskComp = NewObject<USkeletalMeshComponent>(GetOwner(), NAME_None, RF_Transient);
			DiskComp->SetupAttachment(SkelComp);
			DiskComp->SetSkeletalMeshAsset(DiskMesh);
			DiskComp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			DiskComp->SetCanEverAffectNavigation(false);
			DiskComp->RegisterComponent();
			DiskComp->SetLeaderPoseComponent(SkelComp);
		}
	}
	return true;
}

bool UDAAvatarComponent::SetupSkeletal()
{
	if (SetupCast())
	{
		return true;
	}
	USkeletalMesh* Mesh = LoadCharacterAsset<USkeletalMesh>(TEXT("SK_Student"));
	if (!Mesh)
	{
		return false;
	}
	for (const TCHAR* State : { TEXT("Idle"), TEXT("Walk"), TEXT("Run"), TEXT("Jump"), TEXT("Swim"), TEXT("Wave") })
	{
		if (UAnimSequence* Seq = LoadCharacterAsset<UAnimSequence>(FString::Printf(TEXT("A_Student_%s"), State)))
		{
			Anims.Add(FName(State), Seq);
		}
	}
	if (!Anims.Contains(TEXT("Idle")))
	{
		return false;   // a mesh without animations would T-pose; keep the procedural avatar
	}
	FinishSkeletal(Mesh);
	// SK_Student's walk / run cycles were tuned for these speeds
	WalkAnimSpeed = 320.f;
	RunAnimSpeed = 750.f;
	return true;
}

UAnimSequence* UDAAvatarComponent::FindAnim(FName State) const
{
	const TObjectPtr<UAnimSequence>* Found = Anims.Find(State);
	return Found ? Found->Get() : nullptr;
}

void UDAAvatarComponent::TickSkeletal(float DeltaTime, float GroundSpeed, bool bInAir)
{
	static const FName NameIdle(TEXT("Idle"));
	static const FName NameWalk(TEXT("Walk"));
	static const FName NameRun(TEXT("Run"));
	static const FName NameJump(TEXT("Jump"));
	static const FName NameFall(TEXT("Fall"));
	static const FName NameSwim(TEXT("Swim"));
	static const FName NameWave(TEXT("Wave"));
	static const FName NameDuel(TEXT("Duel"));
	const float VerticalSpeed = GetOwner() ? GetOwner()->GetVelocity().Z : 0.f;
	FName Want = NameIdle;
	float Rate = 1.f;
	bool bLoop = true;
	if (SwimAlpha > 0.5f)
	{
		Want = FindAnim(NameSwim) ? NameSwim : NameWalk;
		Rate = FindAnim(NameSwim) ? 1.f : 0.7f;
	}
	else if (bInAir && FindAnim(NameJump))
	{
		// rising: the jump take (once); falling: the fall loop when there is one
		Want = (VerticalSpeed < -50.f && FindAnim(NameFall)) ? NameFall : NameJump;
		bLoop = Want == NameFall;
	}
	else if (GroundSpeed > (WalkAnimSpeed + RunAnimSpeed) * 0.5f + 60.f && FindAnim(NameRun))
	{
		Want = NameRun;
		Rate = FMath::Clamp(GroundSpeed / RunAnimSpeed, 0.8f, 3.f);   // the player sprints at 950 cm/s
	}
	else if (GroundSpeed > 20.f && FindAnim(NameWalk))
	{
		Want = NameWalk;
		Rate = FMath::Clamp(GroundSpeed / WalkAnimSpeed, 0.45f, 2.0f);
	}
	else if (DuelPoseAlpha > 0.5f && (FindAnim(NameDuel) || FindAnim(NameWave)))
	{
		Want = FindAnim(NameDuel) ? NameDuel : NameWave;
		bLoop = Want == NameDuel;
	}
	if (Want != CurrentAnim)
	{
		if (UAnimSequence* Seq = FindAnim(Want))
		{
			SkelComp->PlayAnimation(Seq, bLoop);
			CurrentAnim = Want;
		}
	}
	SkelComp->SetPlayRate(Rate);
	// lean the whole body forward while swimming
	SkelComp->SetRelativeRotation(FRotator(0.f, 0.f, -70.f * SwimAlpha));
	SkelComp->SetRelativeLocation(FVector(0.0, 0.0, 60.0 * SwimAlpha));
}

void UDAAvatarComponent::BeginPlay()
{
	Super::BeginPlay();

	if (bPreferSkeletal && SetupSkeletal())
	{
		ApplyColours();
		return;
	}

	Pelvis = NewObject<USceneComponent>(GetOwner(), NAME_None, RF_Transient);
	Pelvis->SetupAttachment(this);
	Pelvis->SetRelativeLocation(HipHeight);
	Pelvis->RegisterComponent();
	SetRelativeScale3D(FVector(BodyScale));

	Torso = MakePart(TEXT("SM_Avatar_Torso"), Pelvis, FVector::ZeroVector);
	Head = MakePart(TEXT("SM_Avatar_Head"), Torso, HeadJoint);
	ArmL = MakePart(TEXT("SM_Avatar_ArmL"), Torso, ArmLJoint);
	ArmR = MakePart(TEXT("SM_Avatar_ArmR"), Torso, ArmRJoint);
	LegL = MakePart(TEXT("SM_Avatar_LegL"), Pelvis, LegLJoint);
	LegR = MakePart(TEXT("SM_Avatar_LegR"), Pelvis, LegRJoint);
	if (bShowDuelDisk)
	{
		Disk = MakePart(TEXT("SM_Avatar_DuelDisk"), ArmL, DiskOnArm);
	}
	BreathPhase = FMath::FRand() * 6.28f;
	ApplyColours();
}

void UDAAvatarComponent::SetDorm(EDADorm NewDorm)
{
	Dorm = NewDorm;
	ApplyColours();
}

void UDAAvatarComponent::ApplyColours()
{
	if (SkelComp)
	{
		if (bAnimeCast && !bDormTint)
		{
			return;   // named characters keep their own colours
		}
		if (JacketMaterials.Num() == 0)
		{
			const TArray<FName> Slots = SkelComp->GetMaterialSlotNames();
			for (int32 i = 0; i < Slots.Num(); ++i)
			{
				const FString SlotName = Slots[i].ToString().ToLower();
				// anime cast: only the neutral "...JacketTint" / "...HairTint" slots; SK_Student: keyword match
				const bool bJacket = bAnimeCast ? SlotName.Contains(TEXT("jackettint"))
					: JacketSlotKeywords.ContainsByPredicate([&SlotName](const FString& K) { return SlotName.Contains(K); });
				const bool bHair = bAnimeCast ? SlotName.Contains(TEXT("hairtint")) : SlotName.Contains(TEXT("hair"));
				if (!bJacket && !bHair)
				{
					continue;
				}
				if (UMaterialInstanceDynamic* MID = SkelComp->CreateDynamicMaterialInstance(i))
				{
					if (bJacket)
					{
						JacketMaterials.Add(MID);
					}
					else
					{
						MID->SetVectorParameterValue(TEXT("Tint"), HairColor);
					}
				}
			}
		}
		for (UMaterialInstanceDynamic* MID : JacketMaterials)
		{
			if (MID)
			{
				MID->SetVectorParameterValue(TEXT("Tint"), DuelAcademy::DormColor(Dorm));
			}
		}
		return;
	}
	if (!Torso)
	{
		return;
	}
	if (JacketMaterials.Num() == 0)
	{
		for (UStaticMeshComponent* Part : { Torso.Get(), ArmL.Get(), ArmR.Get() })
		{
			if (!Part || !Part->GetStaticMesh())
			{
				continue;
			}
			const int32 Slot = Part->GetMaterialIndex(TEXT("M_Jacket"));
			if (Slot != INDEX_NONE)
			{
				if (UMaterialInstanceDynamic* MID = Part->CreateDynamicMaterialInstance(Slot))
				{
					JacketMaterials.Add(MID);
				}
			}
		}
		if (Head && Head->GetStaticMesh())
		{
			const int32 HairSlot = Head->GetMaterialIndex(TEXT("M_Hair"));
			if (HairSlot != INDEX_NONE)
			{
				if (UMaterialInstanceDynamic* MID = Head->CreateDynamicMaterialInstance(HairSlot))
				{
					MID->SetVectorParameterValue(TEXT("Tint"), HairColor);
				}
			}
		}
	}
	const FLinearColor Color = DuelAcademy::DormColor(Dorm);
	for (UMaterialInstanceDynamic* MID : JacketMaterials)
	{
		if (MID)
		{
			MID->SetVectorParameterValue(TEXT("Tint"), Color);
		}
	}
}

void UDAAvatarComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	const AActor* Owner = GetOwner();
	FVector Velocity = Owner ? Owner->GetVelocity() : FVector::ZeroVector;
	bool bInAir = false;
	if (const ACharacter* Char = Cast<ACharacter>(Owner))
	{
		if (const UCharacterMovementComponent* Move = Char->GetCharacterMovement())
		{
			bInAir = Move->IsFalling();
		}
	}
	const float GroundSpeed = FVector(Velocity.X, Velocity.Y, 0.0).Size();
	if (SkelComp)
	{
		TickSkeletal(DeltaTime, GroundSpeed, bInAir);
		return;
	}
	if (!Pelvis || !Torso)
	{
		return;
	}
	Time += DeltaTime;
	SmoothedSpeed = FMath::FInterpTo(SmoothedSpeed, GroundSpeed, DeltaTime, 8.f);
	AirAlpha = FMath::FInterpTo(AirAlpha, (bInAir && SwimAlpha < 0.5f) ? 1.f : 0.f, DeltaTime, 10.f);

	const float Move01 = FMath::Clamp(SmoothedSpeed / StrideSpeed, 0.f, 1.6f);
	// Stride frequency grows with speed (~1.6 Hz walk, ~2.6 Hz run)
	const float Freq = 1.2f + 0.9f * FMath::Min(Move01, 1.6f);
	Phase += DeltaTime * Freq * 2.f * PI * (Move01 > 0.02f ? 1.f : 0.f);
	if (Phase > 2.f * PI)
	{
		Phase -= 2.f * PI;
	}

	const float StrideAmp = 34.f * FMath::Min(Move01, 1.f) + 10.f * FMath::Max(Move01 - 1.f, 0.f);
	const float S = FMath::Sin(Phase);
	const float Bob = FMath::Abs(FMath::Cos(Phase)) * 3.5f * FMath::Min(Move01, 1.2f);

	// Idle breathing
	const float Breath = FMath::Sin(Time * 1.6f + BreathPhase);

	// ---- legs / arms (roll = rotation about the avatar's lateral X axis)
	float LegLAngle = S * StrideAmp;
	float LegRAngle = -S * StrideAmp;
	float ArmLAngle = -S * StrideAmp * 0.8f;
	float ArmRAngle = S * StrideAmp * 0.8f;
	float ArmSpread = 4.f + Breath * 1.f;
	float TorsoLean = -4.f * FMath::Min(Move01, 1.4f);

	// Jump / fall pose
	LegLAngle = FMath::Lerp(LegLAngle, -25.f, AirAlpha);
	LegRAngle = FMath::Lerp(LegRAngle, 12.f, AirAlpha);
	ArmLAngle = FMath::Lerp(ArmLAngle, 35.f, AirAlpha);
	ArmRAngle = FMath::Lerp(ArmRAngle, 35.f, AirAlpha);
	ArmSpread = FMath::Lerp(ArmSpread, 35.f, AirAlpha);

	// Dueling pose: left (disk) arm raised forward
	ArmLAngle = FMath::Lerp(ArmLAngle, 80.f, DuelPoseAlpha);

	// Swimming: crawl stroke
	if (SwimAlpha > 0.01f)
	{
		const float SwimPhase = Time * 3.2f;
		ArmLAngle = FMath::Lerp(ArmLAngle, FMath::RadiansToDegrees(SwimPhase) , SwimAlpha);
		ArmRAngle = FMath::Lerp(ArmRAngle, FMath::RadiansToDegrees(SwimPhase + PI), SwimAlpha);
		LegLAngle = FMath::Lerp(LegLAngle, FMath::Sin(Time * 9.f) * 15.f, SwimAlpha);
		LegRAngle = FMath::Lerp(LegRAngle, -FMath::Sin(Time * 9.f) * 15.f, SwimAlpha);
		ArmSpread = FMath::Lerp(ArmSpread, 12.f, SwimAlpha);
	}

	LegL->SetRelativeRotation(FRotator(0.f, 0.f, LegLAngle));
	LegR->SetRelativeRotation(FRotator(0.f, 0.f, LegRAngle));
	ArmL->SetRelativeRotation(FRotator(-ArmSpread, 0.f, ArmLAngle));
	ArmR->SetRelativeRotation(FRotator(ArmSpread, 0.f, ArmRAngle));

	// ---- body
	const float SwimPitch = 80.f * SwimAlpha;
	Pelvis->SetRelativeLocation(HipHeight + FVector(0.0, 0.0, Bob - 2.0 * Breath * (1.f - Move01) * 0.5f - 60.0 * SwimAlpha));
	Pelvis->SetRelativeRotation(FRotator(0.f, 0.f, TorsoLean * 0.4f - SwimPitch));
	Torso->SetRelativeRotation(FRotator(0.f, 0.f, TorsoLean + FMath::Sin(Phase * 2.f) * 1.5f * Move01));
	Torso->SetRelativeScale3D(FVector(1.0, 1.0 + 0.012 * Breath, 1.0 + 0.008 * Breath));
	Head->SetRelativeRotation(FRotator(0.f, FMath::Sin(Time * 0.37f + BreathPhase) * 8.f * (1.f - Move01 * 0.7f),
		-TorsoLean * 0.6f + SwimPitch * 0.6f));
}
