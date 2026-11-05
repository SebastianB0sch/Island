// Duel Academy Island - the student's all-terrain motorcycle.

#include "DAMotorcycleComponent.h"

#include "Components/SpotLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
	const TCHAR* BikeMasterMaterial = TEXT("/Game/DuelAcademy/Materials/M_DA_Master.M_DA_Master");
	const TCHAR* BikeEmissiveMaterial = TEXT("/Game/DuelAcademy/Materials/M_DA_Emissive.M_DA_Emissive");

	// Layout (cm, bike space: +X forward, +Z up, origin on the ground between the wheels).
	const float RearHubX = -70.f;
	const float FrontHubX = 72.f;
	const FVector SteeringHead(46.0, 0.0, 100.0);
	const FVector RiderSeat(-14.0, 0.0, 0.0);

	// Suspension spring (offset in cm, rider included).
	const float SpringStiffness = 260.f;
	const float SpringDamping = 20.f;
}

UDAMotorcycleComponent::UDAMotorcycleComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	SetCanEverAffectNavigation(false);

	// Constructor references keep the basic shapes in a cooked build.
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	CubeMesh = Cube.Succeeded() ? Cube.Object : nullptr;
	CylinderMesh = Cylinder.Succeeded() ? Cylinder.Object : nullptr;
	SphereMesh = Sphere.Succeeded() ? Sphere.Object : nullptr;
}

void UDAMotorcycleComponent::BeginPlay()
{
	Super::BeginPlay();
	Build();
	SetDeployed(bDeployed);
}

// ------------------------------------------------------------------------ construction

USceneComponent* UDAMotorcycleComponent::AddPivot(USceneComponent* Parent, const FVector& Location)
{
	USceneComponent* C = NewObject<USceneComponent>(GetOwner(), NAME_None, RF_Transient);
	C->SetupAttachment(Parent);
	C->SetRelativeLocation(Location);
	C->RegisterComponent();
	return C;
}

UStaticMeshComponent* UDAMotorcycleComponent::AddPart(UStaticMesh* Mesh, USceneComponent* Parent, const FVector& Location,
	const FRotator& Rotation, const FVector& Scale, UMaterialInterface* Material)
{
	UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(GetOwner(), NAME_None, RF_Transient);
	C->SetupAttachment(Parent);
	C->SetRelativeTransform(FTransform(Rotation, Location, Scale));
	C->SetMobility(EComponentMobility::Movable);
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	C->SetGenerateOverlapEvents(false);
	C->SetCanEverAffectNavigation(false);
	C->CastShadow = true;
	C->bCastDynamicShadow = true;
	if (Mesh)
	{
		C->SetStaticMesh(Mesh);
	}
	if (Material)
	{
		C->SetMaterial(0, Material);
	}
	C->RegisterComponent();
	return C;
}

UStaticMeshComponent* UDAMotorcycleComponent::AddRod(USceneComponent* Parent, const FVector& A, const FVector& B,
	float Diameter, UMaterialInterface* Material)
{
	const FVector Axis = B - A;
	const float Length = static_cast<float>(Axis.Size());
	const FRotator Rot = Length > KINDA_SMALL_NUMBER ? FRotationMatrix::MakeFromZ(Axis).Rotator() : FRotator::ZeroRotator;
	// The engine cylinder is 100 cm tall and 100 cm across, centred, along +Z.
	return AddPart(CylinderMesh, Parent, (A + B) * 0.5, Rot, FVector(Diameter / 100.f, Diameter / 100.f, Length / 100.f), Material);
}

