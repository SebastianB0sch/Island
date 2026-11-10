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
#include "Engine/OverlapResult.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Math/RotationMatrix.h"
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
	Amplitude = FMath::IsFinite(Amplitude) ? Amplitude : 0.f;
	Period = FMath::IsFinite(Period) ? FMath::Max(Period, 0.5f) : 5.f;
	Sway = FMath::IsFinite(Sway) ? Sway : 0.f;
	HeaveLimit = FMath::IsFinite(HeaveLimit) ? FMath::Max(HeaveLimit, 0.f) : 8.f;
	TiltLimit = FMath::IsFinite(TiltLimit) ? FMath::Max(TiltLimit, 0.f) : 5.f;
	Damping = FMath::IsFinite(Damping) ? FMath::Clamp(Damping, 0.1f, 2.f) : 0.7f;

	// Hull footprint from the mesh bounds (actor space): where the wave surface is sampled.
	if (const UStaticMesh* HullMesh = Mesh ? Mesh->GetStaticMesh() : nullptr)
	{
		const FBoxSphereBounds Bounds = HullMesh->GetBounds();
		const FVector Scale = GetActorScale3D().GetAbs();
		HullCenter = FVector(Bounds.Origin.X * Scale.X, Bounds.Origin.Y * Scale.Y, 0.0);
		HullHalfLength = FMath::Max(static_cast<float>(Bounds.BoxExtent.X * Scale.X), 10.f);
		HullHalfWidth = FMath::Max(static_cast<float>(Bounds.BoxExtent.Y * Scale.Y), 10.f);
	}
	if (!FMath::IsFinite(ResponseTime) || ResponseTime <= 0.f)
	{
		// A 1 m buoy answers in about half a second, the 60 m ferry takes a few seconds.
		ResponseTime = FMath::Clamp(0.5f + 2.f * FMath::Max(HullHalfLength, HullHalfWidth) / 1500.f, 0.5f, 5.f);
	}
}

void ADAFloatingActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	Time += DeltaSeconds;
	if (!TickBuoyancy(DeltaSeconds))
	{
		TickSineBob();
	}
}

void ADAFloatingActor::TickSineBob()
{
	const float W = 2.f * PI / FMath::Max(Period, 0.5f);
	const float Z = Amplitude * FMath::Sin(Time * W + Phase);
	const float Roll = Sway * FMath::Sin(Time * W * 0.7f + Phase * 1.3f);
	const float Pitch = Sway * 0.6f * FMath::Sin(Time * W * 0.53f + Phase * 0.7f);
	SetActorLocationAndRotation(BaseLocation + FVector(0.0, 0.0, Z),
		FRotator(BaseRotation.Pitch + Pitch, BaseRotation.Yaw, BaseRotation.Roll + Roll), false, nullptr, ETeleportType::None);
}

