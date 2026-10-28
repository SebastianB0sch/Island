// Duel Academy Island - small data-driven world actors.

#include "DAWorldActors.h"

#include "Components/AudioComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DAIslandManager.h"
#include "DAIslandSubsystem.h"
#include "DATypes.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"

// ======================================================================== ADAInstancedScatter

ADAInstancedScatter::ADAInstancedScatter()
{
	PrimaryActorTick.bCanEverTick = false;
	Instances = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("Instances"));
	RootComponent = Instances;
	Instances->SetMobility(EComponentMobility::Static);
	Instances->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
	Instances->SetCanEverAffectNavigation(false);
}

void ADAInstancedScatter::SetInstances(UStaticMesh* Mesh, const TArray<FTransform>& Transforms, int32 CullStart, int32 CullEnd, bool bCollision, bool bCastShadow)
{
	Instances->ClearInstances();
	Instances->SetStaticMesh(Mesh);
	Instances->SetCullDistances(CullStart, CullEnd);
	Instances->SetCollisionEnabled(bCollision ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);
	Instances->SetCastShadow(bCastShadow);
	Instances->AddInstances(Transforms, false, true);
	Modify();
}

int32 ADAInstancedScatter::GetInstanceCount() const
{
	return Instances ? Instances->GetInstanceCount() : 0;
}

// ======================================================================== ADAFloatingActor

ADAFloatingActor::ADAFloatingActor()
{
	PrimaryActorTick.bCanEverTick = true;
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	RootComponent = Mesh;
	Mesh->SetMobility(EComponentMobility::Movable);
	Mesh->SetCollisionProfileName(UCollisionProfile::BlockAll_ProfileName);
}

void ADAFloatingActor::BeginPlay()
{
	Super::BeginPlay();
	BaseLocation = GetActorLocation();
	BaseRotation = GetActorRotation();
	Phase = FMath::FRandRange(0.f, 2.f * PI);
}

void ADAFloatingActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	Time += DeltaSeconds;
	const float W = 2.f * PI / FMath::Max(Period, 0.5f);
	const float Z = Amplitude * FMath::Sin(Time * W + Phase);
	const float Roll = Sway * FMath::Sin(Time * W * 0.7f + Phase * 1.3f);
	const float Pitch = Sway * 0.6f * FMath::Sin(Time * W * 0.53f + Phase * 0.7f);
	SetActorLocationAndRotation(BaseLocation + FVector(0.0, 0.0, Z),
		FRotator(BaseRotation.Pitch + Pitch, BaseRotation.Yaw, BaseRotation.Roll + Roll), false, nullptr, ETeleportType::None);
}

// ======================================================================== ADAEmitter

ADAEmitter::ADAEmitter()
{
	PrimaryActorTick.bCanEverTick = true;
	Puffs = CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Puffs"));
	RootComponent = Puffs;
	Puffs->SetMobility(EComponentMobility::Movable);
	Puffs->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Puffs->SetCastShadow(false);
	Puffs->NumCustomDataFloats = 1;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (SphereMesh.Succeeded())
	{
		Puffs->SetStaticMesh(SphereMesh.Object);
	}
}