UMaterialInstanceDynamic* UDAMotorcycleComponent::MakeMaterial(UMaterialInterface* Base, const FLinearColor& Tint,
	float Roughness, float Metallic, float EmissiveStrength)
{
	if (!Base)
	{
		return nullptr;
	}
	UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(Base, GetOwner());
	MID->SetVectorParameterValue(TEXT("Tint"), Tint);
	MID->SetScalarParameterValue(TEXT("Roughness"), Roughness);
	MID->SetScalarParameterValue(TEXT("Metallic"), Metallic);
	MID->SetScalarParameterValue(TEXT("DetailStrength"), 0.15f);
	if (EmissiveStrength >= 0.f)
	{
		MID->SetScalarParameterValue(TEXT("Strength"), EmissiveStrength);
	}
	return MID;
}

USceneComponent* UDAMotorcycleComponent::BuildWheel(USceneComponent* Parent, const FVector& Hub,
	UMaterialInterface* Rubber, UMaterialInterface* Rim, UMaterialInterface* Dark)
{
	const float R = WheelRadius;
	USceneComponent* Wheel = AddPivot(Parent, Hub);
	// Roll 90 turns the cylinder's +Z onto the axle (+Y).
	const FRotator Axle(0.f, 0.f, 90.f);
	AddPart(CylinderMesh, Wheel, FVector::ZeroVector, Axle, FVector(2.f * R / 100.f, 2.f * R / 100.f, 0.20f), Rubber);
	AddPart(CylinderMesh, Wheel, FVector::ZeroVector, Axle, FVector(1.25f * R / 100.f, 1.25f * R / 100.f, 0.215f), Rim);
	AddPart(CylinderMesh, Wheel, FVector::ZeroVector, Axle, FVector(0.16f, 0.16f, 0.30f), Dark);
	// Spokes: wider than the rim so they show on both faces and make the spin readable.
	for (int32 i = 0; i < 3; ++i)
	{
		AddPart(CubeMesh, Wheel, FVector::ZeroVector, FRotator(60.f * i, 0.f, 0.f),
			FVector(1.2f * R / 100.f, 0.225f, 0.025f), Dark);
	}
	// Knobby tread: blocks around the tyre, each pointing out radially.
	const int32 Knobs = 14;
	for (int32 i = 0; i < Knobs; ++i)
	{
		const float A = 360.f * i / Knobs;
		const float Rad = FMath::DegreesToRadians(A);
		const FVector Pos(R * FMath::Cos(Rad), (i % 2 == 0) ? 3.0 : -3.0, R * FMath::Sin(Rad));
		AddPart(CubeMesh, Wheel, Pos, FRotator(A - 90.f, 0.f, 0.f), FVector(0.07f, 0.15f, 0.05f), Rubber);
	}
	return Wheel;
}