bool ADAFloatingActor::TickBuoyancy(float DeltaSeconds)
{
	if (!bUseWaves)
	{
		return false;
	}
	const ADAIslandManager* Manager = CachedManager.Get();
	if (!Manager)
	{
		const UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this);
		CachedManager = Sub ? Sub->GetManager() : nullptr;
		Manager = CachedManager.Get();
	}
	if (!Manager || !Manager->HasWaveData())
	{
		return false;
	}

	// Sample the surface at the middle, bow, stern, port and starboard of the hull's rest position.
	const FRotator Heading(0.f, BaseRotation.Yaw, 0.f);
	const FVector Forward = Heading.RotateVector(FVector::ForwardVector);
	const FVector Right = Heading.RotateVector(FVector::RightVector);
	const FVector Center = BaseLocation + Heading.RotateVector(HullCenter);
	const FDAWaterInfo Mid = Manager->QueryWater(Center, true);
	if (!Mid.bWaves)
	{
		return false;   // flat water here (river, pond, or this body has no wave set): keep the sine bob
	}
	const float Along = HullHalfLength * 0.8f;
	const float Across = HullHalfWidth * 0.8f;
	auto WaveAt = [Manager](const FVector& P)
	{
		const FDAWaterInfo Info = Manager->QueryWater(P, true);
		return Info.SurfaceZ - Info.StillZ;
	};
	const float HMid = Mid.SurfaceZ - Mid.StillZ;
	const float HBow = WaveAt(Center + Forward * Along);
	const float HStern = WaveAt(Center - Forward * Along);
	const float HStar = WaveAt(Center + Right * Across);
	const float HPort = WaveAt(Center - Right * Across);

	// A little of the old idle bob stays in, so a hull on a nearly flat lake is not frozen.
	const float W = 2.f * PI / FMath::Max(Period, 0.5f);
	const float MaxHeave = FMath::Abs(Amplitude) * HeaveLimit;
	const float MaxTilt = FMath::Abs(Sway) * TiltLimit;
	const float TargetHeave = FMath::Clamp((HBow + HStern + HStar + HPort + 2.f * HMid) / 6.f
		+ 0.15f * Amplitude * FMath::Sin(Time * W + Phase), -MaxHeave, MaxHeave);
	// FRotator: positive pitch lifts the bow (+X), positive roll dips the starboard side (+Y).
	const float TargetPitch = FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan2(HBow - HStern, 2.f * Along))
		+ 0.1f * Sway * FMath::Sin(Time * W * 0.53f + Phase * 0.7f), -MaxTilt, MaxTilt);
	const float TargetRoll = FMath::Clamp(-FMath::RadiansToDegrees(FMath::Atan2(HStar - HPort, 2.f * Across))
		+ 0.15f * Sway * FMath::Sin(Time * W * 0.7f + Phase * 1.3f), -MaxTilt, MaxTilt);

	// Damped springs, integrated in small steps so a long frame cannot blow them up.
	const float Omega = 2.f * PI / FMath::Max(ResponseTime, 0.1f);
	float Remaining = FMath::Clamp(DeltaSeconds, 0.f, 0.25f);
	while (Remaining > 1.e-5f)
	{
		const float Dt = FMath::Min(Remaining, 1.f / 60.f);
		Remaining -= Dt;
		HeaveVel += (Omega * Omega * (TargetHeave - Heave) - 2.f * Damping * Omega * HeaveVel) * Dt;
		Heave += HeaveVel * Dt;
		PitchVel += (Omega * Omega * (TargetPitch - PitchDeg) - 2.f * Damping * Omega * PitchVel) * Dt;
		PitchDeg += PitchVel * Dt;
		RollVel += (Omega * Omega * (TargetRoll - RollDeg) - 2.f * Damping * Omega * RollVel) * Dt;
		RollDeg += RollVel * Dt;
	}
	if (!FMath::IsFinite(Heave) || !FMath::IsFinite(PitchDeg) || !FMath::IsFinite(RollDeg))
	{
		Heave = HeaveVel = PitchDeg = PitchVel = RollDeg = RollVel = 0.f;
	}
	SetActorLocationAndRotation(BaseLocation + FVector(0.0, 0.0, Heave),
		FRotator(BaseRotation.Pitch + PitchDeg, BaseRotation.Yaw, BaseRotation.Roll + RollDeg), false, nullptr, ETeleportType::None);
	return true;
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
	EffectScale = FMath::IsFinite(EffectScale) ? FMath::Max(EffectScale, 0.05f) : 1.f;
	// A negative rate would run particle ages backwards and feed a negative
	// fraction into the opacity curve (NaN); zero freezes the plume.
	Rate = FMath::IsFinite(Rate) ? FMath::Max(Rate, 0.f) : 1.f;
	Ring = FMath::IsFinite(Ring) ? FMath::Max(Ring, 0.f) : 0.f;
	RingPoints = FMath::Max(RingPoints, 0);
	RingAngle = FMath::IsFinite(RingAngle) ? RingAngle : 0.f;
	JetSpread = FMath::IsFinite(JetSpread) ? FMath::Clamp(JetSpread, 0.f, 45.f) : 2.5f;
	FloorZ = FMath::IsFinite(FloorZ) ? FloorZ : static_cast<float>(GetActorLocation().Z);
	if (JetVelocity.ContainsNaN())
	{
		JetVelocity = FVector(0.0, 0.0, 600.0);
	}
	const float S = EffectScale;
	int32 Count = 12;
	float Glow = -1.f;   // >= 0: emissive strength of M_DA_Spray's "Glow" parameter
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
	case EDAEmitterKind::Spray:
		// Rise = hop height, Spread = how far a droplet flies out; Lifetime is only the scale of the
		// horizontal speed - each droplet lives exactly as long as its hop takes (see Respawn).
		// About eight droplets per metre of ring radius keep a landing circle busy.
		Count = Ring > 0.f ? FMath::Clamp(FMath::RoundToInt(Ring * 0.08f), 16, 64) : 18;
		Lifetime = 0.55f; Rise = 35.f * S; Spread = 60.f * S; BaseSize = 0.045f * S; MaxOpacity = 0.85f;
		Gravity = 980.f;
		Color = FLinearColor(0.92f, 0.97f, 1.f);
		break;
	case EDAEmitterKind::Jet:
	{
		// A stream of droplets on a projectile path. Lifetime = the flight time from the nozzle down to the
		// water at FloorZ; Rise / Spread describe the splash droplets thrown up where the stream lands.
		Gravity = 980.f;
		JetLocalVelocity = GetActorTransform().InverseTransformVectorNoScale(JetVelocity);
		const float Drop = FloorZ - static_cast<float>(GetActorLocation().Z);   // <= 0: the water is below the nozzle
		const float Vz = static_cast<float>(JetLocalVelocity.Z);
		const float Disc = Vz * Vz - 2.f * Gravity * Drop;
		JetFlightTime = FMath::Clamp(Disc > 0.f ? (Vz + FMath::Sqrt(Disc)) / Gravity : 0.3f, 0.15f, 6.f);
		Lifetime = JetFlightTime;
		// About 70 droplets per second of flight keep the stream closed; a third as many splash droplets.
		const int32 Stream = FMath::Clamp(FMath::RoundToInt(70.f * FMath::Clamp(Rate, 0.25f, 3.f) * JetFlightTime), 14, 140);
		const int32 Splash = FMath::Clamp(Stream / 3, 6, 36);
		FirstSplash = NextSplash = Stream;
		Count = Stream + Splash;
		Rise = 22.f * S; Spread = 30.f * S; BaseSize = 0.05f * S; MaxOpacity = 0.9f;
		Color = FLinearColor(0.92f, 0.97f, 1.f);
		break;
	}
	case EDAEmitterKind::Fireflies:
		// Spread = radius of the swarm, Rise = height of the band the motes drift in.
		Count = 16; Lifetime = 6.f; Rise = 160.f * S; Spread = 300.f * S; BaseSize = 0.035f; MaxOpacity = 1.f;
		Color = FLinearColor(0.75f, 1.f, 0.3f);
		Glow = 60.f;
		break;
	case EDAEmitterKind::Steam:
	default:
		Count = 12; Lifetime = 3.5f; Rise = 360.f * S; Spread = 55.f * S; BaseSize = 0.45f * S; MaxOpacity = 0.33f;
		break;
	}
	UMaterialInterface* Base = Material.Get();
	if (!Base && (Kind == EDAEmitterKind::Spray || Kind == EDAEmitterKind::Jet || Kind == EDAEmitterKind::Fireflies))
	{
		Base = LoadObject<UMaterialInterface>(nullptr, DuelAcademy::SprayMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);
	}
	if (!Base)
	{
		Base = LoadObject<UMaterialInterface>(nullptr, DuelAcademy::SmokeMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);
	}
	if (Base)
	{
		UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(Base, this);
		MID->SetVectorParameterValue(TEXT("Color"), Color);
		if (Glow >= 0.f)
		{
			MID->SetScalarParameterValue(TEXT("Glow"), Glow);
		}
		Puffs->SetMaterial(0, MID);
	}
	Puffs->ClearInstances();
	Particles.SetNum(Count);
	for (int32 i = 0; i < Count; ++i)
	{
		Particles[i].bSplash = Kind == EDAEmitterKind::Jet && i >= FirstSplash;
		Respawn(Particles[i], true);
		Puffs->AddInstance(FTransform(FQuat::Identity, Particles[i].Start, FVector(0.01)), false);
		Puffs->SetCustomDataValue(i, 0, 0.f, false);
	}
}