void ADAEmitter::BeginPlay()
{
	Super::BeginPlay();
	Rng.Initialize(static_cast<int32>(GetUniqueID() * 31u + 7u));
	const float S = FMath::Max(EffectScale, 0.05f);
	int32 Count = 12;
	FLinearColor Color(0.95f, 0.95f, 0.97f);
	switch (Kind)
	{
	case EDAEmitterKind::Smoke:
		Count = 26; Lifetime = 13.f; Rise = 1150.f * S; Spread = 260.f * S; BaseSize = 1.1f * S; MaxOpacity = 0.55f;
		Color = FLinearColor(0.22f, 0.21f, 0.21f);
		break;
	case EDAEmitterKind::Mist:
		Count = 14; Lifetime = 5.5f; Rise = 70.f * S; Spread = 240.f * S; BaseSize = 1.0f * S; MaxOpacity = 0.22f;
		break;
	case EDAEmitterKind::Sparks:
		Count = 20; Lifetime = 1.6f; Rise = 500.f * S; Spread = 120.f * S; BaseSize = 0.08f * S; MaxOpacity = 1.f;
		Color = FLinearColor(1.f, 0.45f, 0.1f);
		break;
	case EDAEmitterKind::Steam:
	default:
		Count = 12; Lifetime = 3.5f; Rise = 360.f * S; Spread = 55.f * S; BaseSize = 0.45f * S; MaxOpacity = 0.33f;
		break;
	}
	UMaterialInterface* Base = Material ? Material.Get() : LoadObject<UMaterialInterface>(nullptr, DuelAcademy::SmokeMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (Base)
	{
		UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(Base, this);
		MID->SetVectorParameterValue(TEXT("Color"), Color);
		Puffs->SetMaterial(0, MID);
	}
	Puffs->ClearInstances();
	Particles.SetNum(Count);
	for (int32 i = 0; i < Count; ++i)
	{
		Respawn(Particles[i], true);
		Puffs->AddInstance(FTransform(FQuat::Identity, Particles[i].Start, FVector(0.01)), false);
		Puffs->SetCustomDataValue(i, 0, 0.f, false);
	}
}

void ADAEmitter::Respawn(FPuff& P, bool bInitial)
{
	P.Life = Lifetime * Rng.FRandRange(0.75f, 1.25f);
	P.Age = bInitial ? Rng.FRandRange(0.f, P.Life) : 0.f;
	const float A = Rng.FRandRange(0.f, 2.f * PI);
	const float R = Rng.FRandRange(0.f, Spread * 0.35f);
	P.Start = FVector(FMath::Cos(A) * R, FMath::Sin(A) * R, 0.0);
	const FVector Drift(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), 0.0);
	P.Velocity = FVector(Drift.X * Spread / Lifetime, Drift.Y * Spread / Lifetime, Rise / Lifetime * Rng.FRandRange(0.7f, 1.2f));
	P.Size0 = BaseSize * Rng.FRandRange(0.7f, 1.1f);
	P.Size1 = P.Size0 * (Kind == EDAEmitterKind::Sparks ? 0.3f : Rng.FRandRange(2.4f, 3.6f));
}

void ADAEmitter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	// Small emitters stop animating when the player is far away.
	CheckTimer -= DeltaSeconds;
	if (CheckTimer <= 0.f)
	{
		CheckTimer = 0.5f;
		bVisibleToPlayer = true;
		if (Kind != EDAEmitterKind::Smoke)
		{
			const APlayerController* PC = GetWorld()->GetFirstPlayerController();
			const APawn* Pawn = PC ? PC->GetPawn() : nullptr;
			bVisibleToPlayer = !Pawn || FVector::Dist(Pawn->GetActorLocation(), GetActorLocation()) < 25000.f * FMath::Max(EffectScale, 1.f);
		}
	}
	if (!bVisibleToPlayer)
	{
		return;
	}

	// Wind: a slow lean so smoke plumes drift.
	const FVector Wind(160.0, 60.0, 0.0);
	Transforms.SetNum(Particles.Num(), EAllowShrinking::No);
	for (int32 i = 0; i < Particles.Num(); ++i)
	{
		FPuff& P = Particles[i];
		P.Age += DeltaSeconds * Rate;
		if (P.Age >= P.Life)
		{
			Respawn(P, false);
		}
		const float T = P.Age / P.Life;
		const FVector Pos = P.Start + P.Velocity * P.Age + Wind * (Kind == EDAEmitterKind::Smoke ? T * T * EffectScale : 0.f);
		const float Size = FMath::Lerp(P.Size0, P.Size1, FMath::Sqrt(T));
		const float Opacity = MaxOpacity * FMath::Pow(FMath::Sin(T * PI), 0.8f);
		Transforms[i] = FTransform(FQuat::Identity, Pos, FVector(Size));
		Puffs->SetCustomDataValue(i, 0, Opacity, false);
	}
	// one batched update per frame (marks the render state dirty once)
	Puffs->BatchUpdateInstancesTransforms(0, Transforms, false, true, true);
}

// ======================================================================== ADALighthouseBeam

