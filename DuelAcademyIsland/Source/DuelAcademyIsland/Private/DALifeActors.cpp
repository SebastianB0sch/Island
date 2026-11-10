// Duel Academy Island - turning meshes and procedural bird flocks.

#include "DALifeActors.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	/** The palette master (Tint / Roughness / Metallic); it is flagged for instanced static meshes. */
	const TCHAR* LifeMasterMaterial = TEXT("/Game/DuelAcademy/Materials/M_DA_Master.M_DA_Master");

	/** Distance (cm) from the first player's pawn to a point; 0 (= "near") while there is no pawn yet. */
	double PlayerDistance(const UWorld* World, const FVector& Point)
	{
		const APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
		const APawn* Pawn = PC ? PC->GetPawn() : nullptr;
		return Pawn ? FVector::Dist(Pawn->GetActorLocation(), Point) : 0.0;
	}
}

// ======================================================================== ADASpinner

ADASpinner::ADASpinner()
{
	PrimaryActorTick.bCanEverTick = true;
	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;
	Root->SetMobility(EComponentMobility::Static);
	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	Mesh->SetupAttachment(Root);
	Mesh->SetMobility(EComponentMobility::Movable);
	Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Mesh->SetCanEverAffectNavigation(false);
}

void ADASpinner::BeginPlay()
{
	Super::BeginPlay();
	Rpm = FMath::IsFinite(Rpm) ? FMath::Clamp(Rpm, -600.f, 600.f) : 0.f;
	if (Axis.ContainsNaN() || Axis.IsNearlyZero())
	{
		Axis = FVector(0.0, 1.0, 0.0);
	}
	Axis = Axis.GetSafeNormal();
	ActiveDistance = FMath::IsFinite(ActiveDistance) ? FMath::Max(ActiveDistance, 0.f) : 30000.f;
	CheckTimer = FMath::FRandRange(0.f, 0.5f);
	// Wheels do not all start at the same spoke.
	Mesh->AddLocalRotation(FQuat(Axis, FMath::FRandRange(0.f, 2.f * PI)));
}

void ADASpinner::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	CheckTimer -= DeltaSeconds;
	if (CheckTimer <= 0.f)
	{
		CheckTimer = 0.5f;
		bActive = ActiveDistance <= 0.f || PlayerDistance(GetWorld(), GetActorLocation()) < ActiveDistance;
	}
	if (!bActive || Rpm == 0.f)
	{
		return;
	}
	const float Angle = Rpm / 60.f * 2.f * PI * FMath::Min(DeltaSeconds, 0.1f);
	Mesh->AddLocalRotation(FQuat(Axis, Angle));
}

// ======================================================================== ADABirdFlock

