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

	// Layout (cm before ModelScale, bike space: +X forward, +Y right, +Z up, origin on the ground between the wheels).
	const float RearHubX = -70.f;
	const float FrontHubX = 78.f;
	const FVector SteeringHead(46.0, 0.0, 100.0);
	const FVector RiderSeat(-14.0, 0.0, 0.0);
	const FVector SwingarmPivot(-10.0, 0.0, 43.0);
	/** Shock mounts: top on the frame, bottom on the swingarm linkage (body space at rest). */
	const FVector ShockTop(-22.0, 0.0, 86.0);
	const FVector ShockBottom(-36.0, 0.0, 46.0);
	/** Rider contacts: the seat surface under the hips, the top of the right peg (the left is mirrored), and the
	 *  right grip centre in steering space (relative to the steering head, before the steering turns it). */
	const FVector SeatPoint(-10.0, 0.0, 100.0);
	const FVector PegTop(6.0, 17.0, 41.5);
	const FVector GripCentre(-10.65, 35.0, 24.25);
	/** Where the left foot goes down at a stop: on the ground just behind the peg, under the slid hip (bike root
	 *  space, cm before scale). */
	const FVector FootGround(-2.0, -34.0, 0.0);
	/** The hips slide this far towards the foot that goes down (cm) and drop off the seat's crown, so a 1.0 rider
	 *  reaches the ground on tiptoe from the 93 cm seat (a tall enduro is like that). */
	const float FootDownHipSlide = 15.f;
	const float FootDownHipDrop = 4.f;

	// Fork: from the top clamp (steering space) down to the front hub; the stanchions are parallel to the steering axis.
	const FVector ForkTop(-2.0, 0.0, 10.0);
	const FVector FrontHubSteer(FrontHubX - 46.0, 0.0, 36.0 - 100.0);   // FrontHub - SteeringHead at WheelRadius 36

	// Suspension springs (cm at the axle, rider included): stiffness, damping, travel limits.
	const float RearStiffness = 260.f;
	const float RearDamping = 20.f;
	const float FrontStiffness = 320.f;
	const float FrontDamping = 24.f;
	const float MinTravel = -4.f;
	const float MaxTravel = 11.f;

	// 5-speed dirt-bike box.
	const float GearRatios[5] = { 2.55f, 1.85f, 1.42f, 1.15f, 0.94f };
	const float PrimaryDrive = 3.15f;
	const float FinalDrive = 3.40f;
	const float AudioTopSpeed = 2200.f;

	// Geometry of the instanced rings.
	const int32 TyreSegments = 30;
	const int32 RimSegments = 26;
	const int32 TyreKnobsPerRow = 18;
	const int32 WheelSpokesPerSide = 8;
	const int32 DiscHoles = 12;
	/** Chain: link pitch (cm) and the rear sprocket radius as a share of the wheel radius. */
	const float ChainPitch = 2.6f;
	const float RearSprocketShare = 0.30f;

	FVector ForkAxisDown()
	{
		return (FrontHubSteer - ForkTop).GetSafeNormal();
	}
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
	ModelScale = FMath::IsFinite(ModelScale) ? FMath::Clamp(ModelScale, 0.3f, 3.f) : 0.95f;
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