FTransform ADAEmitter::DropletTransform(const FVector& Pos, const FVector& Vel, float Size, float StretchPerSpeed)
{
	// A falling drop reads as a short streak: stretch the sphere along its velocity (up to 4x at speed).
	const float Speed = static_cast<float>(Vel.Size());
	if (Speed < 1.f || StretchPerSpeed <= 0.f)
	{
		return FTransform(FQuat::Identity, Pos, FVector(Size));
	}
	const float Stretch = 1.f + FMath::Min(Speed * StretchPerSpeed, 3.f);
	return FTransform(FRotationMatrix::MakeFromX(Vel).ToQuat(), Pos, FVector(Size * Stretch, Size, Size));
}

void ADAEmitter::RespawnJet(FPuff& P, bool bInitial)
{
	if (P.bSplash)
	{
		// Splash droplets sleep until a stream droplet lands (TriggerSplash).
		P.bIdle = true;
		P.Age = 0.f;
		P.Life = 1.f;
		return;
	}
	// Leave the nozzle inside a narrow cone with a few percent of speed jitter: the stream frays as it flies.
	const FVector Axis = JetLocalVelocity.GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
	FVector U = FVector::CrossProduct(Axis, FMath::Abs(Axis.Z) < 0.9 ? FVector::UpVector : FVector::ForwardVector).GetSafeNormal();
	const FVector V = FVector::CrossProduct(Axis, U);
	const float Cone = FMath::DegreesToRadians(JetSpread) * FMath::Sqrt(Rng.FRand());
	const float Around = Rng.FRandRange(0.f, 2.f * PI);
	const FVector Dir = Axis * FMath::Cos(Cone) + (U * FMath::Cos(Around) + V * FMath::Sin(Around)) * FMath::Sin(Cone);
	P.Velocity = Dir * (JetLocalVelocity.Size() * Rng.FRandRange(0.96f, 1.04f));
	P.Start = (U * Rng.FRandRange(-1.f, 1.f) + V * Rng.FRandRange(-1.f, 1.f)) * (BaseSize * 20.0);
	// Its own flight time down to the water (the jitter changes it a little).
	const float Drop = FloorZ - static_cast<float>(GetActorLocation().Z);
	const float Vz = static_cast<float>(P.Velocity.Z);
	const float Disc = Vz * Vz - 2.f * Gravity * Drop;
	P.Life = FMath::Clamp(Disc > 0.f ? (Vz + FMath::Sqrt(Disc)) / Gravity : JetFlightTime, 0.1f, 8.f);
	P.Age = bInitial ? Rng.FRandRange(0.f, P.Life) : 0.f;
	P.bIdle = false;
	P.Size0 = BaseSize * Rng.FRandRange(0.65f, 1.1f);
	P.Size1 = P.Size0 * 0.7f;
}