void UDAMotorcycleComponent::Build()
{
	if (bBuilt || !GetOwner())
	{
		return;
	}
	bBuilt = true;

	UMaterialInterface* Master = LoadObject<UMaterialInterface>(nullptr, BikeMasterMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);
	UMaterialInterface* Emissive = LoadObject<UMaterialInterface>(nullptr, BikeEmissiveMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);
	PaintMaterial = MakeMaterial(Master, Paint, 0.35f, 0.2f);
	UMaterialInstanceDynamic* White = MakeMaterial(Master, FLinearColor(0.82f, 0.82f, 0.8f), 0.45f, 0.f);
	UMaterialInstanceDynamic* Dark = MakeMaterial(Master, FLinearColor(0.035f, 0.035f, 0.04f), 0.55f, 0.5f);
	UMaterialInstanceDynamic* Metal = MakeMaterial(Master, FLinearColor(0.6f, 0.6f, 0.63f), 0.25f, 1.f);
	UMaterialInstanceDynamic* Seat = MakeMaterial(Master, FLinearColor(0.02f, 0.02f, 0.02f), 0.85f, 0.f);
	UMaterialInstanceDynamic* Gold = MakeMaterial(Master, FLinearColor(0.85f, 0.6f, 0.15f), 0.3f, 1.f);
	UMaterialInstanceDynamic* Lamp = MakeMaterial(Emissive, FLinearColor(1.f, 0.95f, 0.8f), 0.4f, 0.f, 4.f);
	UMaterialInstanceDynamic* Tail = MakeMaterial(Emissive, FLinearColor(1.f, 0.05f, 0.03f), 0.4f, 0.f, 3.f);

	Tilt = AddPivot(this, FVector::ZeroVector);
	Body = AddPivot(Tilt, FVector::ZeroVector);
	RiderMount = AddPivot(Tilt, RiderSeat);

	const float R = WheelRadius;

	// ---- rear: wheel, swingarm, shock
	UMaterialInstanceDynamic* Rubber = MakeMaterial(Master, FLinearColor(0.018f, 0.018f, 0.02f), 0.95f, 0.f);
	RearWheel = BuildWheel(Body, FVector(RearHubX, 0.0, R), Rubber, Metal, Dark);
	for (const float Side : { -9.f, 9.f })
	{
		AddRod(Body, FVector(-12.0, Side, 42.0), FVector(RearHubX, Side, R), 6.f, Metal);
	}
	AddRod(Body, FVector(-22.0, 0.0, 86.0), FVector(-36.0, 0.0, 46.0), 9.f, Gold);
	AddRod(Body, FVector(-22.0, 0.0, 86.0), FVector(-36.0, 0.0, 46.0), 4.f, Metal);

	// ---- frame, engine, exhaust
	AddRod(Body, SteeringHead, FVector(14.0, 0.0, 44.0), 7.f, Dark);                   // down tube
	AddRod(Body, SteeringHead, FVector(-24.0, 0.0, 86.0), 6.f, Dark);                  // spar
	AddRod(Body, FVector(-24.0, 0.0, 86.0), FVector(-14.0, 0.0, 38.0), 6.f, Dark);     // rear frame
	AddRod(Body, FVector(-24.0, 0.0, 86.0), FVector(-78.0, 0.0, 92.0), 4.f, Dark);     // subframe
	AddPart(CubeMesh, Body, FVector(0.0, 0.0, 48.0), FRotator::ZeroRotator, FVector(0.40f, 0.22f, 0.30f), Dark);
	AddRod(Body, FVector(6.0, 0.0, 58.0), FVector(20.0, 0.0, 84.0), 17.f, Metal);      // cylinder
	AddPart(CylinderMesh, Body, FVector(-4.0, 12.0, 46.0), FRotator(0.f, 0.f, 90.f), FVector(0.22f, 0.22f, 0.04f), Metal);
	for (const float Side : { -1.f, 1.f })
	{
		AddRod(Body, FVector(-6.0, 10.0 * Side, 40.0), FVector(-6.0, 22.0 * Side, 40.0), 3.f, Metal);   // foot pegs
	}
	AddRod(Body, FVector(16.0, 9.0, 66.0), FVector(-8.0, 16.0, 60.0), 6.f, Metal);     // header
	AddRod(Body, FVector(-8.0, 16.0, 60.0), FVector(-40.0, 17.0, 80.0), 7.f, Metal);
	AddRod(Body, FVector(-38.0, 17.0, 79.0), FVector(-80.0, 17.0, 93.0), 13.f, Dark);  // silencer
	AddRod(Body, FVector(-80.0, 17.0, 93.0), FVector(-85.0, 17.0, 95.0), 8.f, Metal);

	// ---- bodywork: tank, shrouds, seat, side panels, rear fender, tail light
	AddPart(SphereMesh, Body, FVector(18.0, 0.0, 90.0), FRotator(-6.f, 0.f, 0.f), FVector(0.48f, 0.30f, 0.22f), PaintMaterial);
	for (const float Side : { -1.f, 1.f })
	{
		AddPart(CubeMesh, Body, FVector(28.0, 13.0 * Side, 78.0), FRotator(22.f, 0.f, 0.f), FVector(0.30f, 0.03f, 0.22f), PaintMaterial);
		AddPart(CubeMesh, Body, FVector(-32.0, 11.0 * Side, 80.0), FRotator::ZeroRotator, FVector(0.30f, 0.03f, 0.16f), White);
	}
	AddPart(CubeMesh, Body, FVector(-16.0, 0.0, 94.0), FRotator(-3.f, 0.f, 0.f), FVector(0.72f, 0.22f, 0.08f), Seat);
	AddPart(CubeMesh, Body, FVector(-58.0, 0.0, 95.0), FRotator(-12.f, 0.f, 0.f), FVector(0.58f, 0.20f, 0.035f), PaintMaterial);
	AddPart(CubeMesh, Body, FVector(-85.0, 0.0, 100.0), FRotator(-12.f, 0.f, 0.f), FVector(0.03f, 0.10f, 0.04f), Tail);

	// ---- steering front end: fork, front wheel, fender, bars, number plate, headlight
	FrontPivot = AddPivot(Body, SteeringHead);
	const FVector FrontHub(FrontHubX - SteeringHead.X, 0.0, R - SteeringHead.Z);
	FrontWheel = BuildWheel(FrontPivot, FrontHub, Rubber, Metal, Dark);
	for (const float Side : { -10.f, 10.f })
	{
		const FVector Top(-2.0, Side, 8.0);
		const FVector Hub(FrontHub.X, Side, FrontHub.Z);
		const FVector Mid = FMath::Lerp(Top, Hub, 0.45);
		AddRod(FrontPivot, Top, Mid, 8.f, Dark);
		AddRod(FrontPivot, Mid, Hub, 6.f, Gold);
	}
	AddPart(CubeMesh, FrontPivot, FVector(0.0, 0.0, 4.0), FRotator::ZeroRotator, FVector(0.10f, 0.28f, 0.06f), Dark);
	AddRod(FrontPivot, FVector(-2.0, 0.0, 6.0), FVector(-6.0, 0.0, 16.0), 4.f, Dark);
	AddRod(FrontPivot, FVector(-6.0, -38.0, 16.0), FVector(-6.0, 38.0, 16.0), 3.5f, Metal);
	for (const float Side : { -1.f, 1.f })
	{
		AddRod(FrontPivot, FVector(-6.0, 29.0 * Side, 16.0), FVector(-6.0, 40.0 * Side, 16.0), 4.5f, Seat);
	}
	AddPart(CubeMesh, FrontPivot, FVector(FrontHub.X + 4.0, 0.0, FrontHub.Z + R + 7.0), FRotator(-8.f, 0.f, 0.f),
		FVector(0.50f, 0.16f, 0.03f), PaintMaterial);
	AddPart(CubeMesh, FrontPivot, FVector(10.0, 0.0, -8.0), FRotator(20.f, 0.f, 0.f), FVector(0.04f, 0.26f, 0.24f), White);
	AddPart(SphereMesh, FrontPivot, FVector(13.0, 0.0, -9.0), FRotator::ZeroRotator, FVector(0.07f, 0.12f, 0.09f), Lamp);

	Headlight = NewObject<USpotLightComponent>(GetOwner(), NAME_None, RF_Transient);
	Headlight->SetupAttachment(FrontPivot);
	Headlight->SetRelativeLocationAndRotation(FVector(17.0, 0.0, -9.0), FRotator(-7.f, 0.f, 0.f));
	Headlight->SetIntensityUnits(ELightUnits::Unitless);
	Headlight->SetIntensity(0.f);
	Headlight->SetInnerConeAngle(16.f);
	Headlight->SetOuterConeAngle(32.f);
	Headlight->SetAttenuationRadius(4500.f);
	Headlight->SetLightColor(FLinearColor(1.f, 0.94f, 0.82f));
	Headlight->SetCastShadows(false);
	Headlight->RegisterComponent();
}

