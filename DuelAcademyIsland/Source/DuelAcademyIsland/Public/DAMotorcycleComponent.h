// Duel Academy Island - the student's all-terrain motorcycle (procedural parts + code animation).

#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "DAMotorcycleComponent.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class USpotLightComponent;

/** Per-tick pose input for the motorcycle; all angles in degrees. */
struct FDABikePose
{
	/** Signed ground speed along the bike's heading (cm/s); drives the wheel spin. */
	float ForwardSpeed = 0.f;
	/** -1 (full left) .. 1 (full right) handlebar angle. */
	float Steer = 0.f;
	/** Roll into the turn; positive leans towards the bike's right (+Y). */
	float Lean = 0.f;
	/** Nose-up pitch (slope of the ground, or the flight path while airborne). */
	float Pitch = 0.f;
	/** 0 = day, 1 = night: scales the headlight. */
	float NightAlpha = 0.f;
	bool bAirborne = false;
};

/**
 * A dirt bike assembled at runtime from the engine's basic shapes, so it needs
 * no imported assets: knobby wheels with spinning spokes, a steering front end
 * (fork, bars, number plate, headlight), long-travel suspension that sags on
 * landings, and dorm-coloured plastics.
 *
 * Attach it at the bottom of the capsule; it faces the owner's +X. The rider
 * (the avatar component) is attached to GetRiderMount() while riding, so it
 * leans and pitches together with the bike. Purely visual: no collision.
 */
UCLASS(ClassGroup = (DuelAcademy), meta = (BlueprintSpawnableComponent))
class DUELACADEMYISLAND_API UDAMotorcycleComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	UDAMotorcycleComponent();

	virtual void BeginPlay() override;

	/** Show (with a quick pop-in) or hide the bike. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Motorcycle")
	void SetDeployed(bool bOn);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Motorcycle")
	bool IsDeployed() const { return bDeployed; }

	/** Plastics colour (the character passes its dorm colour). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Motorcycle")
	void SetPaint(const FLinearColor& Color);

	/** Advance the pop-in, wheels, steering, lean, pitch and suspension. The owner calls this every tick
	 *  while the bike is deployed; the component itself never ticks. */
	void UpdateRide(float DeltaTime, const FDABikePose& Pose);

	/** The rider's root: on the seat line, at ground level of the (tilted) bike. */
	USceneComponent* GetRiderMount() const { return RiderMount; }

	/** Height (cm, above the rider mount) where the rider's hips belong. */
	float GetRiderHipHeight() const { return SeatHeight + 10.f; }

	/** Wheel radius (cm); the hub height above the ground. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float WheelRadius = 36.f;

	/** Seat top height above the ground (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float SeatHeight = 98.f;

	/** Full handlebar lock (degrees). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float MaxSteerAngle = 28.f;

private:
	UStaticMeshComponent* AddPart(UStaticMesh* Mesh, USceneComponent* Parent, const FVector& Location,
		const FRotator& Rotation, const FVector& Scale, UMaterialInterface* Material);
	/** A cylinder of the given diameter spanning A..B (parent space). */
	UStaticMeshComponent* AddRod(USceneComponent* Parent, const FVector& A, const FVector& B, float Diameter,
		UMaterialInterface* Material);
	USceneComponent* AddPivot(USceneComponent* Parent, const FVector& Location);
	USceneComponent* BuildWheel(USceneComponent* Parent, const FVector& Hub, UMaterialInterface* Rubber,
		UMaterialInterface* Rim, UMaterialInterface* Dark);
	UMaterialInstanceDynamic* MakeMaterial(UMaterialInterface* Base, const FLinearColor& Tint, float Roughness,
		float Metallic, float EmissiveStrength = -1.f);
	void Build();

	UPROPERTY() TObjectPtr<UStaticMesh> CubeMesh;
	UPROPERTY() TObjectPtr<UStaticMesh> CylinderMesh;
	UPROPERTY() TObjectPtr<UStaticMesh> SphereMesh;

	/** Lean / pitch / suspension; carries the bike body and the rider mount. */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> Tilt;
	/** Every bike part (scaled for the pop-in, so the rider is not). */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> Body;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> FrontPivot;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> FrontWheel;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> RearWheel;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> RiderMount;
	UPROPERTY(Transient) TObjectPtr<USpotLightComponent> Headlight;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> PaintMaterial;

	FLinearColor Paint = FLinearColor(0.75f, 0.05f, 0.04f);
	bool bBuilt = false;
	bool bDeployed = false;
	float DeployAlpha = 0.f;
	float WheelAngle = 0.f;
	float SuspensionOffset = 0.f;
	float SuspensionVelocity = 0.f;
	bool bWasAirborne = false;
	float Time = 0.f;
	float NightAlphaSmoothed = 0.f;
};