void ADAEmitter::TriggerSplash(const FVector& Where)
{
	if (FirstSplash >= Particles.Num())
	{
		return;
	}
	FPuff& P = Particles[NextSplash];
	NextSplash = NextSplash + 1 < Particles.Num() ? NextSplash + 1 : FirstSplash;
	// Thrown up and outward from the landing point; back on the water after exactly one hop.
	const float Up = FMath::Sqrt(2.f * Gravity * FMath::Max(Rise, 1.f)) * Rng.FRandRange(0.45f, 1.f);
	const float Out = Spread / 0.4f * Rng.FRandRange(0.2f, 1.f);
	const float A = Rng.FRandRange(0.f, 2.f * PI);
	P.bIdle = false;
	P.Start = Where;
	P.Velocity = FVector(FMath::Cos(A) * Out, FMath::Sin(A) * Out, Up);
	P.Age = 0.f;
	P.Life = FMath::Max(2.f * Up / Gravity, 0.05f);
	P.Size0 = BaseSize * Rng.FRandRange(0.45f, 0.8f);
	P.Size1 = P.Size0 * 0.6f;
}

void ADAEmitter::TickFireflies(float DeltaSeconds)
{
	// Night only: fade in at dusk, hide the component by day.
	float Night = 1.f;
	if (const UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		if (const ADAIslandManager* M = Sub->GetManager())
		{
			Night = M->GetNightFactor();
		}
	}
	Night = FMath::IsFinite(Night) ? FMath::Clamp(Night, 0.f, 1.f) : 1.f;
	NightGlow = FMath::FInterpTo(NightGlow, Night, DeltaSeconds, 0.5f);
	const bool bShow = NightGlow > 0.02f;
	if (Puffs->IsVisible() != bShow)
	{
		Puffs->SetVisibility(bShow);
	}
	if (!bShow)
	{
		return;
	}
	const float T = static_cast<float>(GetWorld()->GetTimeSeconds());
	Transforms.SetNum(Particles.Num(), EAllowShrinking::No);
	for (int32 i = 0; i < Particles.Num(); ++i)
	{
		const FPuff& P = Particles[i];
		// Each mote wanders round its own home on three slow, unrelated sines and blinks at its own pace.
		const float K = P.Seed;
		const FVector Drift(FMath::Sin(T * 0.31f + K) * 70.0, FMath::Cos(T * 0.23f + K * 1.7f) * 70.0, FMath::Sin(T * 0.41f + K * 0.6f) * 28.0);
		const float Blink = FMath::Max(0.f, FMath::Sin(T * (0.8f + 0.9f * FMath::Frac(K * 0.137f)) + K * 2.3f));
		const float Light = Blink * Blink * Blink;
		Transforms[i] = FTransform(FQuat::Identity, P.Start + Drift, FVector(BaseSize * (0.6f + 0.4f * Light)));
		Puffs->SetCustomDataValue(i, 0, MaxOpacity * NightGlow * Light, false);
	}
	Puffs->BatchUpdateInstancesTransforms(0, Transforms, false, true, true);
}