ADABirdFlock::ADABirdFlock()
{
	PrimaryActorTick.bCanEverTick = true;
	USceneComponent* SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = SceneRoot;
	static ConstructorHelpers::FObjectFinder<UStaticMesh> SphereMesh(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(TEXT("/Engine/BasicShapes/Cube.Cube"));
	auto Make = [this, SceneRoot](const TCHAR* Name, UStaticMesh* ShapeMesh)
	{
		UInstancedStaticMeshComponent* C = CreateDefaultSubobject<UInstancedStaticMeshComponent>(Name);
		C->SetupAttachment(SceneRoot);
		C->SetMobility(EComponentMobility::Movable);
		C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		C->SetCastShadow(false);
		C->SetCanEverAffectNavigation(false);
		if (ShapeMesh)
		{
			C->SetStaticMesh(ShapeMesh);
		}
		return C;
	};
	Bodies = Make(TEXT("Bodies"), SphereMesh.Succeeded() ? SphereMesh.Object : nullptr);
	Wings = Make(TEXT("Wings"), CubeMesh.Succeeded() ? CubeMesh.Object : nullptr);
}

void ADABirdFlock::BeginPlay()
{
	Super::BeginPlay();
	Count = FMath::Clamp(Count, 1, 64);
	Radius = FMath::IsFinite(Radius) ? FMath::Max(Radius, 300.f) : 6000.f;
	Height = FMath::IsFinite(Height) ? FMath::Max(Height, 100.f) : 2500.f;
	ActiveDistance = FMath::IsFinite(ActiveDistance) ? FMath::Max(ActiveDistance, 1000.f) : 45000.f;

	FLinearColor BodyColor(0.93f, 0.93f, 0.9f);
	FLinearColor WingColor(0.78f, 0.79f, 0.8f);
	float FlightSpeed = 900.f;
	if (Kind == EDABirdKind::Songbird)
	{
		BodyLength = 14.f; WingSpan = 13.f; FlapRate = 9.f; GlideShare = 0.15f; FlightSpeed = 700.f;
		BodyColor = FLinearColor(0.2f, 0.13f, 0.08f);
		WingColor = FLinearColor(0.13f, 0.09f, 0.06f);
	}
	else
	{
		BodyLength = 45.f; WingSpan = 58.f; FlapRate = 2.6f; GlideShare = 0.65f; FlightSpeed = 900.f;
	}
	if (FMath::IsFinite(Speed) && Speed > 0.f)
	{
		FlightSpeed = Speed;
	}

	if (UMaterialInterface* Master = LoadObject<UMaterialInterface>(nullptr, LifeMasterMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet))
	{
		auto Paint = [this, Master](UInstancedStaticMeshComponent* C, const FLinearColor& Tint)
		{
			UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(Master, this);
			MID->SetVectorParameterValue(TEXT("Tint"), Tint);
			MID->SetScalarParameterValue(TEXT("Roughness"), 0.85f);
			MID->SetScalarParameterValue(TEXT("DetailStrength"), 0.f);
			C->SetMaterial(0, MID);
		};
		Paint(Bodies, BodyColor);
		Paint(Wings, WingColor);
	}

	FRandomStream Rng(static_cast<int32>(GetUniqueID() * 131u + 17u));
	Birds.SetNum(Count);
	Bodies->ClearInstances();
	Wings->ClearInstances();
	for (FBird& B : Birds)
	{
		// Every bird flies its own loop somewhere inside the cylinder; the loops overlap into a loose flock.
		B.Loop = Radius * Rng.FRandRange(0.25f, 0.6f);
		const float A = Rng.FRandRange(0.f, 2.f * PI);
		const float R = (Radius - B.Loop) * FMath::Sqrt(Rng.FRand());
		B.Home = FVector(FMath::Cos(A) * R, FMath::Sin(A) * R, Height * Rng.FRandRange(0.25f, 0.8f));
		B.Angle = Rng.FRandRange(0.f, 2.f * PI);
		B.Turn = Rng.FRand() < 0.5f ? -1.f : 1.f;
		B.AngularSpeed = FlightSpeed * Rng.FRandRange(0.8f, 1.2f) / FMath::Max(B.Loop, 100.f);
		B.Seed = Rng.FRandRange(0.f, 100.f);
		B.FlapPhase = Rng.FRandRange(0.f, 2.f * PI);
		B.Scale = Rng.FRandRange(0.85f, 1.15f);
		Bodies->AddInstance(FTransform(FQuat::Identity, B.Home, FVector(0.01)), false);
		Wings->AddInstance(FTransform(FQuat::Identity, B.Home, FVector(0.01)), false);
		Wings->AddInstance(FTransform(FQuat::Identity, B.Home, FVector(0.01)), false);
	}
	BodyTransforms.SetNum(Count);
	WingTransforms.SetNum(Count * 2);
	CheckTimer = FMath::FRandRange(0.f, 0.5f);
}

void ADABirdFlock::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	CheckTimer -= DeltaSeconds;
	if (CheckTimer <= 0.f)
	{
		CheckTimer = 0.5f;
		const bool bNear = PlayerDistance(GetWorld(), GetActorLocation()) < ActiveDistance + Radius;
		if (bNear != bAwake)
		{
			bAwake = bNear;
			Bodies->SetVisibility(bAwake);
			Wings->SetVisibility(bAwake);
		}
	}
	if (!bAwake || Birds.Num() == 0)
	{
		return;
	}
	Time += FMath::Min(DeltaSeconds, 0.1f);

	// Engine shapes are 100 cm across: scales below are size / 100.
	const float BodyScale = BodyLength / 100.f;
	const float WingLength = WingSpan / 100.f;
	for (int32 i = 0; i < Birds.Num(); ++i)
	{
		FBird& B = Birds[i];
		B.Angle += B.Turn * B.AngularSpeed * FMath::Min(DeltaSeconds, 0.1f);
		// A wobbling circle: the radius breathes and the bird climbs and sinks slowly.
		const float Wobble = 1.f + 0.22f * FMath::Sin(B.Angle * 0.37f + B.Seed);
		const float Rad = B.Loop * Wobble;
		const float Climb = Height * 0.12f * FMath::Sin(Time * 0.17f + B.Seed * 1.9f);
		const FVector Pos = B.Home + FVector(FMath::Cos(B.Angle) * Rad, FMath::Sin(B.Angle) * Rad, Climb);
		// Heading = the tangent of the loop; bank into the turn like a gliding bird.
		const float Yaw = FMath::RadiansToDegrees(B.Angle) + 90.f * B.Turn;
		// FRotator roll > 0 dips the right wing: a left (counter-clockwise, Turn = +1) turn banks left.
		const float Bank = -22.f * B.Turn;
		const FQuat Body = FRotator(0.f, Yaw, Bank).Quaternion();

		// Wing beat: a few beats, then a glide with the wings held slightly up (gulls glide most of the time).
		const float Cycle = FMath::Frac(Time * 0.11f + B.Seed * 0.31f);
		const float Beating = Cycle > GlideShare ? 1.f : 0.f;
		const float Beat = FMath::Sin(Time * FlapRate * 2.f * PI + B.FlapPhase);
		const float WingAngle = Beating > 0.f ? 38.f * Beat : 8.f + 3.f * FMath::Sin(Time * 0.9f + B.Seed);

		const float S = B.Scale;
		BodyTransforms[i] = FTransform(Body, Pos, FVector(BodyScale * S, BodyScale * 0.3f * S, BodyScale * 0.26f * S));
		for (int32 Side = 0; Side < 2; ++Side)
		{
			// A wing is a flat box hinged at the shoulder: raise it about the bird's forward axis (roll), then
			// move its centre half a wing out along its own span. FRotator roll > 0 dips +Y, so the right wing
			// (+Y) rises with a negative roll and the left wing (-Y) with a positive one.
			const float Sign = Side == 0 ? 1.f : -1.f;
			const FQuat Wing = Body * FRotator(0.f, 0.f, -Sign * WingAngle).Quaternion();
			const FVector Shoulder = Pos + Body.RotateVector(FVector(BodyLength * 0.08f * S, 0.0, BodyLength * 0.06f * S));
			const FVector Centre = Shoulder + Wing.RotateVector(FVector(0.0, Sign * WingSpan * 0.5f * S, 0.0));
			WingTransforms[i * 2 + Side] = FTransform(Wing, Centre,
				FVector(BodyScale * 0.42f * S, WingLength * S, 0.012f * S));
		}
	}
	Bodies->BatchUpdateInstancesTransforms(0, BodyTransforms, false, true, true);
	Wings->BatchUpdateInstancesTransforms(0, WingTransforms, false, true, true);
}