ADALighthouseBeam::ADALighthouseBeam()
{
	PrimaryActorTick.bCanEverTick = true;
	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	Spinner = CreateDefaultSubobject<USceneComponent>(TEXT("Spinner"));
	Spinner->SetupAttachment(Root);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(TEXT("/Engine/BasicShapes/Cone.Cone"));
	auto MakeBeam = [this](const TCHAR* Name, float Yaw) -> UStaticMeshComponent*
	{
		UStaticMeshComponent* B = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		B->SetupAttachment(Spinner);
		B->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		B->SetCastShadow(false);
		if (ConeMesh.Succeeded())
		{
			B->SetStaticMesh(ConeMesh.Object);
		}
		B->SetRelativeRotation(FRotator(0.f, Yaw, 0.f));
		return B;
	};
	auto MakeSpot = [this](const TCHAR* Name, float Yaw) -> USpotLightComponent*
	{
		USpotLightComponent* L = CreateDefaultSubobject<USpotLightComponent>(Name);
		L->SetupAttachment(Spinner);
		L->SetRelativeRotation(FRotator(-2.f, Yaw, 0.f));
		L->SetInnerConeAngle(2.f);
		L->SetOuterConeAngle(5.f);
		L->SetAttenuationRadius(60000.f);
		L->SetLightColor(FLinearColor(1.f, 0.93f, 0.75f));
		L->SetCastShadows(false);
		L->SetIntensityUnits(ELightUnits::Unitless);
		L->SetIntensity(0.f);
		return L;
	};
	BeamA = MakeBeam(TEXT("BeamA"), 0.f);
	BeamB = MakeBeam(TEXT("BeamB"), 180.f);
	SpotA = MakeSpot(TEXT("SpotA"), 0.f);
	SpotB = MakeSpot(TEXT("SpotB"), 180.f);
}

void ADALighthouseBeam::BeginPlay()
{
	Super::BeginPlay();
	UMaterialInterface* Beam = LoadObject<UMaterialInterface>(nullptr, DuelAcademy::BeamMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);
	for (UStaticMeshComponent* B : { BeamA.Get(), BeamB.Get() })
	{
		// Engine cone: 100 cm tall along +Z with the apex up. Lay it along the beam with the apex at the lamp.
		const float Len = BeamLength / 100.f;
		const FRotator Yaw = B->GetRelativeRotation();
		B->SetRelativeRotation(FRotator(90.f, Yaw.Yaw, 0.f));
		B->SetRelativeLocation(Yaw.Vector() * BeamLength * 0.5f);
		B->SetRelativeScale3D(FVector(Len * 0.08f, Len * 0.08f, Len));
		if (Beam)
		{
			B->SetMaterial(0, Beam);
		}
	}
}

void ADALighthouseBeam::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	Spinner->AddLocalRotation(FRotator(0.f, RotationSpeed * DeltaSeconds, 0.f));

	float Night = 1.f;
	if (const UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		if (const ADAIslandManager* M = Sub->GetManager())
		{
			Night = M->GetNightFactor();
		}
	}
	Intensity = FMath::FInterpTo(Intensity, Night, DeltaSeconds, 1.5f);
	const bool bOn = Intensity > 0.05f;
	SpotA->SetIntensity(300000.f * Intensity);
	SpotB->SetIntensity(300000.f * Intensity);
	BeamA->SetVisibility(bOn);
	BeamB->SetVisibility(bOn);
}

// ======================================================================== ADAAmbientSound

ADAAmbientSound::ADAAmbientSound()
{
	PrimaryActorTick.bCanEverTick = false;
	Audio = CreateDefaultSubobject<UAudioComponent>(TEXT("Audio"));
	RootComponent = Audio;
	Audio->bAutoActivate = false;
}

void ADAAmbientSound::BeginPlay()
{
	Super::BeginPlay();
	if (!Sound)
	{
		return;
	}
	Audio->SetSound(Sound);
	Audio->bAllowSpatialization = true;
	Audio->bOverrideAttenuation = true;
	Audio->AttenuationOverrides.bAttenuate = true;
	Audio->AttenuationOverrides.bSpatialize = true;
	Audio->AttenuationOverrides.AttenuationShape = EAttenuationShape::Sphere;
	Audio->AttenuationOverrides.AttenuationShapeExtents = FVector(Radius * 0.2f, 0.0, 0.0);
	Audio->AttenuationOverrides.FalloffDistance = Radius;
	Audio->SetVolumeMultiplier(Volume);
	Audio->Play(FMath::FRandRange(0.f, 5.f));
}