void ADAEmitter::Respawn(FPuff& P, bool bInitial)
{
	if (Kind == EDAEmitterKind::Jet)
	{
		RespawnJet(P, bInitial);
		return;
	}
	if (Kind == EDAEmitterKind::Fireflies)
	{
		// Motes never respawn: a home inside the swarm's cylinder and a random number for drift and blink.
		const float A = Rng.FRandRange(0.f, 2.f * PI);
		const float R = Spread * FMath::Sqrt(Rng.FRand());
		P.Start = FVector(FMath::Cos(A) * R, FMath::Sin(A) * R, Rng.FRandRange(30.f, FMath::Max(Rise, 40.f)));
		P.Seed = Rng.FRandRange(0.f, 1000.f);
		P.Life = Lifetime;
		P.Age = 0.f;
		return;
	}
	P.Life = Lifetime * Rng.FRandRange(0.75f, 1.25f);
	P.Age = bInitial ? Rng.FRandRange(0.f, P.Life) : 0.f;
	float A = Rng.FRandRange(0.f, 2.f * PI);
	float R = Rng.FRandRange(0.f, Spread * 0.35f);
	if (Ring > 0.f)
	{
		if (RingPoints > 0)
		{
			A = FMath::DegreesToRadians(RingAngle) + 2.f * PI * static_cast<float>(Rng.RandRange(0, RingPoints - 1)) / RingPoints;
		}
		R = Ring + Rng.FRandRange(-0.15f, 0.15f) * Spread;
	}
	const FVector Out(FMath::Cos(A), FMath::Sin(A), 0.0);   // away from the axis
	const FVector Side(-Out.Y, Out.X, 0.0);
	P.Start = Out * R;
	if (Ring > 0.f && RingPoints > 0)
	{
		P.Start += Side * (Rng.FRandRange(-0.12f, 0.12f) * Spread);   // a jet's splash, not a single point
	}
	if (Kind == EDAEmitterKind::Spray)
	{
		// Thrown up (and mostly outward) from the water surface; it lands back on it after exactly one hop.
		const float Up = FMath::Sqrt(2.f * Gravity * Rise) * Rng.FRandRange(0.55f, 1.f);
		P.Life = 2.f * Up / Gravity;
		P.Age = bInitial ? Rng.FRandRange(0.f, P.Life) : 0.f;
		const float H = Spread / Lifetime;
		const FVector Dir = Ring > 0.f ? Out : FVector(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), 0.0).GetSafeNormal();
		const FVector Across(-Dir.Y, Dir.X, 0.0);
		P.Velocity = Dir * (H * Rng.FRandRange(-0.3f, 1.f)) + Across * (H * Rng.FRandRange(-0.5f, 0.5f)) + FVector(0.0, 0.0, Up);
	}
	else
	{
		const FVector Drift(Rng.FRandRange(-1.f, 1.f), Rng.FRandRange(-1.f, 1.f), 0.0);
		P.Velocity = FVector(Drift.X * Spread / Lifetime, Drift.Y * Spread / Lifetime, Rise / Lifetime * Rng.FRandRange(0.7f, 1.2f));
	}
	P.Size0 = BaseSize * Rng.FRandRange(0.7f, 1.1f);
	P.Size1 = P.Size0 * (Kind == EDAEmitterKind::Sparks ? 0.3f : Kind == EDAEmitterKind::Spray ? 0.6f : Rng.FRandRange(2.4f, 3.6f));
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
			// droplets and fireflies are specks: nobody sees them past ~80 m (a jet's stream a little further)
			const float Range = Kind == EDAEmitterKind::Spray || Kind == EDAEmitterKind::Fireflies ? 8000.f
				: Kind == EDAEmitterKind::Jet ? 12000.f : 25000.f;
			bVisibleToPlayer = !Pawn || FVector::Dist(Pawn->GetActorLocation(), GetActorLocation()) < Range * FMath::Max(EffectScale, 1.f);
		}
	}
	if (!bVisibleToPlayer)
	{
		return;
	}
	if (Kind == EDAEmitterKind::Fireflies)
	{
		TickFireflies(DeltaSeconds);
		return;
	}

	Transforms.SetNum(Particles.Num(), EAllowShrinking::No);
	if (Kind == EDAEmitterKind::Jet)
	{
		// Real time, real gravity: Rate only sets how dense the stream is (BeginPlay).
		const float Dt = FMath::Min(DeltaSeconds, 0.1f);
		const FVector Down(0.0, 0.0, Gravity);
		const float FloorLocal = FloorZ - static_cast<float>(GetActorLocation().Z);
		for (int32 i = 0; i < Particles.Num(); ++i)
		{
			FPuff& P = Particles[i];
			if (P.bSplash && P.bIdle)
			{
				Transforms[i] = FTransform(FQuat::Identity, FVector(0.0, 0.0, FloorLocal), FVector(0.001));
				Puffs->SetCustomDataValue(i, 0, 0.f, false);
				continue;
			}
			P.Age += Dt;
			if (P.Age >= P.Life)
			{
				if (P.bSplash)
				{
					P.bIdle = true;
					Transforms[i] = FTransform(FQuat::Identity, FVector(0.0, 0.0, FloorLocal), FVector(0.001));
					Puffs->SetCustomDataValue(i, 0, 0.f, false);
					continue;
				}
				// The droplet reached the water: a splash hops up where it landed, the droplet starts over.
				FVector Landed = P.Start + P.Velocity * P.Life - Down * (0.5f * P.Life * P.Life);
				Landed.Z = FloorLocal + 1.0;
				TriggerSplash(Landed);
				RespawnJet(P, false);
			}
			const float T = P.Age / P.Life;
			const FVector Pos = P.Start + P.Velocity * P.Age - Down * (0.5f * P.Age * P.Age);
			const FVector Vel = P.Velocity - Down * P.Age;
			const float Size = FMath::Lerp(P.Size0, P.Size1, T);
			// Stream: solid from the nozzle on, thinning out just before it lands. Splash: fades as it hops.
			const float Opacity = P.bSplash ? MaxOpacity * 0.8f * (1.f - T)
				: MaxOpacity * FMath::Min(1.f, T * 20.f) * FMath::Min(1.f, (1.f - T) * 8.f + 0.35f);
			Transforms[i] = DropletTransform(Pos, Vel, Size, P.bSplash ? 0.002f : 0.004f);
			Puffs->SetCustomDataValue(i, 0, Opacity, false);
		}
		Puffs->BatchUpdateInstancesTransforms(0, Transforms, false, true, true);
		return;
	}

	// Wind: a slow lean so smoke plumes drift.
	const FVector Wind(160.0, 60.0, 0.0);
	for (int32 i = 0; i < Particles.Num(); ++i)
	{
		FPuff& P = Particles[i];
		P.Age += DeltaSeconds * Rate;
		if (P.Age >= P.Life)
		{
			Respawn(P, false);
		}
		const float T = P.Age / P.Life;
		const FVector Pos = P.Start + P.Velocity * P.Age + Wind * (Kind == EDAEmitterKind::Smoke ? T * T * EffectScale : 0.f)
			- FVector(0.0, 0.0, 0.5f * Gravity * P.Age * P.Age);
		const float Size = FMath::Lerp(P.Size0, P.Size1, FMath::Sqrt(T));
		const float Opacity = MaxOpacity * FMath::Pow(FMath::Sin(T * PI), 0.8f);
		if (Kind == EDAEmitterKind::Spray)
		{
			// droplets streak a little along their hop
			Transforms[i] = DropletTransform(Pos, P.Velocity - FVector(0.0, 0.0, Gravity * P.Age), Size, 0.002f);
		}
		else
		{
			Transforms[i] = FTransform(FQuat::Identity, Pos, FVector(Size));
		}
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
	RotationSpeed = FMath::IsFinite(RotationSpeed) ? RotationSpeed : 0.f;
	BeamLength = FMath::IsFinite(BeamLength) ? FMath::Max(BeamLength, 0.f) : 0.f;
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
	Night = FMath::IsFinite(Night) ? FMath::Clamp(Night, 0.f, 1.f) : 1.f;
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
	Radius = FMath::IsFinite(Radius) ? FMath::Max(Radius, 1.f) : 4000.f;
	Volume = FMath::IsFinite(Volume) ? FMath::Max(Volume, 0.f) : 1.f;
	Audio->SetSound(Sound);
	Audio->bAllowSpatialization = true;
	Audio->bOverrideAttenuation = true;
	Audio->AttenuationOverrides.bAttenuate = true;
	Audio->AttenuationOverrides.bSpatialize = true;
	Audio->AttenuationOverrides.AttenuationShape = EAttenuationShape::Sphere;
	Audio->AttenuationOverrides.AttenuationShapeExtents = FVector(Radius * 0.2f, 0.0, 0.0);
	Audio->AttenuationOverrides.FalloffDistance = Radius;
	Audio->SetVolumeMultiplier(Volume);
	// Randomising the start phase desynchronises nearby ambiences, but seeking
	// past the clip length can leave a short loop silent.
	const float Duration = Sound->GetDuration();
	const float MaxStart = Duration > 0.f ? FMath::Max(0.f, FMath::Min(5.f, Duration) - 0.01f) : 0.f;
	Audio->Play(FMath::FRandRange(0.f, MaxStart));
}

