// Duel Academy Island - the student's all-terrain motorcycle.

#include "DAMotorcycleComponent.h"

#include "Components/InstancedStaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DAEngineSynthComponent.h"
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
	const float FrontHubX = 78.f;
	const FVector SteeringHead(46.0, 0.0, 100.0);
	const FVector RiderSeat(-14.0, 0.0, 0.0);

	// Suspension spring (offset in cm, rider included).
	const float SpringStiffness = 260.f;
	const float SpringDamping = 20.f;

	// 5-speed dirt-bike box.
	const float GearRatios[5] = { 2.55f, 1.85f, 1.42f, 1.15f, 0.94f };
	const float PrimaryDrive = 3.15f;
	const float FinalDrive = 3.40f;
	const float AudioTopSpeed = 2200.f;

	// Geometry of the tyre/rim ring built from instanced boxes.
	const int32 TyreSegments = 24;
	const int32 RimSegments = 22;
	const int32 TyreKnobs = 16;
	const int32 WheelSpokesPerSide = 8;
}

UDAMotorcycleComponent::UDAMotorcycleComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
	SetCanEverAffectNavigation(false);

	// Constructor references keep the basic shapes in a cooked build.
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cone(TEXT("/Engine/BasicShapes/Cone.Cone"));
	CubeMesh = Cube.Succeeded() ? Cube.Object : nullptr;
	CylinderMesh = Cylinder.Succeeded() ? Cylinder.Object : nullptr;
	SphereMesh = Sphere.Succeeded() ? Sphere.Object : nullptr;
	ConeMesh = Cone.Succeeded() ? Cone.Object : nullptr;
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

UInstancedStaticMeshComponent* UDAMotorcycleComponent::AddInstances(UStaticMesh* Mesh, USceneComponent* Parent,
	const TArray<FTransform>& Transforms, UMaterialInterface* Material)
{
	UInstancedStaticMeshComponent* C = NewObject<UInstancedStaticMeshComponent>(GetOwner(), NAME_None, RF_Transient);
	C->SetupAttachment(Parent);
	C->SetMobility(EComponentMobility::Movable);
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	C->SetGenerateOverlapEvents(false);
	C->SetCanEverAffectNavigation(false);
	C->SetCastShadow(true);
	if (Mesh)
	{
		C->SetStaticMesh(Mesh);
	}
	if (Material)
	{
		C->SetMaterial(0, Material);
	}
	C->RegisterComponent();
	for (const FTransform& T : Transforms)
	{
		C->AddInstance(T, false);
	}
	return C;
}

FTransform UDAMotorcycleComponent::MakeRodTransform(const FVector& A, const FVector& B, float Diameter) const
{
	const FVector Axis = B - A;
	const float Length = static_cast<float>(Axis.Size());
	const FRotator Rot = Length > KINDA_SMALL_NUMBER ? FRotationMatrix::MakeFromZ(Axis).Rotator() : FRotator::ZeroRotator;
	// The engine cylinder is 100 cm tall and 100 cm across, centred, along +Z.
	return FTransform(Rot, (A + B) * 0.5, FVector(Diameter / 100.f, Diameter / 100.f, Length / 100.f));
}

