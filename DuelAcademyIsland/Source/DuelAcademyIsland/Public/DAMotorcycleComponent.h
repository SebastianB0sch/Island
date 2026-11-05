// Duel Academy Island - the student's all-terrain motorcycle (procedural parts + code animation).

#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "DAMotorcycleComponent.generated.h"

class UStaticMesh;
class UStaticMeshComponent;
class UInstancedStaticMeshComponent;
class UMaterialInterface;
class UMaterialInstanceDynamic;
class USpotLightComponent;
class UPointLightComponent;
class UDAEngineSynthComponent;

/** Per-tick pose input for the motorcycle; all angles in degrees. */
struct FDABikePose
{
	/** Signed ground speed along the bike's heading (cm/s); drives the wheel spin and gearbox. */
	float ForwardSpeed = 0.f;
	/** -1 (full left) .. 1 (full right) handlebar angle. */
	float Steer = 0.f;
	/** Roll into the turn; positive leans towards the bike's right (+Y). */
	float Lean = 0.f;
	/** Nose-up pitch (slope of the ground, or the flight path while airborne). */
	float Pitch = 0.f;
	/** Rider throttle, 0 (closed) .. 1 (wide open); drives the exhaust note and engine vibration. */
	float Throttle = 0.f;
	/** The rider is hard on the brakes; lights the brake light and dives the fork. */
	bool bBraking = false;
	/** 0 = day, 1 = night: scales the headlight. */
	float NightAlpha = 0.f;
	bool bAirborne = false;
};

/**
 * A dirt bike assembled at runtime from the engine's basic shapes, so it needs
 * no imported assets: a spoked, knobby front/rear wheel pair (tyre, rim and
 * spokes built as instanced rings), a long-travel fork with dive, a swinging
 * rear end with chain and sprocket, a finned single-cylinder engine, radiator,
 * exhaust with heat shield, bodywork and lights.
 *
 * Attach it at the bottom of the capsule; it faces the owner's +X. The rider
 * (the avatar component) is attached to GetRiderMount() while riding, so it
 * leans and pitches together with the bike. Purely visual: no collision.
 *
 * It also runs its own procedural engine audio (UDAEngineSynthComponent): a
 * 5-speed drivetrain model turns ground speed into rpm and gear, and the synth
 * makes the single-cylinder note, gearbox whine, tyre/wind noise and overrun
 * crackle from that state.
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

	/** Advance the pop-in, wheels, steering, lean, pitch, suspension, lights, drivetrain and audio.
	 *  The owner calls this every tick while the bike is deployed; the component itself never ticks. */
	void UpdateRide(float DeltaTime, const FDABikePose& Pose);

	/** The rider's root: on the seat line, at ground level of the (tilted) bike. */
	USceneComponent* GetRiderMount() const { return RiderMount; }

	/** Height (cm, above the rider mount) where the rider's hips belong. */
	float GetRiderHipHeight() const { return SeatHeight + 10.f; }

	/** Current engine speed and selected gear (HUD/debug). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Motorcycle")
	float GetEngineRPM() const { return EngineRPM; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Motorcycle")
	int32 GetGear() const { return Gear; }

	/** Wheel radius (cm); the hub height above the ground. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float WheelRadius = 36.f;

	/** Seat top height above the ground (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float SeatHeight = 98.f;

	/** Full handlebar lock (degrees). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float MaxSteerAngle = 28.f;

	/** Engine idle and redline (rpm), used by the drivetrain and audio. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float IdleRPM = 1400.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float RedlineRPM = 8200.f;

private:
	UStaticMeshComponent* AddPart(UStaticMesh* Mesh, USceneComponent* Parent, const FVector& Location,
		const FRotator& Rotation, const FVector& Scale, UMaterialInterface* Material);
	/** A cylinder of the given diameter spanning A..B (parent space). */
	UStaticMeshComponent* AddRod(USceneComponent* Parent, const FVector& A, const FVector& B, float Diameter,
		UMaterialInterface* Material);
	/** A cylinder transform spanning A..B, for instanced spokes/rings. */
	FTransform MakeRodTransform(const FVector& A, const FVector& B, float Diameter) const;
	/** One instanced mesh for repeated details (tyre ring, spokes, fins, chain, ...). */
	UInstancedStaticMeshComponent* AddInstances(UStaticMesh* Mesh, USceneComponent* Parent,
		const TArray<FTransform>& Transforms, UMaterialInterface* Material);
	USceneComponent* AddPivot(USceneComponent* Parent, const FVector& Location);
	USceneComponent* BuildWheel(USceneComponent* Parent, const FVector& Hub, bool bRear,
		UMaterialInterface* Rubber, UMaterialInterface* Rim, UMaterialInterface* Dark,
		UMaterialInterface* Metal, UMaterialInterface* Gold);
	UMaterialInstanceDynamic* MakeMaterial(UMaterialInterface* Base, const FLinearColor& Tint, float Roughness,
		float Metallic, float EmissiveStrength = -1.f);
	void Build();
	void UpdateDrivetrain(float DeltaTime, const FDABikePose& Pose, float Acceleration);
	void TriggerExhaustPop(bool bFlash);

	UPROPERTY() TObjectPtr<UStaticMesh> CubeMesh;
	UPROPERTY() TObjectPtr<UStaticMesh> CylinderMesh;
	UPROPERTY() TObjectPtr<UStaticMesh> SphereMesh;
	UPROPERTY() TObjectPtr<UStaticMesh> ConeMesh;

	/** Lean / pitch / suspension; carries the bike body and the rider mount. */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> Tilt;
	/** Engine vibration (bike and rider shake, but the pop-in scale is below this). */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> Vibe;
	/** Every scaled bike part (pop-in only; the rider is not scaled). */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> Body;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> FrontPivot;
	/** Upper fork, triple clamps, bars and headlight: dives under braking. */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> FrontUpper;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> FrontWheel;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> RearWheel;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> RiderMount;
	UPROPERTY(Transient) TObjectPtr<USpotLightComponent> Headlight;
	UPROPERTY(Transient) TObjectPtr<UPointLightComponent> BrakeGlow;
	UPROPERTY(Transient) TObjectPtr<UStaticMeshComponent> ExhaustFlame;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> PaintMaterial;
	UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> TailMaterial;
	UPROPERTY(Transient) TObjectPtr<UDAEngineSynthComponent> EngineAudio;

	FLinearColor Paint = FLinearColor(0.75f, 0.05f, 0.04f);
	bool bBuilt = false;
	bool bDeployed = false;
	bool bAudioStarted = false;
	float DeployAlpha = 0.f;
	float WheelAngle = 0.f;
	float SuspensionOffset = 0.f;
	float SuspensionVelocity = 0.f;
	float FrontTravel = 0.f;
	float FrontTravelVelocity = 0.f;
	float VibePhase = 0.f;
	float BrakeAlpha = 0.f;
	float ExhaustFlashTimer = 0.f;
	bool bWasAirborne = false;
	float LastForwardSpeed = 0.f;
	float Time = 0.f;
	float NightAlphaSmoothed = 0.f;

	// Drivetrain (audio side of the bike; movement stays on the character).
	int32 Gear = 1;
	float EngineRPM = 1400.f;
	float ShiftTimer = 0.f;
	float BackfireCooldown = 0.f;
};