// ======================================================================== ADADoor

ADADoor::ADADoor()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	Root->SetMobility(EComponentMobility::Static);
	PivotA = CreateDefaultSubobject<USceneComponent>(TEXT("PivotA"));
	PivotA->SetupAttachment(Root);
	PivotB = CreateDefaultSubobject<USceneComponent>(TEXT("PivotB"));
	PivotB->SetupAttachment(Root);
	auto MakeLeaf = [this](const TCHAR* Name, USceneComponent* Parent)
	{
		UStaticMeshComponent* Leaf = CreateDefaultSubobject<UStaticMeshComponent>(Name);
		Leaf->SetupAttachment(Parent);
		Leaf->SetCollisionProfileName(UCollisionProfile::BlockAllDynamic_ProfileName);
		// never trap a pawn or yank the camera; the door opens before anyone reaches it anyway
		Leaf->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
		Leaf->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
		Leaf->SetCanEverAffectNavigation(false);
		return Leaf;
	};
	LeafA = MakeLeaf(TEXT("LeafA"), PivotA);
	LeafB = MakeLeaf(TEXT("LeafB"), PivotB);
	for (USceneComponent* C : { PivotA.Get(), PivotB.Get() })
	{
		C->SetMobility(EComponentMobility::Movable);
	}
	LeafA->SetMobility(EComponentMobility::Movable);
	LeafB->SetMobility(EComponentMobility::Movable);
}