void UDAMotorcycleComponent::AddTube(USceneComponent* Parent, const TArray<FVector>& Points, float Diameter,
	UMaterialInterface* Material)
{
	for (int32 i = 0; i + 1 < Points.Num(); ++i)
	{
		AddRod(Parent, Points[i], Points[i + 1], Diameter, Material);
		if (i > 0)
		{
			// a ball at each bend so the tube reads as one bent pipe
			AddPart(SphereMesh, Parent, Points[i], FRotator::ZeroRotator, FVector(Diameter / 100.f), Material);
		}
	}
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
	const float WidthCm = (bRear ? 17.f : 14.5f);
	const FRotator Axle(0.f, 0.f, 90.f);

	USceneComponent* Wheel = AddPivot(Parent, Hub);

	// Round-section tyre: a ring of short cylinders laid along the tread, each an ellipse as wide as the tyre and
	// as deep as its sidewall, so the carcass is rounded like a real tyre instead of a boxy band. The ring leaves
	// the hub and spokes visible through the wheel.
	{
		TArray<FTransform> TyreRing;
		TyreRing.Reserve(TyreSegments);
		const float SegmentLength = 2.f * PI * TyreMidR / TyreSegments * 1.12f;
		for (int32 i = 0; i < TyreSegments; ++i)
		{
			const float Rad = 2.f * PI * i / TyreSegments;
			const FVector Radial(FMath::Cos(Rad), 0.0, FMath::Sin(Rad));
			const FVector Tangent(-FMath::Sin(Rad), 0.0, FMath::Cos(Rad));
			const FRotator Rot = FRotationMatrix::MakeFromZX(Tangent, Radial).Rotator();
			TyreRing.Add(FTransform(Rot, Radial * TyreMidR,
				FVector(TyreThickness * 1.05f / 100.f, WidthCm / 100.f, SegmentLength / 100.f)));
		}
		AddInstances(CylinderMesh, Wheel, TyreRing, Rubber);
	}

	// Knobby tread: a centre row and two shoulder rows, staggered like an enduro tyre.
	{
		TArray<FTransform> Knobs;
		Knobs.Reserve(TyreKnobsPerRow * 3);
		for (int32 Row = 0; Row < 3; ++Row)
		{
			const float Side = static_cast<float>(Row - 1);               // -1 left shoulder, 0 centre, 1 right shoulder
			const float RowR = R + (Row == 1 ? 1.1f : 0.2f);
			const float Offset = (Row == 1 ? 0.5f : 0.f) * 360.f / TyreKnobsPerRow;
			for (int32 i = 0; i < TyreKnobsPerRow; ++i)
			{
				const float A = 360.f * i / TyreKnobsPerRow + Offset;
				const float Rad = FMath::DegreesToRadians(A);
				const FVector Pos(RowR * FMath::Cos(Rad), Side * WidthCm * 0.33f, RowR * FMath::Sin(Rad));
				// shoulder knobs lean out with the carcass (the box's local -Z faces out of the tread; a positive
				// roll would tip it towards +Y before the pitch, so the right shoulder rolls negative)
				Knobs.Add(FTransform(FRotator(A + 90.f, 0.f, -Side * 28.f), Pos,
					Row == 1 ? FVector(0.055f, 0.06f, 0.035f) : FVector(0.045f, 0.045f, 0.032f)));
			}
		}
		AddInstances(CubeMesh, Wheel, Knobs, Rubber);
	}

	// Rim: a round tube ring with a deeper spoke bed inside it.
	{
		TArray<FTransform> RimRing;
		TArray<FTransform> RimBed;
		RimRing.Reserve(RimSegments);
		RimBed.Reserve(RimSegments);
		for (int32 i = 0; i < RimSegments; ++i)
		{
			const float Rad = 2.f * PI * i / RimSegments;
			const FVector Radial(FMath::Cos(Rad), 0.0, FMath::Sin(Rad));
			const FVector Tangent(-FMath::Sin(Rad), 0.0, FMath::Cos(Rad));
			const FRotator Rot = FRotationMatrix::MakeFromZX(Tangent, Radial).Rotator();
			const float Seg = 2.f * PI * RimR / RimSegments * 1.12f;
			RimRing.Add(FTransform(Rot, Radial * RimR, FVector(0.030f, 0.060f, Seg / 100.f)));
			RimBed.Add(FTransform(Rot, Radial * (RimR - 1.6f), FVector(0.022f, 0.032f, Seg / 100.f)));
		}
		AddInstances(CylinderMesh, Wheel, RimRing, Rim);
		AddInstances(CylinderMesh, Wheel, RimBed, Dark);
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
				// from the wide hub flange in to the centre of the rim
				const FVector A0(FMath::Cos(Rad) * 4.0f, SideY * 0.8f, FMath::Sin(Rad) * 4.0f);
				const FVector B0(FMath::Cos(Rad) * RimR * 0.94f, SideY * 0.15f, FMath::Sin(Rad) * RimR * 0.94f);
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

	// Drilled brake disc (left side) on a dark carrier, and a caliper on the fork leg / swingarm.
	const float DiscY = -WidthCm * 0.34f;
	const float DiscDiameter = 0.60f * R;
	AddPart(CylinderMesh, Wheel, FVector(0.0, DiscY, 0.0), Axle,
		FVector(DiscDiameter / 100.f, DiscDiameter / 100.f, 0.006f), Metal);
	AddPart(CylinderMesh, Wheel, FVector(0.0, DiscY - 0.2f, 0.0), Axle,
		FVector(0.30f * R / 100.f, 0.30f * R / 100.f, 0.012f), Dark);
	{
		TArray<FTransform> Holes;
		Holes.Reserve(DiscHoles);
		const float HoleR = DiscDiameter * 0.5f * 0.80f;
		for (int32 i = 0; i < DiscHoles; ++i)
		{
			const float Rad = 2.f * PI * (i + 0.5f) / DiscHoles;
			Holes.Add(FTransform(Axle, FVector(HoleR * FMath::Cos(Rad), DiscY - 0.15f, HoleR * FMath::Sin(Rad)),
				FVector(0.014f, 0.014f, 0.009f)));
		}
		AddInstances(CylinderMesh, Wheel, Holes, Dark);
	}
	const FVector CaliperPos = Hub + FVector(0.11f * R, DiscY - 0.5f, 0.38f * R);
	AddPart(CubeMesh, Parent, CaliperPos, FRotator(12.f, 0.f, 0.f), FVector(0.065f, 0.055f, 0.11f), Dark);
	AddPart(CubeMesh, Parent, CaliperPos + FVector(0.0, -0.35f, 0.0), FRotator(12.f, 0.f, 0.f),
		FVector(0.045f, 0.012f, 0.065f), Gold);

	// Rear sprocket and teeth (right side).
	if (bRear)
	{
		const float SprocketY = WidthCm * 0.36f;
		const float SprocketR = RearSprocketShare * R;
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

UInstancedStaticMeshComponent* UDAMotorcycleComponent::BuildChainRun(const FVector& A, const FVector& B,
	UMaterialInterface* Plate, UMaterialInterface* Pin, int32 RunIndex)
{
	// A and B are body-space points; the run lives on the swingarm.
	const FVector LocalA = A - SwingarmPivot;
	const FVector LocalB = B - SwingarmPivot;
	const FVector Dir = (LocalB - LocalA).GetSafeNormal();
	const float Length = static_cast<float>((LocalB - LocalA).Size());
	ChainStart[RunIndex] = LocalA;
	ChainDir[RunIndex] = Dir;
	// the pins under the plates keep the run continuous while the links slide
	AddRod(Swingarm, LocalA, LocalB, 0.9f, Pin);
	TArray<FTransform> Links;
	const int32 Count = FMath::Max(1, FMath::FloorToInt(Length / ChainPitch));
	Links.Reserve(Count);
	for (int32 i = 0; i < Count; ++i)
	{
		Links.Add(FTransform(FRotator::ZeroRotator, FVector(i * ChainPitch, 0.0, 0.0), FVector(0.021f, 0.016f, 0.011f)));
	}
	UInstancedStaticMeshComponent* Run = AddInstances(CubeMesh, Swingarm, Links, Plate);
	if (Run)
	{
		Run->SetRelativeLocationAndRotation(LocalA, FRotationMatrix::MakeFromX(Dir).Rotator());
	}
	return Run;
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
	UMaterialInstanceDynamic* Alloy = MakeMaterial(Master, FLinearColor(0.30f, 0.31f, 0.33f), 0.34f, 1.f);
	UMaterialInstanceDynamic* Seat = MakeMaterial(Master, FLinearColor(0.018f, 0.018f, 0.02f), 0.88f, 0.f);
	UMaterialInstanceDynamic* Gold = MakeMaterial(Master, FLinearColor(0.88f, 0.62f, 0.16f), 0.28f, 1.f);
	UMaterialInstanceDynamic* Rubber = MakeMaterial(Master, FLinearColor(0.016f, 0.016f, 0.018f), 0.95f, 0.f);
	UMaterialInstanceDynamic* Lamp = MakeMaterial(Emissive, FLinearColor(1.f, 0.95f, 0.8f), 0.35f, 0.f, 4.f);
	UMaterialInstanceDynamic* Flame = MakeMaterial(Emissive, FLinearColor(1.f, 0.32f, 0.03f), 0.4f, 0.f, 8.f);
	TailMaterial = MakeMaterial(Emissive, FLinearColor(1.f, 0.035f, 0.02f), 0.35f, 0.f, 3.f);

	const float R = WheelRadius;

	// Tilt (lean / pitch on the ground) -> Vibe (engine shake) -> Sprung (suspension heave / pitch) carries the
	// rider mount and the scaled Body; inside the Body the swingarm and the fork keep the wheels on the ground.
	Tilt = AddPivot(this, FVector::ZeroVector);
	Vibe = AddPivot(Tilt, FVector::ZeroVector);
	Sprung = AddPivot(Vibe, FVector::ZeroVector);
	Body = AddPivot(Sprung, FVector::ZeroVector);
	Body->SetRelativeScale3D(FVector(ModelScale));
	RiderMount = AddPivot(Sprung, RiderSeat * ModelScale);

	// ---- rear: swingarm with the wheel, chain runs and guides; shock on its linkage
	Swingarm = AddPivot(Body, SwingarmPivot);
	const FVector RearHubLocal = FVector(RearHubX, 0.0, R) - SwingarmPivot;
	RearWheel = BuildWheel(Swingarm, RearHubLocal, true, Rubber, Metal, Dark, Metal, Gold);
	for (const float Side : { -11.f, 11.f })
	{
		AddRod(Swingarm, FVector(0.0, Side, 0.0), RearHubLocal + FVector(0.0, Side * -0.1f, 0.0), 5.5f, Alloy);
		// axle blocks and chain adjusters at the rear of each arm
		AddPart(CubeMesh, Swingarm, RearHubLocal + FVector(0.0, Side, 0.0), FRotator::ZeroRotator,
			FVector(0.07f, 0.03f, 0.05f), Metal);
	}
	AddPart(CubeMesh, Swingarm, FVector(-30.0, 0.0, -4.0), FRotator::ZeroRotator, FVector(0.08f, 0.21f, 0.05f), Alloy);
	AddPart(CylinderMesh, Swingarm, FVector::ZeroVector, FRotator(0.f, 0.f, 90.f), FVector(0.07f, 0.07f, 0.26f), Dark);
	// shock linkage on the swingarm (the shock's bottom eye)
	AddPart(CubeMesh, Swingarm, ShockBottom - SwingarmPivot + FVector(0.0, 0.0, -2.0), FRotator(-10.f, 0.f, 0.f),
		FVector(0.09f, 0.08f, 0.05f), Dark);

	const float ChainY = 5.8f;
	const float FrontSprocketR = 7.f;
	const float RearSprocketR = RearSprocketShare * R;
	AddPart(CylinderMesh, Body, FVector(-2.0, ChainY, 45.0), FRotator(0.f, 0.f, 90.f),
		FVector(FrontSprocketR * 2.f / 100.f, FrontSprocketR * 2.f / 100.f, 0.018f), Metal);
	ChainLinksTop = BuildChainRun(FVector(-2.0, ChainY, 45.0 + FrontSprocketR), FVector(RearHubX, ChainY, R + RearSprocketR), Dark, Gold, 0);
	ChainLinksBottom = BuildChainRun(FVector(-2.0, ChainY, 45.0 - FrontSprocketR), FVector(RearHubX, ChainY, R - RearSprocketR), Dark, Gold, 1);
	AddPart(CubeMesh, Swingarm, FVector(-28.0, ChainY + 1.3f, 11.0), FRotator(-6.f, 0.f, 0.f), FVector(0.50f, 0.015f, 0.030f), Dark);
	AddPart(CubeMesh, Swingarm, FVector(-6.0, ChainY, 3.5), FRotator(-18.f, 0.f, 0.f), FVector(0.11f, 0.026f, 0.045f), Dark);

	// The shock: damper body and piggyback reservoir hang from the top mount; the spring, shaft and bottom eye
	// stretch to the linkage (ShockSpring is scaled along the shock as it compresses).
	{
		const float Length0 = static_cast<float>((ShockTop - ShockBottom).Size());
		ShockAim = AddPivot(Body, ShockTop);
		ShockAim->SetRelativeRotation(FRotationMatrix::MakeFromZ(ShockTop - ShockBottom).Rotator());
		AddPart(CylinderMesh, ShockAim, FVector(0.0, 0.0, -1.0), FRotator(0.f, 0.f, 90.f), FVector(0.05f, 0.05f, 0.07f), Dark);
		AddPart(CylinderMesh, ShockAim, FVector(0.0, 0.0, -8.0), FRotator::ZeroRotator, FVector(0.055f, 0.055f, 0.15f), Dark);
		AddPart(CylinderMesh, ShockAim, FVector(0.0, 0.0, -4.0), FRotator::ZeroRotator, FVector(0.075f, 0.075f, 0.025f), Gold);
		AddPart(CylinderMesh, ShockAim, FVector(0.0, 7.5, -7.0), FRotator::ZeroRotator, FVector(0.065f, 0.065f, 0.16f), Gold);
		AddRod(ShockAim, FVector(0.0, 0.0, -4.0), FVector(0.0, 7.5, -2.0), 1.2f, Dark);
		ShockSpring = AddPivot(ShockAim, FVector::ZeroVector);
		AddRod(ShockSpring, FVector(0.0, 0.0, -14.0), FVector(0.0, 0.0, -Length0 + 2.0), 2.6f, Metal);
		TArray<FTransform> Coils;
		const int32 CoilCount = 9;
		for (int32 i = 0; i < CoilCount; ++i)
		{
			const float Z = FMath::Lerp(-6.f, -Length0 + 4.f, static_cast<float>(i) / (CoilCount - 1));
			// alternate the tilt a little so the stack reads as a helix
			Coils.Add(FTransform(FRotator((i % 2 == 0) ? 7.f : -7.f, 0.f, 0.f), FVector(0.0, 0.0, Z), FVector(0.085f, 0.085f, 0.011f)));
		}
		AddInstances(CylinderMesh, ShockSpring, Coils, Gold);
		AddPart(CylinderMesh, ShockSpring, FVector(0.0, 0.0, -Length0 + 4.0), FRotator::ZeroRotator, FVector(0.075f, 0.075f, 0.02f), Gold);
		AddPart(CylinderMesh, ShockSpring, FVector(0.0, 0.0, -Length0), FRotator(0.f, 0.f, 90.f), FVector(0.045f, 0.045f, 0.07f), Dark);
	}

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
	for (const float Side : { -1.f, 1.f })
	{
		// swingarm pivot plates either side of the pivot bolt
		AddPart(CubeMesh, Body, SwingarmPivot + FVector(0.0, Side * 13.5f, 1.0), FRotator(8.f, 0.f, 0.f),
			FVector(0.13f, 0.012f, 0.16f), Alloy);
	}

	// ---- engine: cases, finned cylinder, head, covers, radiator, controls
	AddPart(CubeMesh, Body, FVector(-2.0, 0.0, 48.0), FRotator::ZeroRotator, FVector(0.36f, 0.25f, 0.30f), Dark);
	AddPart(CubeMesh, Body, FVector(2.0, 0.0, 35.0), FRotator(10.f, 0.f, 0.f), FVector(0.30f, 0.22f, 0.12f), Dark);
	AddPart(CylinderMesh, Body, FVector(-4.0, 14.0, 46.0), FRotator(0.f, 0.f, 90.f),
		FVector(0.22f, 0.22f, 0.045f), Metal);                                          // clutch cover
	AddPart(CylinderMesh, Body, FVector(-4.0, -14.0, 46.0), FRotator(0.f, 0.f, 90.f),
		FVector(0.18f, 0.18f, 0.038f), Metal);                                          // ignition cover
	{
		// cover bolts round the clutch cover
		TArray<FTransform> Bolts;
		for (int32 i = 0; i < 8; ++i)
		{
			const float Rad = 2.f * PI * i / 8.f;
			Bolts.Add(FTransform(FRotator(0.f, 0.f, 90.f), FVector(-4.0 + 9.5 * FMath::Cos(Rad), 16.4, 46.0 + 9.5 * FMath::Sin(Rad)),
				FVector(0.012f, 0.012f, 0.01f)));
		}
		AddInstances(CylinderMesh, Body, Bolts, Dark);
	}
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
	// carburettor / throttle body and intake boot behind the cylinder
	AddRod(Body, FVector(2.0, 0.0, 76.0), FVector(-12.0, 0.0, 80.0), 7.f, Rubber);
	AddPart(CylinderMesh, Body, FVector(-7.0, 0.0, 78.5), FRotator(0.f, 0.f, 90.f), FVector(0.07f, 0.07f, 0.12f), Alloy);

	// Radiator and hoses.
	AddPart(CubeMesh, Body, FVector(31.0, 0.0, 68.0), FRotator(12.f, 0.f, 0.f), FVector(0.05f, 0.34f, 0.24f), Dark);
	for (const float Side : { -1.f, 1.f })
	{
		AddPart(CubeMesh, Body, FVector(31.0, Side * 17.0f, 68.0), FRotator(12.f, 0.f, 0.f),
			FVector(0.06f, 0.025f, 0.24f), Metal);
	}
	AddRod(Body, FVector(30.0, 8.0, 79.0), FVector(12.0, 8.0, 82.0), 3.4f, Rubber);
	AddRod(Body, FVector(30.0, -8.0, 57.0), FVector(8.0, -7.0, 52.0), 3.4f, Rubber);

	// Skid plate, foot pegs (with cleats), gear and brake pedals, kick-start, folded side stand.
	AddPart(CubeMesh, Body, FVector(4.0, 0.0, 31.0), FRotator(8.f, 0.f, 0.f), FVector(0.40f, 0.25f, 0.03f), Metal);
	{
		TArray<FTransform> Cleats;
		for (const float Side : { -1.f, 1.f })
		{
			AddRod(Body, FVector(-2.0, 12.0 * Side, 43.0), FVector(6.0, 12.0 * Side, 40.0), 2.5f, Dark);
			AddPart(CubeMesh, Body, FVector(PegTop.X, (PegTop.Y + 0.5f) * Side, 40.0), FRotator::ZeroRotator,
				FVector(0.055f, 0.12f, 0.025f), Metal);
			for (int32 i = 0; i < 4; ++i)
			{
				Cleats.Add(FTransform(FRotator::ZeroRotator, FVector(PegTop.X, (11.5f + 3.2f * i) * Side, PegTop.Z - 0.4f),
					FVector(0.06f, 0.006f, 0.012f)));
			}
		}
		AddInstances(CubeMesh, Body, Cleats, Dark);
	}
	AddRod(Body, FVector(0.0, -15.0, 40.0), FVector(10.0, -21.0, 35.0), 2.0f, Metal);
	AddPart(CubeMesh, Body, FVector(12.5, -22.0, 34.0), FRotator::ZeroRotator, FVector(0.085f, 0.030f, 0.028f), Dark);
	AddRod(Body, FVector(-2.0, 15.0, 38.0), FVector(12.0, 20.0, 33.0), 2.0f, Metal);
	AddPart(CubeMesh, Body, FVector(14.0, 21.0, 32.0), FRotator::ZeroRotator, FVector(0.085f, 0.030f, 0.028f), Dark);
	AddRod(Body, FVector(2.0, 16.0, 48.0), FVector(-6.0, 20.0, 34.0), 2.4f, Metal);
	AddPart(CubeMesh, Body, FVector(-8.0, 20.0, 32.0), FRotator(0.f, -20.f, 0.f), FVector(0.10f, 0.030f, 0.030f), Dark);
	AddRod(Body, FVector(-8.0, -12.0, 37.0), FVector(-34.0, -15.5, 40.0), 2.2f, Dark);
	AddPart(CubeMesh, Body, FVector(-35.0, -15.8, 40.0), FRotator(4.f, 0.f, 0.f), FVector(0.05f, 0.02f, 0.03f), Dark);

	// ---- exhaust: a header that curls out of the port and back along the right side, silencer, heat shield, tip
	AddTube(Body, { FVector(17.0, 2.0, 72.0), FVector(23.5, 6.0, 64.0), FVector(22.0, 11.5, 53.0), FVector(9.0, 15.5, 49.5),
		FVector(-8.0, 17.0, 58.0), FVector(-40.0, 17.0, 79.0) }, 5.6f, Metal);
	AddRod(Body, FVector(-38.0, 17.0, 79.0), FVector(-80.0, 17.0, 93.0), 13.0f, Dark);
	AddRod(Body, FVector(-80.0, 17.0, 93.0), FVector(-85.0, 17.0, 95.0), 8.0f, Metal);
	AddPart(CubeMesh, Body, FVector(-34.0, 17.0, 92.0), FRotator(-26.f, 0.f, 0.f), FVector(0.25f, 0.065f, 0.018f), Metal);
	AddPart(CubeMesh, Body, FVector(-6.0, 19.6, 59.0), FRotator(-27.f, 0.f, 0.f), FVector(0.16f, 0.010f, 0.06f), Alloy);
	for (const float X : { -48.f, -66.f })
	{
		AddPart(CylinderMesh, Body, FVector(X, 17.0, (X < -60.f ? 89.f : 84.f)), FRotator(22.f, 0.f, 0.f),
			FVector(0.145f, 0.145f, 0.012f), Metal);
	}

	// ---- bodywork: tank, louvred shrouds, seat, side panels, fenders, tail light
	AddPart(SphereMesh, Body, FVector(17.0, 0.0, 91.0), FRotator(-5.f, 0.f, 0.f), FVector(0.50f, 0.29f, 0.24f), PaintMaterial);
	AddPart(CubeMesh, Body, FVector(13.0, 0.0, 100.0), FRotator(-4.f, 0.f, 0.f), FVector(0.31f, 0.21f, 0.055f), PaintMaterial);
	AddPart(CylinderMesh, Body, FVector(9.0, 0.0, 103.0), FRotator::ZeroRotator, FVector(0.085f, 0.085f, 0.022f), Metal);
	AddPart(CylinderMesh, Body, FVector(9.0, 0.0, 105.0), FRotator::ZeroRotator, FVector(0.025f, 0.025f, 0.018f), Dark);
	{
		TArray<FTransform> Louvres;
		for (const float Side : { -1.f, 1.f })
		{
			AddPart(CubeMesh, Body, FVector(28.0, 15.0 * Side, 80.0), FRotator(18.f, 0.f, 0.f),
				FVector(0.34f, 0.035f, 0.28f), PaintMaterial);
			AddPart(CubeMesh, Body, FVector(31.0, 16.9f * Side, 82.0), FRotator(18.f, 0.f, 0.f),
				FVector(0.15f, 0.006f, 0.12f), Dark);
			for (int32 i = 0; i < 5; ++i)
			{
				Louvres.Add(FTransform(FRotator(18.f, 0.f, 0.f), FVector(26.0 + 2.6 * i, 17.15 * Side, 81.0 + 0.85 * i),
					FVector(0.008f, 0.006f, 0.11f)));
			}
			AddPart(CubeMesh, Body, FVector(23.0, 17.2f * Side, 73.0), FRotator(18.f, 0.f, 0.f),
				FVector(0.12f, 0.010f, 0.065f), White);
			AddPart(CubeMesh, Body, FVector(-36.0, 12.0 * Side, 85.0), FRotator(-6.f, 0.f, 0.f),
				FVector(0.28f, 0.030f, 0.17f), White);
			AddPart(CubeMesh, Body, FVector(-36.0, 13.6f * Side, 85.0), FRotator(-6.f, 0.f, 0.f),
				FVector(0.22f, 0.008f, 0.13f), Dark);
		}
		AddInstances(CubeMesh, Body, Louvres, PaintMaterial);
	}
	// Seat: a long flat bench that rises onto the tank at the front and rounds off at the back.
	AddPart(CubeMesh, Body, FVector(-16.0, 0.0, 96.0), FRotator(-3.f, 0.f, 0.f), FVector(0.46f, 0.21f, 0.075f), Seat);
	AddPart(CubeMesh, Body, FVector(-44.0, 0.0, 98.0), FRotator(-4.f, 0.f, 0.f), FVector(0.32f, 0.19f, 0.065f), Seat);
	AddPart(SphereMesh, Body, FVector(6.0, 0.0, 99.5), FRotator(-12.f, 0.f, 0.f), FVector(0.16f, 0.20f, 0.075f), Seat);
	AddPart(SphereMesh, Body, FVector(-59.0, 0.0, 99.2), FRotator(-6.f, 0.f, 0.f), FVector(0.10f, 0.18f, 0.06f), Seat);
	AddPart(CubeMesh, Body, FVector(-20.0, 0.0, 99.9), FRotator(-3.f, 0.f, 0.f), FVector(0.50f, 0.014f, 0.006f), Dark);   // seat seam
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

	// ---- front end. FrontPivot turns about the raked steering axis and carries the clamps, stanchions, bars,
	// plate, headlight and the high fender; FrontLower (sliders, wheel, caliper) telescopes along the fork.
	FrontPivot = AddPivot(Body, SteeringHead);
	FrontLower = AddPivot(FrontPivot, FVector::ZeroVector);
	const FVector FrontHub(FrontHubX - SteeringHead.X, 0.0, R - SteeringHead.Z);
	FrontWheel = BuildWheel(FrontLower, FrontHub, false, Rubber, Metal, Dark, Metal, Gold);

	const FVector ForkMid(12.0f, 0.0f, -24.0f);
	for (const float Side : { -10.f, 10.f })
	{
		const FVector Top = ForkTop + FVector(0.0, Side, 0.0);
		const FVector Mid = ForkMid + FVector(0.0, Side, 0.0);
		const FVector Hub = FrontHub + FVector(0.0, Side, 0.0);
		// The gold stanchion is clamped to the steering; the dark slider rides up over it when the fork compresses.
		AddRod(FrontPivot, Top, Mid + FVector(7.0f, 0.0f, -16.0f), 7.5f, Gold);
		AddRod(FrontLower, Mid + FVector(-3.0f, 0.0f, 7.0f), Hub, 8.5f, Dark);
		AddPart(CylinderMesh, FrontLower, Mid + FVector(-1.0f, 0.0f, 3.0f), FRotator(-25.f, 0.f, 0.f),
			FVector(0.115f, 0.115f, 0.018f), Gold);
		// A white fork guard, aligned with the slider instead of a paddle across it.
		const FVector ForkDir = Hub - Mid;
		const FRotator ForkGuardRot = FRotationMatrix::MakeFromZ(ForkDir).Rotator();
		AddPart(CubeMesh, FrontLower, Mid + ForkDir * 0.45f + FVector(2.0f, Side * 0.9f, 0.0f),
			ForkGuardRot, FVector(0.055f, 0.035f, 0.22f), White);
		AddPart(CubeMesh, FrontLower, Hub, FRotator::ZeroRotator, FVector(0.05f, 0.05f, 0.035f), Metal);
		// fork caps on the top clamp
		AddPart(CylinderMesh, FrontPivot, Top + FVector(0.0, 0.0, 1.5), FRotator(-25.f, 0.f, 0.f), FVector(0.06f, 0.06f, 0.02f), Alloy);
	}
	AddRod(FrontLower, FrontHub + FVector(0.0, -16.0f, 0.0), FrontHub + FVector(0.0, 16.0f, 0.0), 1.6f, Metal);

	// Triple clamps and steering stem.
	AddPart(CubeMesh, FrontPivot, FVector(-2.0, 0.0, 10.0), FRotator::ZeroRotator, FVector(0.10f, 0.29f, 0.040f), Alloy);
	AddPart(CubeMesh, FrontPivot, FVector(4.0, 0.0, -14.0), FRotator::ZeroRotator, FVector(0.10f, 0.27f, 0.050f), Alloy);
	AddRod(FrontPivot, FVector(-2.0, 0.0, 12.0), FVector(8.0, 0.0, 2.0), 3.0f, Metal);

	// Handlebar: a bent bar - flat through the clamps, rising and sweeping back to the grips - with a crossbar
	// and pad, rubber grips, bar ends, levers on their perches and hand guards in front of the hands.
	{
		const FVector BarClamp(-6.0, 15.0, 17.0);
		const FVector BarBend(-8.5, 23.0, 22.5);
		const FVector BarEnd(-11.8, 41.5, 25.2);
		auto M = [](const FVector& V, float Side) { return FVector(V.X, V.Y * Side, V.Z); };
		AddTube(FrontPivot, { M(BarEnd, -1.f), M(BarBend, -1.f), M(BarClamp, -1.f), BarClamp, BarBend, BarEnd }, 3.0f, Alloy);
		AddPart(CubeMesh, FrontPivot, FVector(-6.0, 0.0, 17.0), FRotator::ZeroRotator, FVector(0.08f, 0.16f, 0.05f), Dark);
		AddRod(FrontPivot, FVector(-8.0, -20.0, 21.0), FVector(-8.0, 20.0, 21.0), 2.2f, Alloy);
		AddPart(CubeMesh, FrontPivot, FVector(-8.0, 0.0, 21.0), FRotator::ZeroRotator, FVector(0.05f, 0.18f, 0.05f), Seat);
		const FVector BarDir = (BarEnd - BarBend).GetSafeNormal();
		for (const float Side : { -1.f, 1.f })
		{
			const FVector Dir = M(BarDir, Side);
			const FVector GripIn = M(FMath::Lerp(BarBend, BarEnd, 0.3f), Side);
			const FVector End = M(BarEnd, Side);
			AddRod(FrontPivot, GripIn, End, 4.6f, Rubber);
			AddPart(CubeMesh, FrontPivot, GripIn + Dir * 1.0f, FRotationMatrix::MakeFromY(Dir).Rotator(),
				FVector(0.055f, 0.012f, 0.055f), Dark);                                   // grip flange
			AddRod(FrontPivot, End, End + Dir * 1.6f, 3.4f, Dark);                         // bar end
			// lever perch just inboard of the grip, lever reaching out in front of the fingers
			const FVector Perch = GripIn - Dir * 2.6f;
			AddPart(CubeMesh, FrontPivot, Perch, FRotationMatrix::MakeFromY(Dir).Rotator(), FVector(0.04f, 0.035f, 0.035f), Dark);
			AddTube(FrontPivot, { Perch + FVector(1.5, 0.0, -0.5), Perch + FVector(4.5, Side * 4.0, -1.0), End + FVector(6.0, -Side * 1.5f, -2.5) },
				1.2f, Alloy);
			// hand guard: a plastic shell ahead of the hand on an alloy spar from the clamp to the bar end
			AddPart(CubeMesh, FrontPivot, M(FVector(-4.2, 34.0, 26.5), Side), FRotationMatrix::MakeFromY(Dir).Rotator(),
				FVector(0.022f, 0.15f, 0.085f), PaintMaterial);
			AddPart(CubeMesh, FrontPivot, M(FVector(-6.5, 40.5, 26.0), Side), FRotationMatrix::MakeFromY(Dir).Rotator() + FRotator(0.f, 35.f * Side, 0.f),
				FVector(0.05f, 0.03f, 0.075f), PaintMaterial);
			AddTube(FrontPivot, { M(FVector(-4.0, 16.0, 16.0), Side), M(FVector(1.5, 30.0, 22.0), Side), M(FVector(-10.0, 43.5, 25.2), Side) },
				1.5f, Alloy);
			// cable from the perch down to the frame
			AddRod(FrontPivot, Perch, M(FVector(2.0, 15.0, -12.0), Side), 0.65f, Dark);
		}
		// front brake master cylinder and reservoir on the right perch
		const FVector RightPerch = FMath::Lerp(BarBend, BarEnd, 0.3f) - BarDir * 2.6f;
		AddPart(CylinderMesh, FrontPivot, RightPerch + FVector(0.5, -1.5, 2.5), FRotator(10.f, 0.f, 0.f), FVector(0.05f, 0.05f, 0.06f), Dark);
		AddPart(CubeMesh, FrontPivot, RightPerch + FVector(0.0, -2.0, 5.0), FRotator(10.f, 0.f, 0.f), FVector(0.035f, 0.04f, 0.03f), Metal);
	}
	// Throttle cable.
	AddRod(FrontPivot, FVector(2.0, 14.0, -9.0), FVector(-7.0, 27.0, 22.0), 0.55f, Dark);

	// High front fender on the lower clamp, clear of the tyre at full fork travel: a three-piece arc and its stays.
	{
		const float FenderR = R + 11.0f;
		struct FFenderSegment { float Angle; float Pitch; float Length; };
		static const FFenderSegment Segments[] = {
			{ 122.0f, -32.0f, 25.0f },
			{ 90.0f, 0.0f, 30.0f },
			{ 58.0f, 32.0f, 26.0f }
		};
		for (const FFenderSegment& Segment : Segments)
		{
			const float Rad = FMath::DegreesToRadians(Segment.Angle);
			const FVector Pos = FrontHub + FVector(FenderR * FMath::Cos(Rad), 0.0f, FenderR * FMath::Sin(Rad));
			AddPart(CubeMesh, FrontPivot, Pos, FRotator(Segment.Pitch, 0.f, 0.f),
				FVector(Segment.Length / 100.f, 0.155f, 0.026f), PaintMaterial);
		}
		for (const float Side : { -1.f, 1.f })
		{
			AddRod(FrontPivot, FVector(4.0, 6.0 * Side, -15.0), FrontHub + FVector(FenderR * -0.5f, 6.0 * Side, FenderR * 0.85f), 1.6f, Dark);
		}
	}

	// Number plate/headlight mask; the lens and spot sit ahead of it.
	AddPart(CubeMesh, FrontPivot, FVector(8.8, 0.0, -5.0), FRotator(18.f, 0.f, 0.f), FVector(0.030f, 0.285f, 0.265f), Dark);
	AddPart(CubeMesh, FrontPivot, FVector(9.1, 0.0, -5.0), FRotator(18.f, 0.f, 0.f), FVector(0.030f, 0.260f, 0.240f), White);
	AddPart(SphereMesh, FrontPivot, FVector(12.6, 0.0, -6.0), FRotator::ZeroRotator, FVector(0.075f, 0.13f, 0.10f), Lamp);
	AddPart(CylinderMesh, FrontPivot, FVector(13.0, 0.0, -6.0), FRotator(0.f, 90.f, 0.f), FVector(0.225f, 0.225f, 0.016f), Dark);
	AddPart(CylinderMesh, FrontPivot, FVector(13.2, 0.0, -6.0), FRotator(0.f, 90.f, 0.f), FVector(0.20f, 0.20f, 0.012f), Lamp);
	AddPart(CubeMesh, FrontPivot, FVector(9.0, 0.0, 1.0), FRotator(18.f, 0.f, 0.f), FVector(0.09f, 0.24f, 0.045f), Dark);
	// A small peak over the light, like a dirt-bike headlight mask.
	AddPart(CubeMesh, FrontPivot, FVector(11.0, 0.0, 4.0), FRotator(34.f, 0.f, 0.f), FVector(0.17f, 0.22f, 0.020f), PaintMaterial);

	// Brake line from the caliper up the fork leg (moves with the slider), then up to the master cylinder.
	AddRod(FrontLower, FrontHub + FVector(7.0, -13.0, -4.0), ForkMid + FVector(-4.0, -13.0, 4.0), 0.65f, Dark);
	AddRod(FrontPivot, FVector(6.0, -13.0, 2.0), FVector(-6.0, 22.0, 24.0), 0.65f, Dark);

	// ---- lights
	Headlight = NewObject<USpotLightComponent>(GetOwner(), NAME_None, RF_Transient);
	Headlight->SetupAttachment(FrontPivot);
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
		EngineAudio->SetupAttachment(Sprung);
		EngineAudio->SetRelativeLocation(FVector(-45.0, 14.0, 78.0) * ModelScale);
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
		// it settles onto its springs as it appears
		RearTravel = 6.f;
		FrontTravel = 4.f;
		RearTravelVelocity = FrontTravelVelocity = 0.f;
		bWasAirborne = false;
		Body->SetRelativeScale3D(FVector(0.01f * ModelScale));
		Gear = 1;
		EngineRPM = IdleRPM;
		ShiftTimer = 0.f;
		BackfireCooldown = 0.f;
		LastForwardSpeed = 0.f;
		ExhaustFlashTimer = 0.f;
		SteerDegrees = 0.f;
		// the rider gets on with a foot on the ground
		AirTime = LandHold = 0.f;
		StandAlpha = TuckAlpha = DriveAlpha = 0.f;
		FootDownAlpha = 1.f;
		bFootDownWanted = true;
		RiderSink = RiderSinkVelocity = 0.f;
		LeanShown = 0.f;
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

FQuat UDAMotorcycleComponent::SteerRotation() const
{
	// The steering axis runs up the fork (raked back); turning about it, not about the vertical, tips the
	// wheel and the bars into the turn like a real front end.
	return FQuat(-ForkAxisDown(), FMath::DegreesToRadians(SteerDegrees));
}

FVector UDAMotorcycleComponent::BodyToMount(const FVector& BodyPoint) const
{
	// Body and the rider mount share the sprung chassis; the body is scaled by ModelScale about its origin.
	return (BodyPoint - RiderSeat) * ModelScale;
}

void UDAMotorcycleComponent::GetRiderTargets(FDARiderTargets& Out) const
{
	Out = FDARiderTargets();
	if (!bBuilt || !bDeployed || !RiderMount)
	{
		return;
	}
	Out.bValid = true;
	const FVector Mirror(1.0, -1.0, 1.0);
	// The hips slide towards the foot that goes down and drop off the seat's crown.
	Out.Seat = BodyToMount(SeatPoint) + FVector(0.0, -FootDownHipSlide * FootDownAlpha, -FootDownHipDrop * FootDownAlpha);
	Out.PegRight = BodyToMount(PegTop);
	Out.PegLeft = BodyToMount(PegTop * Mirror);
	const FQuat Steer = SteerRotation();
	Out.GripRight = BodyToMount(SteeringHead + Steer.RotateVector(GripCentre));
	Out.GripLeft = BodyToMount(SteeringHead + Steer.RotateVector(GripCentre * Mirror));
	// The ground beside the bike: the bike's root sits on it, under the leaning, sprung chassis.
	Out.GroundLeft = RiderMount->GetComponentTransform().InverseTransformPosition(
		GetComponentTransform().TransformPosition(FootGround * ModelScale));
	Out.FootDown = FootDownAlpha;
	Out.Stand = StandAlpha;
	Out.Tuck = TuckAlpha;
	Out.Drive = DriveAlpha;
	Out.Sink = RiderSink;
	// Dirt style: the upper body stays more upright than the leaning bike, and upright over the foot at a stop;
	// the head takes out part of what is left.
	const float StopLean = -FootDownLean * FootDownAlpha;
	const float TurnLean = LeanShown - StopLean;
	Out.BodyRoll = -0.3f * TurnLean - 0.85f * StopLean;
	Out.HeadRoll = -0.35f * (LeanShown + Out.BodyRoll);
}

void UDAMotorcycleComponent::UpdateSuspension(float DeltaTime, const FDABikePose& Pose, float Acceleration, bool bBraking)
{
	const float MS = ModelScale;
	const float Speed = FMath::Abs(Pose.ForwardSpeed);
	const float Wheelbase = (FrontHubX - RearHubX) * MS;

	// The ground under the wheels: a few overlaid swells by distance, so the front wheel meets each bump first and
	// the rear one a wheelbase later. Rougher (relative to the springs) the faster the bike goes.
	Rolled += Pose.ForwardSpeed * DeltaTime;
	auto Ground = [](float S)
	{
		return 0.6f * FMath::Sin(S * 0.021f) + 0.4f * FMath::Sin(S * 0.047f + 1.3f) + 0.25f * FMath::Sin(S * 0.093f + 0.4f);
	};
	const float Speed01 = FMath::Clamp(Speed / 1500.f, 0.f, 1.f);
	const float Rough = Pose.bAirborne ? 0.f : (0.3f + 0.9f * Speed01) * FMath::Clamp(Speed / 150.f, 0.f, 1.f);
	float FrontTarget = Rough * Ground(Rolled);
	float RearTarget = Rough * Ground(Rolled - Wheelbase);
	if (Pose.bAirborne)
	{
		// both ends top out in the air
		FrontTarget = RearTarget = MinTravel + 1.f;
	}
	else
	{
		// Weight transfer: the fork dives on the brakes, the rear squats under power and the front lifts a little.
		const float Squat = FMath::Clamp(Acceleration * 0.0016f, -1.5f, 3.f);
		const float Dive = bBraking ? 6.f : FMath::Clamp(-Acceleration * 0.0012f, 0.f, 2.f);
		FrontTarget += Dive - 0.5f * FMath::Max(Squat, 0.f);
		RearTarget += Squat - 0.3f * Dive;
	}
	if (bWasAirborne && !Pose.bAirborne)
	{
		// landing: the longer the flight, the harder both ends bottom
		const float Impact = FMath::Clamp(0.35f + AirTime * 1.4f, 0.35f, 1.3f);
		FrontTravelVelocity += 95.f * Impact;
		RearTravelVelocity += 150.f * Impact;
	}
	auto Spring = [DeltaTime](float& Travel, float& Velocity, float Target, float Stiffness, float Damping)
	{
		Velocity += ((Target - Travel) * Stiffness - Velocity * Damping) * DeltaTime;
		Travel += Velocity * DeltaTime;
		if (Travel > MaxTravel || Travel < MinTravel)
		{
			Travel = FMath::Clamp(Travel, MinTravel, MaxTravel);
			Velocity = 0.f;   // on the bump / top-out stop
		}
	};
	Spring(FrontTravel, FrontTravelVelocity, FrontTarget, FrontStiffness, FrontDamping);
	Spring(RearTravel, RearTravelVelocity, RearTarget, RearStiffness, RearDamping);

	// Chassis heave and pitch from the travel at each axle (the rider rides on it).
	const float Xr = RearHubX * MS;
	const float Xf = FrontHubX * MS;
	const float PitchRad = FMath::Atan2(RearTravel - FrontTravel, Xf - Xr);
	const float Heave = -RearTravel - Xr * FMath::Tan(PitchRad);
	const FRotator SprungRot(FMath::RadiansToDegrees(PitchRad), 0.f, 0.f);
	Sprung->SetRelativeLocationAndRotation(FVector(0.0, 0.0, Heave), SprungRot);

	// Keep the wheels on the ground: where each hub has to be in the chassis' (body) space.
	const FTransform SprungToTilt(SprungRot, FVector(0.0, 0.0, Heave));
	const FVector RearHub = SprungToTilt.InverseTransformPosition(FVector(Xr, 0.0, WheelRadius * MS)) / MS;
	const FVector FrontHub = SprungToTilt.InverseTransformPosition(FVector(Xf, 0.0, WheelRadius * MS)) / MS;

	// Rear: the swingarm swings about its pivot to reach the hub; the shock follows its linkage.
	const FVector RestArm = FVector(RearHubX, 0.0, WheelRadius) - SwingarmPivot;
	const FVector WantArm = RearHub - SwingarmPivot;
	const float Swing = FMath::Clamp(FMath::FindDeltaAngleDegrees(
		FMath::RadiansToDegrees(FMath::Atan2(static_cast<float>(RestArm.Z), static_cast<float>(RestArm.X))),
		FMath::RadiansToDegrees(FMath::Atan2(static_cast<float>(WantArm.Z), static_cast<float>(WantArm.X)))), -16.f, 12.f);
	const FRotator SwingRot(Swing, 0.f, 0.f);
	Swingarm->SetRelativeRotation(SwingRot);
	if (ShockAim && ShockSpring)
	{
		const FVector Bottom = SwingarmPivot + SwingRot.RotateVector(ShockBottom - SwingarmPivot);
		const FVector Axis = ShockTop - Bottom;
		const float Length0 = static_cast<float>((ShockTop - ShockBottom).Size());
		ShockAim->SetRelativeRotation(FRotationMatrix::MakeFromZ(Axis).Rotator());
		ShockSpring->SetRelativeScale3D(FVector(1.0, 1.0, Axis.Size() / FMath::Max(Length0, 1.f)));
	}

	// Front: the sliders and wheel telescope along the fork (parallel to the steering axis, so the steering
	// does not change the slide direction).
	const FVector Down = ForkAxisDown();
	const float Rise = static_cast<float>(FrontHub.Z) - WheelRadius;
	const float Slide = FMath::Clamp(Rise / FMath::Max(0.2f, static_cast<float>(-Down.Z)), -4.f, 13.f);
	FrontLower->SetRelativeLocation(-Down * Slide);
}

void UDAMotorcycleComponent::UpdateRiderStyle(float DeltaTime, const FDABikePose& Pose, float Acceleration, bool bBraking)
{
	const float Speed = FMath::Abs(Pose.ForwardSpeed);
	if (Pose.bAirborne)
	{
		AirTime += DeltaTime;
	}
	else
	{
		if (bWasAirborne)
		{
			// legs soak up the landing; a real jump keeps the rider up on the pegs for a moment
			RiderSinkVelocity += FMath::Clamp(AirTime * 230.f, 15.f, 160.f);
			if (AirTime > 0.25f)
			{
				LandHold = 0.45f;
			}
		}
		AirTime = 0.f;
	}
	LandHold = FMath::Max(0.f, LandHold - DeltaTime);

	// Up on the pegs over jumps and through the landing.
	const float StandTarget = ((Pose.bAirborne && AirTime > 0.12f) || LandHold > 0.f) ? 1.f : 0.f;
	StandAlpha = FMath::FInterpTo(StandAlpha, StandTarget, DeltaTime, StandTarget > StandAlpha ? 8.f : 4.f);

	// Chest down behind the plate when boosting at speed (and a little at a fast cruise).
	const float TuckTarget = (Pose.bBoosting && Speed > 1300.f ? 1.f : FMath::Clamp((Speed - 1600.f) / 600.f, 0.f, 0.4f)) * (1.f - StandAlpha);
	TuckAlpha = FMath::FInterpTo(TuckAlpha, TuckTarget, DeltaTime, 3.f);

	// Left foot down when stopped; back on the peg as soon as the bike pulls away.
	if (!Pose.bAirborne && Speed < 45.f && Pose.Throttle < 0.1f)
	{
		bFootDownWanted = true;
	}
	else if (Pose.bAirborne || Speed > 110.f || Pose.Throttle > 0.2f)
	{
		bFootDownWanted = false;
	}
	FootDownAlpha = FMath::FInterpTo(FootDownAlpha, bFootDownWanted ? 1.f : 0.f, DeltaTime, bFootDownWanted ? 4.5f : 8.f);

	// Weight forward under power, back and braced on the brakes.
	const float DriveTarget = bBraking ? -1.f : FMath::Clamp(Acceleration / 1100.f, -0.6f, 1.f) * (Pose.Throttle > 0.1f ? 1.f : 0.5f);
	DriveAlpha = FMath::FInterpTo(DriveAlpha, DriveTarget, DeltaTime, 5.f);

	RiderSinkVelocity += (-RiderSink * 140.f - RiderSinkVelocity * 15.f) * DeltaTime;
	RiderSink = FMath::Clamp(RiderSink + RiderSinkVelocity * DeltaTime, -3.f, 14.f);
}

void UDAMotorcycleComponent::UpdateDrivetrain(float DeltaTime, const FDABikePose& Pose, float Acceleration)
{
	const float Speed = FMath::Abs(Pose.ForwardSpeed);
	const float Throttle = FMath::Clamp(Pose.Throttle, 0.f, 1.f);
	const bool bGrounded = !Pose.bAirborne;
	const float WheelRPM = Speed / FMath::Max(2.f * PI * WheelRadius * ModelScale, 1.f) * 60.f;

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
		Body->SetRelativeScale3D(FVector(FMath::Max(0.01f, Back) * ModelScale));
	}

	const float Acceleration = (Pose.ForwardSpeed - LastForwardSpeed) / DeltaTime;
	const bool bBraking = Pose.bBraking || (Pose.Throttle < 0.05f && Acceleration < -260.f);
	UpdateDrivetrain(DeltaTime, Pose, Acceleration);

	// Wheels: rolling without slipping (a positive angle about +Y rolls the wheel forwards). The chain moves
	// with the rear sprocket: the top run is pulled forwards, the bottom run goes back.
	const float Radius = FMath::Max(WheelRadius * ModelScale, 1.f);
	const float Roll = Pose.ForwardSpeed / Radius * DeltaTime;
	WheelAngle = FMath::Fmod(WheelAngle + Roll, 2.f * PI);
	const FQuat Spin(FVector::YAxisVector, WheelAngle);
	RearWheel->SetRelativeRotation(Spin);
	FrontWheel->SetRelativeRotation(Spin);
	ChainTravel = FMath::Fmod(ChainTravel + Roll * RearSprocketShare * WheelRadius, ChainPitch);
	const float ChainPhase = ChainTravel < 0.f ? ChainTravel + ChainPitch : ChainTravel;
	if (ChainLinksTop)
	{
		ChainLinksTop->SetRelativeLocation(ChainStart[0] + ChainDir[0] * (ChainPitch - ChainPhase));
	}
	if (ChainLinksBottom)
	{
		ChainLinksBottom->SetRelativeLocation(ChainStart[1] + ChainDir[1] * ChainPhase);
	}

	// Steering about the raked steering axis.
	SteerDegrees = FMath::Clamp(Pose.Steer, -1.f, 1.f) * MaxSteerAngle;
	FrontPivot->SetRelativeRotation(SteerRotation());

	// Both suspensions (the chassis heaves and pitches, the wheels stay down) and how the rider rides.
	UpdateSuspension(DeltaTime, Pose, Acceleration, bBraking);
	UpdateRiderStyle(DeltaTime, Pose, Acceleration, bBraking);
	bWasAirborne = Pose.bAirborne;

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

	// Lean about the tyre contact line (plus the lean onto the rider's foot at a stop), pitch about the point
	// between the wheels; squat and dive come from the suspension itself.
	LeanShown = FMath::Clamp(Pose.Lean - FootDownLean * FootDownAlpha, -45.f, 45.f);
	Tilt->SetRelativeRotation(FRotator(FMath::Clamp(Pose.Pitch, -42.f, 42.f), 0.f, LeanShown));

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