// ------------------------------------------------------------------------ runtime

void UDAMotorcycleComponent::SetPaint(const FLinearColor& Color)
{
	Paint = Color;
	if (PaintMaterial)
	{
		PaintMaterial->SetVectorParameterValue(TEXT("Tint"), Paint);
	}
}

void UDAMotorcycleComponent::SetDeployed(bool bOn)
{
	const bool bWasDeployed = bDeployed;
	bDeployed = bOn;
	if (!Tilt)
	{
		return;   // not built yet; BeginPlay applies the state
	}
	Tilt->SetVisibility(bOn, true);
	if (bOn && !bWasDeployed)
	{
		DeployAlpha = 0.f;
		SuspensionOffset = -6.f;   // settles onto its springs as it appears
		SuspensionVelocity = 0.f;
		bWasAirborne = false;
		Body->SetRelativeScale3D(FVector(0.01));
	}
	if (!bOn && Headlight)
	{
		Headlight->SetIntensity(0.f);
	}
}

void UDAMotorcycleComponent::UpdateRide(float DeltaTime, const FDABikePose& Pose)
{
	if (!bDeployed || !Tilt || DeltaTime <= 0.f)
	{
		return;
	}
	Time += DeltaTime;

	// Pop-in: a short overshooting scale so summoning the bike reads as an event.
	if (DeployAlpha < 1.f)
	{
		DeployAlpha = FMath::Min(1.f, DeployAlpha + DeltaTime / 0.28f);
		const float T = DeployAlpha;
		const float Back = 1.f + 2.70158f * FMath::Pow(T - 1.f, 3.f) + 1.70158f * FMath::Pow(T - 1.f, 2.f);
		Body->SetRelativeScale3D(FVector(FMath::Max(0.01f, Back)));
	}

	// Wheels: rolling without slipping (a positive angle about +Y rolls the wheel forwards).
	WheelAngle = FMath::Fmod(WheelAngle + Pose.ForwardSpeed / FMath::Max(WheelRadius, 1.f) * DeltaTime, 2.f * PI);
	const FQuat Spin(FVector::YAxisVector, WheelAngle);
	RearWheel->SetRelativeRotation(Spin);
	FrontWheel->SetRelativeRotation(Spin);
	FrontPivot->SetRelativeRotation(FRotator(0.f, FMath::Clamp(Pose.Steer, -1.f, 1.f) * MaxSteerAngle, 0.f));

	// Suspension: a damped spring that compresses on landing and chatters a little over rough ground.
	if (bWasAirborne && !Pose.bAirborne)
	{
		SuspensionVelocity -= 160.f;
	}
	bWasAirborne = Pose.bAirborne;
	const float Speed01 = FMath::Clamp(FMath::Abs(Pose.ForwardSpeed) / 1500.f, 0.f, 1.f);
	const float Chatter = Pose.bAirborne ? 0.f : 0.8f * Speed01 * (FMath::Sin(Time * 23.f) + 0.6f * FMath::Sin(Time * 37.f + 1.3f));
	const float Accel = -SpringStiffness * (SuspensionOffset - Chatter) - SpringDamping * SuspensionVelocity;
	SuspensionVelocity += Accel * DeltaTime;
	SuspensionOffset = FMath::Clamp(SuspensionOffset + SuspensionVelocity * DeltaTime, -14.f, 8.f);

	// Lean about the tyre contact line, pitch about the point between the wheels.
	Tilt->SetRelativeLocationAndRotation(FVector(0.0, 0.0, SuspensionOffset),
		FRotator(FMath::Clamp(Pose.Pitch, -40.f, 40.f), 0.f, FMath::Clamp(Pose.Lean, -45.f, 45.f)));

	// Headlight: on at dusk and at night.
	NightAlphaSmoothed = FMath::FInterpTo(NightAlphaSmoothed, FMath::Clamp(Pose.NightAlpha, 0.f, 1.f), DeltaTime, 1.5f);
	if (Headlight)
	{
		Headlight->SetIntensity(18000.f * NightAlphaSmoothed);
	}
}