void ADADoor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	RefreshDoor();
}

void ADADoor::RefreshDoor()
{
	LeafA->SetStaticMesh(LeafMesh);
	LeafB->SetStaticMesh(bDouble ? LeafMesh.Get() : nullptr);
	LeafB->SetVisibility(bDouble);
	LeafB->SetCollisionEnabled(bDouble ? ECollisionEnabled::QueryAndPhysics : ECollisionEnabled::NoCollision);
	ApplyPose();
}

void ADADoor::BeginPlay()
{
	Super::BeginPlay();
	RefreshDoor();
	CheckTimer = FMath::FRandRange(0.f, 0.15f);   // spread the checks of ~200 doors over frames
}

bool ADADoor::FindPawn(FVector& OutLocalPos) const
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return false;
	}
	const FVector Center = GetActorLocation() + FVector(0.0, 0.0, Height * 0.5);
	TArray<FOverlapResult> Hits;
	World->OverlapMultiByObjectType(Hits, Center, FQuat::Identity, FCollisionObjectQueryParams(ECC_Pawn),
		FCollisionShape::MakeSphere(TriggerRadius));
	double Best = TNumericLimits<double>::Max();
	bool bFound = false;
	for (const FOverlapResult& H : Hits)
	{
		const AActor* A = H.GetActor();
		if (!A || !A->IsA<APawn>())
		{
			continue;
		}
		const double D = FVector::DistSquared(A->GetActorLocation(), Center);
		if (D < Best)
		{
			Best = D;
			OutLocalPos = GetActorTransform().InverseTransformPosition(A->GetActorLocation());
			bFound = true;
		}
	}
	return bFound;
}