UStaticMeshComponent* UDAMotorcycleComponent::AddRod(USceneComponent* Parent, const FVector& A, const FVector& B,
	float Diameter, UMaterialInterface* Material)
{
	const FTransform T = MakeRodTransform(A, B, Diameter);
	return AddPart(CylinderMesh, Parent, T.GetLocation(), T.Rotator(), T.GetScale3D(), Material);
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

USceneComponent* UDAMotorcycleComponent::BuildWheel(USceneComponent* Parent, const FVector& Hub, bool bRear,
	UMaterialInterface* Rubber, UMaterialInterface* Rim, UMaterialInterface* Dark,
	UMaterialInterface* Metal, UMaterialInterface* Gold)
{
	const float R = WheelRadius;
	const float RimR = 0.70f * R;
	const float TyreThickness = R - RimR;
	const float TyreMidR = (R + RimR) * 0.5f;
	const float Width = (bRear ? 0.17f : 0.145f);
	const float WidthCm = Width * 100.f;
	const FRotator Axle(0.f, 0.f, 90.f);

	USceneComponent* Wheel = AddPivot(Parent, Hub);

	// Tyre as a ring of tread segments: unlike a solid cylinder this leaves the
	// hub and spokes visible through the wheel, like a real spoked dirt-bike wheel.
	{
		TArray<FTransform> TyreRing;
		TyreRing.Reserve(TyreSegments);
		const float SegmentLength = 2.f * PI * TyreMidR / TyreSegments * 1.04f;
		for (int32 i = 0; i < TyreSegments; ++i)
		{
			const float A = 360.f * i / TyreSegments;
			const float Rad = FMath::DegreesToRadians(A);
			const FVector Pos(TyreMidR * FMath::Cos(Rad), 0.0f, TyreMidR * FMath::Sin(Rad));
			TyreRing.Add(FTransform(FRotator(A + 90.f, 0.f, 0.f), Pos,
				FVector(SegmentLength / 100.f, Width, TyreThickness / 100.f)));
		}
		AddInstances(CubeMesh, Wheel, TyreRing, Rubber);
	}

	// Knobby tread blocks, alternating left/right like a real enduro tyre.
	{
		TArray<FTransform> Knobs;
		Knobs.Reserve(TyreKnobs);
		for (int32 i = 0; i < TyreKnobs; ++i)
		{
			const float A = 360.f * i / TyreKnobs;
			const float Rad = FMath::DegreesToRadians(A);
			const float Side = (i % 2 == 0) ? 1.f : -1.f;
			const FVector Pos((R + 1.2f) * FMath::Cos(Rad), Side * WidthCm * 0.24f, (R + 1.2f) * FMath::Sin(Rad));
			Knobs.Add(FTransform(FRotator(A + 90.f, 0.f, 0.f), Pos, FVector(0.075f, 0.16f, 0.045f)));
		}
		AddInstances(CubeMesh, Wheel, Knobs, Rubber);
	}

	// Metal rim ring.
	{
		TArray<FTransform> RimRing;
		RimRing.Reserve(RimSegments);
		const float SegmentLength = 2.f * PI * RimR / RimSegments * 1.10f;
		for (int32 i = 0; i < RimSegments; ++i)
		{
			const float A = 360.f * i / RimSegments;
			const float Rad = FMath::DegreesToRadians(A);
			const FVector Pos(RimR * FMath::Cos(Rad), 0.0f, RimR * FMath::Sin(Rad));
			RimRing.Add(FTransform(FRotator(A + 90.f, 0.f, 0.f), Pos,
				FVector(SegmentLength / 100.f, 0.055f, 0.024f)));
		}
		AddInstances(CubeMesh, Wheel, RimRing, Rim);
	}

	// Cross-laced spokes, both sides.
	{
		TArray<FTransform> Spokes;
		Spokes.Reserve(2 * WheelSpokesPerSide);
		for (int32 SideIndex = 0; SideIndex < 2; ++SideIndex)
		{
			const float Side = (SideIndex == 0) ? -1.f : 1.f;
			const float SideY = Side * WidthCm * 0.28f;
			for (int32 i = 0; i < WheelSpokesPerSide; ++i)
			{
				const float A = 360.f * i / WheelSpokesPerSide + (Side > 0.f ? 0.f : 180.f / WheelSpokesPerSide);
				const float Rad = FMath::DegreesToRadians(A);
				const FVector A0(FMath::Cos(Rad) * 3.0f, SideY * 0.35f, FMath::Sin(Rad) * 3.0f);
				const FVector B0(FMath::Cos(Rad) * RimR * 0.96f, SideY, FMath::Sin(Rad) * RimR * 0.96f);
				Spokes.Add(MakeRodTransform(A0, B0, 0.55f));
			}
		}
		AddInstances(CylinderMesh, Wheel, Spokes, Metal);
	}

	// Hub, flanges and axle.
	AddPart(CylinderMesh, Wheel, FVector::ZeroVector, Axle, FVector(0.13f, 0.13f, 0.14f), Dark);
	for (const float Side : { -1.f, 1.f })
	{
		AddPart(CylinderMesh, Wheel, FVector(0.0, Side * WidthCm * 0.22f, 0.0), Axle,
			FVector(0.20f, 0.20f, 0.035f), Metal);
	}
	AddRod(Wheel, FVector(0.0, -WidthCm * 0.62f, 0.0), FVector(0.0, WidthCm * 0.62f, 0.0), 1.6f, Metal);

	// Brake disc (left side) and a static caliper on the fork/swingarm.
	const float DiscY = -WidthCm * 0.34f;
	const float DiscDiameter = 0.60f * R;
	AddPart(CylinderMesh, Wheel, FVector(0.0, DiscY, 0.0), Axle,
		FVector(DiscDiameter / 100.f, DiscDiameter / 100.f, 0.006f), Metal);
	AddPart(CylinderMesh, Wheel, FVector(0.0, DiscY - 0.2f, 0.0), Axle,
		FVector(0.30f * R / 100.f, 0.30f * R / 100.f, 0.012f), Dark);
	const FVector CaliperPos = Hub + FVector(0.11f * R, DiscY - 0.5f, 0.38f * R);
	AddPart(CubeMesh, Parent, CaliperPos, FRotator(12.f, 0.f, 0.f), FVector(0.065f, 0.055f, 0.11f), Dark);
	AddPart(CubeMesh, Parent, CaliperPos + FVector(0.0, -0.35f, 0.0), FRotator(12.f, 0.f, 0.f),
		FVector(0.045f, 0.012f, 0.065f), Gold);

	// Rear sprocket and teeth (right side).
	if (bRear)
	{
		const float SprocketY = WidthCm * 0.36f;
		const float SprocketR = 0.30f * R;
		AddPart(CylinderMesh, Wheel, FVector(0.0, SprocketY, 0.0), Axle,
			FVector(SprocketR * 2.f / 100.f, SprocketR * 2.f / 100.f, 0.008f), Metal);
		TArray<FTransform> Teeth;
		Teeth.Reserve(14);
		for (int32 i = 0; i < 14; ++i)
		{
			const float A = 360.f * i / 14.f;
			const float Rad = FMath::DegreesToRadians(A);
			const FVector Pos(SprocketR * FMath::Cos(Rad), SprocketY, SprocketR * FMath::Sin(Rad));
			Teeth.Add(FTransform(FRotator(A + 90.f, 0.f, 0.f), Pos, FVector(0.018f, 0.010f, 0.020f)));
		}
		AddInstances(CubeMesh, Wheel, Teeth, Dark);
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
	PaintMaterial = MakeMaterial(Master, Paint, 0.28f, 0.15f);
	UMaterialInstanceDynamic* White = MakeMaterial(Master, FLinearColor(0.84f, 0.84f, 0.81f), 0.42f, 0.05f);
	UMaterialInstanceDynamic* Dark = MakeMaterial(Master, FLinearColor(0.032f, 0.032f, 0.038f), 0.52f, 0.45f);
	UMaterialInstanceDynamic* Metal = MakeMaterial(Master, FLinearColor(0.62f, 0.62f, 0.65f), 0.22f, 1.f);
	UMaterialInstanceDynamic* Seat = MakeMaterial(Master, FLinearColor(0.018f, 0.018f, 0.02f), 0.88f, 0.f);
	UMaterialInstanceDynamic* Gold = MakeMaterial(Master, FLinearColor(0.88f, 0.62f, 0.16f), 0.28f, 1.f);
	UMaterialInstanceDynamic* Rubber = MakeMaterial(Master, FLinearColor(0.016f, 0.016f, 0.018f), 0.95f, 0.f);
	UMaterialInstanceDynamic* Lamp = MakeMaterial(Emissive, FLinearColor(1.f, 0.95f, 0.8f), 0.35f, 0.f, 4.f);
	UMaterialInstanceDynamic* Flame = MakeMaterial(Emissive, FLinearColor(1.f, 0.32f, 0.03f), 0.4f, 0.f, 8.f);
	TailMaterial = MakeMaterial(Emissive, FLinearColor(1.f, 0.035f, 0.02f), 0.35f, 0.f, 3.f);

	const float R = WheelRadius;

	Tilt = AddPivot(this, FVector::ZeroVector);
	Vibe = AddPivot(Tilt, FVector::ZeroVector);
	Body = AddPivot(Vibe, FVector::ZeroVector);
	RiderMount = AddPivot(Vibe, RiderSeat);

	// ---- rear: wheel, swingarm, shock, chain
	RearWheel = BuildWheel(Body, FVector(RearHubX, 0.0, R), true, Rubber, Metal, Dark, Metal, Gold);
	for (const float Side : { -11.f, 11.f })
	{
		AddRod(Body, FVector(-10.0, Side, 43.0), FVector(RearHubX, Side * 0.9f, R), 5.5f, Metal);
	}
	AddPart(CubeMesh, Body, FVector(-40.0, 0.0, 39.0), FRotator::ZeroRotator, FVector(0.08f, 0.21f, 0.05f), Dark);
	AddRod(Body, FVector(-22.0, 0.0, 86.0), FVector(-36.0, 0.0, 46.0), 8.f, Gold);
	AddRod(Body, FVector(-22.0, 0.0, 86.0), FVector(-36.0, 0.0, 46.0), 3.2f, Metal);
	AddPart(CylinderMesh, Body, FVector(-24.0, 7.5, 80.0), FRotator(28.f, 0.f, 0.f), FVector(0.075f, 0.075f, 0.17f), Metal);
	AddPart(CylinderMesh, Body, FVector(-24.0, 7.5, 89.0), FRotator(28.f, 0.f, 0.f), FVector(0.045f, 0.045f, 0.03f), Gold);

	const float ChainY = 5.8f;
	AddPart(CylinderMesh, Body, FVector(-2.0, ChainY, 45.0), FRotator(0.f, 0.f, 90.f),
		FVector(0.14f, 0.14f, 0.018f), Metal);
	AddRod(Body, FVector(-4.0, ChainY, 51.0), FVector(RearHubX, ChainY, 46.0), 1.35f, Gold);
	AddRod(Body, FVector(-4.0, ChainY, 39.0), FVector(RearHubX, ChainY, 26.0), 1.35f, Gold);
	AddRod(Body, FVector(RearHubX, ChainY, 26.0), FVector(RearHubX, ChainY, 46.0), 1.35f, Gold);
	AddPart(CubeMesh, Body, FVector(-38.0, ChainY + 1.3f, 55.0), FRotator(-13.f, 0.f, 0.f), FVector(0.56f, 0.015f, 0.030f), Dark);
	AddPart(CubeMesh, Body, FVector(-14.0, ChainY, 47.0), FRotator(-18.f, 0.f, 0.f), FVector(0.11f, 0.026f, 0.045f), Dark);

	// ---- frame
	AddRod(Body, SteeringHead, FVector(14.0, 0.0, 44.0), 7.f, Dark);                   // down tube
	AddRod(Body, SteeringHead, FVector(-24.0, 0.0, 86.0), 6.f, Dark);                  // main spar
	AddRod(Body, FVector(-24.0, 0.0, 86.0), FVector(-14.0, 0.0, 38.0), 6.f, Dark);     // rear frame
	AddRod(Body, FVector(-24.0, 0.0, 86.0), FVector(-78.0, 0.0, 92.0), 4.f, Dark);     // subframe
	AddRod(Body, FVector(-24.0, 0.0, 86.0), FVector(-60.0, 0.0, 94.0), 2.8f, Dark);    // subframe brace
	AddRod(Body, FVector(14.0, 0.0, 44.0), FVector(6.0, 0.0, 30.0), 4.f, Dark);        // cradle
	AddRod(Body, FVector(-14.0, 0.0, 38.0), FVector(6.0, 0.0, 30.0), 4.f, Dark);
	AddPart(CubeMesh, Body, FVector(SteeringHead.X, 0.0, SteeringHead.Z), FRotator::ZeroRotator,
		FVector(0.11f, 0.16f, 0.10f), Dark);                                            // steering head

	// ---- engine: cases, finned cylinder, head, covers, radiator, controls
	AddPart(CubeMesh, Body, FVector(-2.0, 0.0, 48.0), FRotator::ZeroRotator, FVector(0.36f, 0.25f, 0.30f), Dark);
	AddPart(CubeMesh, Body, FVector(2.0, 0.0, 35.0), FRotator(10.f, 0.f, 0.f), FVector(0.30f, 0.22f, 0.12f), Dark);
	AddPart(CylinderMesh, Body, FVector(-4.0, 14.0, 46.0), FRotator(0.f, 0.f, 90.f),
		FVector(0.22f, 0.22f, 0.045f), Metal);                                          // clutch cover
	AddPart(CylinderMesh, Body, FVector(-4.0, -14.0, 46.0), FRotator(0.f, 0.f, 90.f),
		FVector(0.18f, 0.18f, 0.038f), Metal);                                          // ignition cover
	AddRod(Body, FVector(7.0, 0.0, 56.0), FVector(13.0, 0.0, 81.0), 17.5f, Dark);       // cylinder

	// Cooling fins, instanced.
	{
		TArray<FTransform> Fins;
		const FVector FinAxis = FVector(6.0f, 0.0f, 25.0f);
		const FRotator FinRot = FRotationMatrix::MakeFromZ(FinAxis).Rotator();
		for (int32 i = 0; i < 6; ++i)
		{
			const float T = static_cast<float>(i) / 5.f;
			const FVector Pos = FMath::Lerp(FVector(7.0f, 0.0f, 56.0f), FVector(13.0f, 0.0f, 81.0f), T);
			Fins.Add(FTransform(FinRot, Pos, FVector(0.235f, 0.235f, 0.008f)));
		}
		AddInstances(CylinderMesh, Body, Fins, Metal);
	}
	AddPart(CubeMesh, Body, FVector(14.0, 0.0, 84.0), FRotator(-16.f, 0.f, 0.f), FVector(0.25f, 0.21f, 0.075f), Metal);
	AddPart(CubeMesh, Body, FVector(14.0, 0.0, 89.0), FRotator(-16.f, 0.f, 0.f), FVector(0.17f, 0.15f, 0.035f), Dark);
	AddPart(SphereMesh, Body, FVector(9.0, 0.0, 89.0), FRotator::ZeroRotator, FVector(0.035f, 0.035f, 0.045f), White);

	// Radiator and hoses.
	AddPart(CubeMesh, Body, FVector(31.0, 0.0, 68.0), FRotator(12.f, 0.f, 0.f), FVector(0.05f, 0.34f, 0.24f), Dark);
	for (const float Side : { -1.f, 1.f })
	{
		AddPart(CubeMesh, Body, FVector(31.0, Side * 17.0f, 68.0), FRotator(12.f, 0.f, 0.f),
			FVector(0.06f, 0.025f, 0.24f), Metal);
	}
	AddRod(Body, FVector(30.0, 8.0, 79.0), FVector(12.0, 8.0, 82.0), 3.4f, Rubber);
	AddRod(Body, FVector(30.0, -8.0, 57.0), FVector(8.0, -7.0, 52.0), 3.4f, Rubber);

	// Skid plate, foot pegs, gear and brake pedals, kick-start.
	AddPart(CubeMesh, Body, FVector(4.0, 0.0, 31.0), FRotator(8.f, 0.f, 0.f), FVector(0.40f, 0.25f, 0.03f), Metal);
	for (const float Side : { -1.f, 1.f })
	{
		AddRod(Body, FVector(-2.0, 12.0 * Side, 43.0), FVector(6.0, 12.0 * Side, 40.0), 2.5f, Dark);
		AddRod(Body, FVector(6.0, 10.0 * Side, 40.0), FVector(6.0, 22.0 * Side, 40.0), 3.f, Metal);
	}
	AddRod(Body, FVector(0.0, -15.0, 40.0), FVector(10.0, -21.0, 35.0), 2.0f, Metal);
	AddPart(CubeMesh, Body, FVector(12.5, -22.0, 34.0), FRotator::ZeroRotator, FVector(0.085f, 0.030f, 0.028f), Dark);
	AddRod(Body, FVector(-2.0, 15.0, 38.0), FVector(12.0, 20.0, 33.0), 2.0f, Metal);
	AddPart(CubeMesh, Body, FVector(14.0, 21.0, 32.0), FRotator::ZeroRotator, FVector(0.085f, 0.030f, 0.028f), Dark);
	AddRod(Body, FVector(2.0, 16.0, 48.0), FVector(-6.0, 20.0, 34.0), 2.4f, Metal);
	AddPart(CubeMesh, Body, FVector(-8.0, 20.0, 32.0), FRotator(0.f, -20.f, 0.f), FVector(0.10f, 0.030f, 0.030f), Dark);

	// ---- exhaust: header, silencer, heat shield, spark-arrestor tip
	AddRod(Body, FVector(16.0, 9.0, 66.0), FVector(-8.0, 16.0, 60.0), 6.0f, Metal);
	AddRod(Body, FVector(-8.0, 16.0, 60.0), FVector(-40.0, 17.0, 80.0), 7.0f, Metal);
	AddRod(Body, FVector(-38.0, 17.0, 79.0), FVector(-80.0, 17.0, 93.0), 13.0f, Dark);
	AddRod(Body, FVector(-80.0, 17.0, 93.0), FVector(-85.0, 17.0, 95.0), 8.0f, Metal);
	AddPart(CubeMesh, Body, FVector(-34.0, 17.0, 92.0), FRotator(-26.f, 0.f, 0.f), FVector(0.25f, 0.065f, 0.018f), Metal);
	for (const float X : { -48.f, -66.f })
	{
		AddPart(CylinderMesh, Body, FVector(X, 17.0, (X < -60.f ? 89.f : 84.f)), FRotator(22.f, 0.f, 0.f),
			FVector(0.145f, 0.145f, 0.012f), Metal);
	}

	// ---- bodywork: tank, shrouds, seat, side panels, fenders, tail light
	AddPart(SphereMesh, Body, FVector(17.0, 0.0, 91.0), FRotator(-5.f, 0.f, 0.f), FVector(0.50f, 0.31f, 0.24f), PaintMaterial);
	AddPart(CubeMesh, Body, FVector(13.0, 0.0, 100.0), FRotator(-4.f, 0.f, 0.f), FVector(0.31f, 0.23f, 0.055f), PaintMaterial);
	AddPart(CylinderMesh, Body, FVector(9.0, 0.0, 103.0), FRotator::ZeroRotator, FVector(0.085f, 0.085f, 0.022f), Metal);
	AddPart(CylinderMesh, Body, FVector(9.0, 0.0, 105.0), FRotator::ZeroRotator, FVector(0.025f, 0.025f, 0.018f), Dark);
	for (const float Side : { -1.f, 1.f })
	{
		AddPart(CubeMesh, Body, FVector(28.0, 15.0 * Side, 80.0), FRotator(18.f, 0.f, 0.f),
			FVector(0.34f, 0.035f, 0.28f), PaintMaterial);
		AddPart(CubeMesh, Body, FVector(31.0, 17.0 * Side, 82.0), FRotator(18.f, 0.f, 0.f),
			FVector(0.15f, 0.012f, 0.12f), Dark);
		AddPart(CubeMesh, Body, FVector(25.0, 17.2f * Side, 74.0), FRotator(18.f, 0.f, 0.f),
			FVector(0.12f, 0.010f, 0.075f), White);
		AddPart(CubeMesh, Body, FVector(-36.0, 12.0 * Side, 85.0), FRotator(-6.f, 0.f, 0.f),
			FVector(0.28f, 0.030f, 0.17f), White);
		AddPart(CubeMesh, Body, FVector(-36.0, 13.6f * Side, 85.0), FRotator(-6.f, 0.f, 0.f),
			FVector(0.22f, 0.008f, 0.13f), Dark);
	}
	AddPart(CubeMesh, Body, FVector(-16.0, 0.0, 96.0), FRotator(-3.f, 0.f, 0.f), FVector(0.46f, 0.22f, 0.075f), Seat);
	AddPart(CubeMesh, Body, FVector(-44.0, 0.0, 98.0), FRotator(-4.f, 0.f, 0.f), FVector(0.32f, 0.20f, 0.065f), Seat);
	AddPart(CubeMesh, Body, FVector(-62.0, 0.0, 98.0), FRotator(-12.f, 0.f, 0.f), FVector(0.46f, 0.18f, 0.030f), PaintMaterial);
	AddPart(CubeMesh, Body, FVector(-82.0, 0.0, 103.0), FRotator(-16.f, 0.f, 0.f), FVector(0.18f, 0.14f, 0.028f), PaintMaterial);
	AddPart(CubeMesh, Body, FVector(-88.0, 0.0, 100.0), FRotator(-14.f, 0.f, 0.f), FVector(0.03f, 0.10f, 0.048f), TailMaterial);
	AddPart(CubeMesh, Body, FVector(-90.0, 0.0, 97.0), FRotator(-14.f, 0.f, 0.f), FVector(0.012f, 0.13f, 0.075f), Dark);

	// Exhaust flame (visible only on a hard pop/backfire).
	ExhaustFlame = AddPart(ConeMesh, Body, FVector(-92.0, 17.0, 96.0), FRotator(0.f, -90.f, 0.f),
		FVector(0.07f, 0.07f, 0.16f), Flame);
	if (ExhaustFlame)
	{
		ExhaustFlame->SetVisibility(false, true);
	}

	// ---- front end: steering, fork, wheel, fender, bars, number plate, headlight
	FrontPivot = AddPivot(Body, SteeringHead);
	FrontUpper = AddPivot(FrontPivot, FVector::ZeroVector);
	const FVector FrontHub(FrontHubX - SteeringHead.X, 0.0, R - SteeringHead.Z);
	FrontWheel = BuildWheel(FrontPivot, FrontHub, false, Rubber, Metal, Dark, Metal, Gold);

	const FVector ForkTop(-2.0f, 0.0f, 10.0f);
	const FVector ForkMid(12.0f, 0.0f, -24.0f);
	for (const float Side : { -10.f, 10.f })
	{
		const FVector Top = ForkTop + FVector(0.0, Side, 0.0);
		const FVector Mid = ForkMid + FVector(0.0, Side, 0.0);
		const FVector Hub = FrontHub + FVector(0.0, Side, 0.0);
		// The gold stanchion slides inside the dark lower slider when the fork dives.
		AddRod(FrontUpper, Top, Mid + FVector(7.0f, 0.0f, -16.0f), 7.5f, Gold);
		AddRod(FrontPivot, Mid + FVector(-3.0f, 0.0f, 7.0f), Hub, 8.5f, Dark);
		AddPart(CylinderMesh, FrontPivot, Mid + FVector(-1.0f, 0.0f, 3.0f), FRotator(-25.f, 0.f, 0.f),
			FVector(0.115f, 0.115f, 0.018f), Gold);
		// A white fork guard, aligned with the slider instead of a paddle across it.
		const FVector ForkDir = Hub - Mid;
		const FRotator ForkGuardRot = FRotationMatrix::MakeFromZ(ForkDir).Rotator();
		AddPart(CubeMesh, FrontPivot, Mid + ForkDir * 0.45f + FVector(2.0f, Side * 0.9f, 0.0f),
			ForkGuardRot, FVector(0.055f, 0.035f, 0.22f), White);
		AddPart(CubeMesh, FrontPivot, Hub, FRotator::ZeroRotator, FVector(0.05f, 0.05f, 0.035f), Metal);
	}
	AddRod(FrontPivot, FrontHub + FVector(0.0, -16.0f, 0.0), FrontHub + FVector(0.0, 16.0f, 0.0), 1.6f, Metal);

	// Triple clamps, steering stem and bars dive with the fork.
	AddPart(CubeMesh, FrontUpper, FVector(-2.0, 0.0, 10.0), FRotator::ZeroRotator, FVector(0.10f, 0.29f, 0.040f), Dark);
	AddPart(CubeMesh, FrontUpper, FVector(4.0, 0.0, -14.0), FRotator::ZeroRotator, FVector(0.10f, 0.27f, 0.050f), Dark);
	AddRod(FrontUpper, FVector(-2.0, 0.0, 12.0), FVector(8.0, 0.0, 2.0), 3.0f, Metal);
	AddRod(FrontUpper, FVector(-6.0, -38.0, 17.0), FVector(-6.0, 38.0, 17.0), 3.2f, Metal);
	AddPart(CubeMesh, FrontUpper, FVector(-6.0, 0.0, 17.0), FRotator::ZeroRotator, FVector(0.10f, 0.17f, 0.05f), Dark);
	AddPart(CubeMesh, FrontUpper, FVector(-6.0, 0.0, 20.0), FRotator::ZeroRotator, FVector(0.10f, 0.13f, 0.055f), Seat);
	for (const float Side : { -1.f, 1.f })
	{
		AddRod(FrontUpper, FVector(-6.0, 28.0 * Side, 17.0), FVector(-6.0, 40.0 * Side, 17.0), 4.5f, Seat);
		AddRod(FrontUpper, FVector(-4.0, 24.0 * Side, 19.0), FVector(7.0, 33.0 * Side, 17.0), 1.2f, Metal);
		AddPart(CubeMesh, FrontUpper, FVector(-2.0, 26.0 * Side, 19.0), FRotator::ZeroRotator,
			FVector(0.045f, 0.035f, 0.022f), Dark);
		AddPart(CubeMesh, FrontUpper, FVector(2.0, 38.0 * Side, 14.5f), FRotator(0.f, 0.f, 0.f),
			FVector(0.15f, 0.022f, 0.10f), White);
		AddRod(FrontUpper, FVector(-4.0, 26.0 * Side, 18.0), FVector(2.0, 15.0 * Side, -12.0), 0.65f, Dark);
	}
	// Front brake master cylinder and reservoir.
	AddPart(CylinderMesh, FrontUpper, FVector(0.0, 22.0, 18.0), FRotator(10.f, 0.f, 0.f), FVector(0.055f, 0.055f, 0.07f), Dark);
	AddPart(CylinderMesh, FrontUpper, FVector(0.0, 26.0, 20.0), FRotator(10.f, 0.f, 0.f), FVector(0.035f, 0.035f, 0.05f), Metal);
	AddRod(FrontUpper, FVector(0.0, 22.0, 18.0), FVector(-1.0, 12.0, 30.0), 0.5f, Dark);
	// Throttle and clutch cables.
	AddRod(FrontUpper, FVector(2.0, 14.0, -9.0), FVector(7.0, 9.0, 20.0), 0.55f, Dark);
	AddRod(FrontUpper, FVector(2.0, 10.0, -6.0), FVector(2.0, 2.0, 35.0), 0.55f, Dark);

	// Front fender: a three-piece arc over the wheel (rear, crown and front lip).
	{
		const float FenderR = R + 4.0f;
		struct FFenderSegment { float Angle; float Pitch; float Length; };
		static const FFenderSegment Segments[] = {
			{ 120.0f, -30.0f, 24.0f },
			{ 90.0f, 0.0f, 26.0f },
			{ 60.0f, 30.0f, 24.0f }
		};
		for (const FFenderSegment& Segment : Segments)
		{
			const float Rad = FMath::DegreesToRadians(Segment.Angle);
			const FVector Pos = FrontHub + FVector(FenderR * FMath::Cos(Rad), 0.0f, FenderR * FMath::Sin(Rad));
			AddPart(CubeMesh, FrontPivot, Pos, FRotator(Segment.Pitch, 0.f, 0.f),
				FVector(Segment.Length / 100.f, 0.155f, 0.026f), PaintMaterial);
		}
	}

	// Number plate/headlight mask; the lens and spot sit ahead of it.
	AddPart(CubeMesh, FrontUpper, FVector(8.8, 0.0, -5.0), FRotator(18.f, 0.f, 0.f), FVector(0.030f, 0.285f, 0.265f), Dark);
	AddPart(CubeMesh, FrontUpper, FVector(9.1, 0.0, -5.0), FRotator(18.f, 0.f, 0.f), FVector(0.030f, 0.260f, 0.240f), White);
	AddPart(SphereMesh, FrontUpper, FVector(12.6, 0.0, -6.0), FRotator::ZeroRotator, FVector(0.075f, 0.13f, 0.10f), Lamp);
	AddPart(CylinderMesh, FrontUpper, FVector(13.0, 0.0, -6.0), FRotator(0.f, 90.f, 0.f), FVector(0.225f, 0.225f, 0.016f), Dark);
	AddPart(CylinderMesh, FrontUpper, FVector(13.2, 0.0, -6.0), FRotator(0.f, 90.f, 0.f), FVector(0.20f, 0.20f, 0.012f), Lamp);
	AddPart(CubeMesh, FrontUpper, FVector(9.0, 0.0, 1.0), FRotator(18.f, 0.f, 0.f), FVector(0.09f, 0.24f, 0.045f), Dark);
	// A small peak over the light, like a dirt-bike headlight mask.
	AddPart(CubeMesh, FrontUpper, FVector(11.0, 0.0, 4.0), FRotator(34.f, 0.f, 0.f), FVector(0.17f, 0.22f, 0.020f), PaintMaterial);

	// Brake line from the caliper up the fork.
	AddRod(FrontPivot, FrontHub + FVector(7.0, -13.0, -4.0), ForkMid + FVector(-4.0, -13.0, 4.0), 0.65f, Dark);
	AddRod(FrontUpper, FVector(6.0, -13.0, 2.0), FVector(-2.0, -26.0, 17.0), 0.65f, Dark);

	// ---- lights
	Headlight = NewObject<USpotLightComponent>(GetOwner(), NAME_None, RF_Transient);
	Headlight->SetupAttachment(FrontUpper);
	Headlight->SetRelativeLocationAndRotation(FVector(14.0, 0.0, -6.0), FRotator(-7.f, 0.f, 0.f));
	Headlight->SetMobility(EComponentMobility::Movable);
	Headlight->SetIntensityUnits(ELightUnits::Unitless);
	Headlight->SetIntensity(0.f);
	Headlight->SetInnerConeAngle(16.f);
	Headlight->SetOuterConeAngle(32.f);
	Headlight->SetAttenuationRadius(4500.f);
	Headlight->SetLightColor(FLinearColor(1.f, 0.94f, 0.82f));
	Headlight->SetCastShadows(false);
	Headlight->RegisterComponent();

	BrakeGlow = NewObject<UPointLightComponent>(GetOwner(), NAME_None, RF_Transient);
	BrakeGlow->SetupAttachment(Body);
	BrakeGlow->SetRelativeLocation(FVector(-90.0, 0.0, 100.0));
	BrakeGlow->SetMobility(EComponentMobility::Movable);
	BrakeGlow->SetIntensityUnits(ELightUnits::Unitless);
	BrakeGlow->SetIntensity(0.f);
	BrakeGlow->SetAttenuationRadius(320.f);
	BrakeGlow->SetLightColor(FLinearColor(1.f, 0.035f, 0.015f));
	BrakeGlow->SetCastShadows(false);
	BrakeGlow->RegisterComponent();

	// ---- audio: a spatialised synth at the exhaust, following lean and suspension
	EngineAudio = NewObject<UDAEngineSynthComponent>(GetOwner(), TEXT("BikeEngineAudio"), RF_Transient);
	if (EngineAudio)
	{
		EngineAudio->SetupAttachment(Vibe);
		EngineAudio->SetRelativeLocation(FVector(-45.0, 14.0, 78.0));
		EngineAudio->RegisterComponent();
	}
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
		FrontTravel = 0.f;
		FrontTravelVelocity = 0.f;
		bWasAirborne = false;
		Body->SetRelativeScale3D(FVector(0.01));
		Gear = 1;
		EngineRPM = IdleRPM;
		ShiftTimer = 0.f;
		BackfireCooldown = 0.f;
		LastForwardSpeed = 0.f;
		ExhaustFlashTimer = 0.f;
		if (ExhaustFlame)
		{
			ExhaustFlame->SetVisibility(false, true);
		}
		if (EngineAudio)
		{
			EngineAudio->StartEngine();
			bAudioStarted = true;
		}
	}
	if (!bOn)
	{
		if (Headlight)
		{
			Headlight->SetIntensity(0.f);
		}
		if (BrakeGlow)
		{
			BrakeGlow->SetIntensity(0.f);
		}
		if (ExhaustFlame)
		{
			ExhaustFlame->SetVisibility(false, true);
		}
		if (EngineAudio && bAudioStarted)
		{
			EngineAudio->StopEngine(0.45f);
			bAudioStarted = false;
		}
	}
}

void UDAMotorcycleComponent::TriggerExhaustPop(bool bFlash)
{
	if (EngineAudio)
	{
		EngineAudio->TriggerExhaustPop();
	}
	if (bFlash)
	{
		ExhaustFlashTimer = 0.11f;
	}
}

void UDAMotorcycleComponent::UpdateDrivetrain(float DeltaTime, const FDABikePose& Pose, float Acceleration)
{
	const float Speed = FMath::Abs(Pose.ForwardSpeed);
	const float Throttle = FMath::Clamp(Pose.Throttle, 0.f, 1.f);
	const bool bGrounded = !Pose.bAirborne;
	const float WheelRPM = Speed / FMath::Max(2.f * PI * WheelRadius, 1.f) * 60.f;

	if (Speed < 35.f && ShiftTimer <= 0.f)
	{
		Gear = 1;
	}

	if (ShiftTimer > 0.f)
	{
		ShiftTimer -= DeltaTime;
	}
	else if (Speed > 90.f)
	{
		const float UpShiftRPM = FMath::Max(IdleRPM + 1200.f, RedlineRPM - 1200.f);
		const float DownShiftRPM = IdleRPM + 1300.f;
		if (Gear < 5 && EngineRPM > UpShiftRPM)
		{
			++Gear;
			ShiftTimer = 0.16f;
			if (EngineAudio)
			{
				EngineAudio->TriggerShift();
			}
		}
		else if (Gear > 1 && EngineRPM < DownShiftRPM)
		{
			--Gear;
			ShiftTimer = 0.14f;
			if (EngineAudio)
			{
				EngineAudio->TriggerShift();
			}
			// A closed-throttle downshift barks through the exhaust.
			if (Throttle < 0.15f && Speed > 500.f)
			{
				TriggerExhaustPop(true);
			}
		}
	}

	const float Ratio = GearRatios[FMath::Clamp(Gear, 1, 5) - 1] * PrimaryDrive * FinalDrive;
	const float DrivenRPM = WheelRPM * Ratio;
	float TargetRPM;
	if (Pose.bAirborne)
	{
		// The rear wheel is off the ground: the throttle revs the engine freely.
		TargetRPM = Throttle > 0.05f ? IdleRPM + Throttle * (RedlineRPM - IdleRPM) * 0.72f : DrivenRPM;
	}
	else if (Speed < 230.f && DrivenRPM < IdleRPM * 1.4f)
	{
		// Slipping the clutch off the line.
		TargetRPM = FMath::Max(DrivenRPM, IdleRPM + Throttle * 2800.f);
	}
	else
	{
		TargetRPM = FMath::Max(DrivenRPM, IdleRPM + Throttle * 350.f);
	}
	if (ShiftTimer > 0.f)
	{
		TargetRPM = FMath::Max(IdleRPM, DrivenRPM * 0.90f);
	}
	TargetRPM = FMath::Clamp(TargetRPM, IdleRPM * 0.85f, RedlineRPM + 250.f);
	EngineRPM = FMath::FInterpTo(EngineRPM, TargetRPM, DeltaTime, ShiftTimer > 0.f ? 14.f : 6.5f);

	if (Speed < 35.f && Throttle < 0.02f)
	{
		EngineRPM = FMath::FInterpTo(EngineRPM, IdleRPM, DeltaTime, 4.f);
	}

	// A hard throttle chop at speed lights the exhaust.
	BackfireCooldown -= DeltaTime;
	if (bGrounded && Throttle < 0.05f && Speed > 450.f && Acceleration < -250.f && BackfireCooldown <= 0.f)
	{
		TriggerExhaustPop(true);
		BackfireCooldown = 0.9f + FMath::FRandRange(0.f, 1.0f);
	}

	if (EngineAudio)
	{
		FDAEngineAudioParams Params;
		Params.RPM = EngineRPM;
		Params.Throttle = Throttle;
		Params.Speed = Speed;
		Params.Speed01 = FMath::Clamp(Speed / AudioTopSpeed, 0.f, 1.f);
		Params.Gear = static_cast<float>(Gear);
		Params.bGrounded = bGrounded;
		Params.bBraking = Pose.bBraking;
		EngineAudio->SetEngineState(Params);
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

	const float Acceleration = (Pose.ForwardSpeed - LastForwardSpeed) / DeltaTime;
	const bool bBraking = Pose.bBraking || (Pose.Throttle < 0.05f && Acceleration < -260.f);
	UpdateDrivetrain(DeltaTime, Pose, Acceleration);

	// Wheels: rolling without slipping (a positive angle about +Y rolls the wheel forwards).
	WheelAngle = FMath::Fmod(WheelAngle + Pose.ForwardSpeed / FMath::Max(WheelRadius, 1.f) * DeltaTime, 2.f * PI);
	const FQuat Spin(FVector::YAxisVector, WheelAngle);
	RearWheel->SetRelativeRotation(Spin);
	FrontWheel->SetRelativeRotation(Spin);
	FrontPivot->SetRelativeRotation(FRotator(0.f, FMath::Clamp(Pose.Steer, -1.f, 1.f) * MaxSteerAngle, 0.f));

	// Front suspension: the upper fork/bars/headlight dive under braking and
	// on landing while the wheel (and fender) stay planted on the ground.
	if (bWasAirborne && !Pose.bAirborne)
	{
		FrontTravelVelocity += 55.f;
	}
	const float DiveTarget = bBraking ? 5.0f : FMath::Clamp(-Acceleration * 0.0018f, -1.0f, 3.0f);
	FrontTravelVelocity += ((DiveTarget - FrontTravel) * 320.f - FrontTravelVelocity * 24.f) * DeltaTime;
	FrontTravel = FMath::Clamp(FrontTravel + FrontTravelVelocity * DeltaTime, -2.5f, 7.0f);
	FrontUpper->SetRelativeLocation(FVector(0.0, 0.0, -FrontTravel));

	// Rear suspension: a damped spring that compresses on landing and chatters a
	// little over rough ground.
	if (bWasAirborne && !Pose.bAirborne)
	{
		SuspensionVelocity -= 150.f;
	}
	bWasAirborne = Pose.bAirborne;
	const float Speed01 = FMath::Clamp(FMath::Abs(Pose.ForwardSpeed) / 1500.f, 0.f, 1.f);
	const float Chatter = Pose.bAirborne ? 0.f : (0.4f + 0.8f * Speed01) * (FMath::Sin(Time * 23.f) + 0.6f * FMath::Sin(Time * 37.f + 1.3f));
	const float Accel = -SpringStiffness * (SuspensionOffset - Chatter) - SpringDamping * SuspensionVelocity;
	SuspensionVelocity += Accel * DeltaTime;
	SuspensionOffset = FMath::Clamp(SuspensionOffset + SuspensionVelocity * DeltaTime, -9.f, 7.f);

	// Engine vibration: a small half-order shake through the chassis and rider.
	const float Rpm01 = FMath::Clamp((EngineRPM - IdleRPM) / FMath::Max(RedlineRPM - IdleRPM, 1.f), 0.f, 1.f);
	VibePhase = FMath::Fmod(VibePhase + (EngineRPM / 60.f) * PI * DeltaTime, 2.f * PI);
	const float VibeAmp = (0.15f + 0.85f * Rpm01) * (0.55f + 0.45f * Pose.Throttle);
	Vibe->SetRelativeLocation(FVector(0.0,
		0.045f * FMath::Sin(VibePhase) * VibeAmp,
		0.060f * FMath::Sin(2.f * VibePhase + 0.7f) * VibeAmp));
	Vibe->SetRelativeRotation(FRotator(
		0.10f * FMath::Sin(2.f * VibePhase + 0.4f) * VibeAmp,
		0.00f,
		0.07f * FMath::Sin(VibePhase + 1.2f) * VibeAmp));

	// Lean about the tyre contact line, pitch about the point between the wheels.
	// A little squat/dive is folded into the pitch for weight transfer.
	const float AccelPitch = FMath::Clamp(Acceleration * 0.0015f, -2.5f, 2.5f);
	Tilt->SetRelativeLocationAndRotation(FVector(0.0, 0.0, SuspensionOffset),
		FRotator(FMath::Clamp(Pose.Pitch + AccelPitch, -42.f, 42.f), 0.f, FMath::Clamp(Pose.Lean, -45.f, 45.f)));

	// Lights.
	NightAlphaSmoothed = FMath::FInterpTo(NightAlphaSmoothed, FMath::Clamp(Pose.NightAlpha, 0.f, 1.f), DeltaTime, 1.5f);
	BrakeAlpha = FMath::FInterpTo(BrakeAlpha, bBraking ? 1.f : 0.f, DeltaTime, 18.f);
	if (Headlight)
	{
		Headlight->SetIntensity(18000.f * NightAlphaSmoothed);
	}
	if (BrakeGlow)
	{
		BrakeGlow->SetIntensity(900.f * BrakeAlpha * NightAlphaSmoothed);
	}
	if (TailMaterial)
	{
		TailMaterial->SetScalarParameterValue(TEXT("Strength"), 2.5f + 8.0f * BrakeAlpha);
	}

	// Exhaust flame on a hard pop; a short, flickering cone at the silencer tip.
	if (ExhaustFlame)
	{
		if (ExhaustFlashTimer > 0.f)
		{
			ExhaustFlashTimer -= DeltaTime;
			ExhaustFlame->SetVisibility(true, true);
			const float Flicker = 0.8f + 0.35f * FMath::Sin(Time * 95.f) + 0.15f * FMath::Sin(Time * 171.f);
			ExhaustFlame->SetRelativeScale3D(FVector(0.07f, 0.07f, 0.16f * Flicker));
		}
		else
		{
			ExhaustFlame->SetVisibility(false, true);
		}
	}

	LastForwardSpeed = Pose.ForwardSpeed;
}