void ADADoor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	CheckTimer -= DeltaSeconds;
	if (CheckTimer <= 0.f)
	{
		CheckTimer = 0.15f;
		bool bCheck = Alpha > 0.f || Target > 0.f;
		if (!bCheck)
		{
			const APawn* Player = UGameplayStatics::GetPlayerPawn(this, 0);
			bCheck = !Player || FVector::DistSquared(Player->GetActorLocation(), GetActorLocation()) < FMath::Square(ActiveDistance);
		}
		if (bCheck)
		{
			FVector Local;
			const bool bPawn = FindPawn(Local);
			if (bPawn && Target <= 0.f && Alpha <= KINDA_SMALL_NUMBER)
			{
				// choose the side once per opening: away from the pawn, unless the doorway forces one
				Side = SwingSide != 0 ? float(FMath::Sign(SwingSide)) : (Local.Y >= 0.0 ? -1.f : 1.f);
			}
			Target = bPawn ? 1.f : 0.f;
		}
	}
	if (!FMath::IsNearlyEqual(Alpha, Target))
	{
		const float Step = DeltaSeconds / FMath::Max(OpenTime, 0.05f);
		Alpha = Target > Alpha ? FMath::Min(Alpha + Step, Target) : FMath::Max(Alpha - Step, Target);
		ApplyPose();
	}
}

void ADADoor::ApplyPose()
{
	const float LeafWidth = bDouble ? Width * 0.5f : Width;
	// ease in / out
	const float E = Alpha * Alpha * (3.f - 2.f * Alpha);
	if (Mode == EDADoorMode::Slide)
	{
		PivotA->SetRelativeLocationAndRotation(FVector(-Width * 0.5f - E * LeafWidth * 0.95f, 0.0, 0.0), FRotator::ZeroRotator);
		PivotB->SetRelativeLocationAndRotation(FVector(Width * 0.5f + E * LeafWidth * 0.95f, 0.0, 0.0), FRotator(0.f, 180.f, 0.f));
	}
	else
	{
		// FRotator yaw turns +X towards +Y: leaf A (towards +X) swings to +Y with a positive angle,
		// leaf B (turned 180 deg, towards -X) with a negative one
		const float Angle = E * OpenAngle * Side;
		PivotA->SetRelativeLocationAndRotation(FVector(-Width * 0.5f, 0.0, 0.0), FRotator(0.f, Angle, 0.f));
		PivotB->SetRelativeLocationAndRotation(FVector(Width * 0.5f, 0.0, 0.0), FRotator(0.f, 180.f - Angle, 0.f));
	}
}
