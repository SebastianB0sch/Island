// Duel Academy Island - the student's all-terrain motorcycle (procedural parts + code animation).

#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "DATypes.h"
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
	/** Signed ground speed along the bike's heading (cm/s); drives the wheel spin, chain and gearbox. */
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
	/** Boost held: the rider tucks in behind the number plate. */
	bool bBoosting = false;
	/** 0 = day, 1 = night: scales the headlight. */
	float NightAlpha = 0.f;
	bool bAirborne = false;
};

/**
 * A dirt bike assembled at runtime from the engine's basic shapes, so it needs no imported assets: round-section
 * knobby tyres on spoked wheels (built as instanced rings), drilled brake discs, a telescopic fork that steers
 * about its raked steering axis, a swingarm with a linked shock, an animated chain, a finned single-cylinder
 * engine, radiator and louvred shrouds, a curved exhaust, bent handlebars with hand guards, bodywork and lights.
 *
 * Suspension is real kinematics: the chassis (frame, engine, bodywork and the rider) heaves and pitches on the
 * two springs while the wheels stay on the ground - the swingarm swings, the fork sliders telescope over the
 * stanchions, the shock spring compresses. Bumps reach the front wheel first and the rear a wheelbase later.
 *
 * Attach it at the bottom of the capsule; it faces the owner's +X. The rider (the avatar component) is attached
 * to GetRiderMount() on the sprung chassis, and GetRiderTargets() tells it where the seat, grips and pegs are
 * this frame and how to ride: tucked when boosting, standing on the pegs over jumps and landings, weight back on
 * the brakes, the left foot down when stopped (the bike leans onto it). Purely visual: no collision.
 *
 * It also runs its own procedural engine audio (UDAEngineSynthComponent): a 5-speed drivetrain model turns ground
 * speed into rpm and gear, and the synth makes the single-cylinder note, gearbox whine, tyre/wind noise and
 * overrun crackle from that state.
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

	/** Advance the pop-in, wheels, chain, steering, lean, pitch, suspension, rider style, lights, drivetrain and
	 *  audio. The owner calls this every tick while the bike is deployed; the component itself never ticks. */
	void UpdateRide(float DeltaTime, const FDABikePose& Pose);

	/** The rider's root: on the seat line, at ground level of the (tilted, sprung) bike. */
	USceneComponent* GetRiderMount() const { return RiderMount; }

	/** This frame's seat, grips, pegs and riding style, in the rider mount's space (see FDARiderTargets). */
	void GetRiderTargets(FDARiderTargets& Out) const;

	/** Height (cm, above the rider mount) where the hips of a rider without IK belong. */
	float GetRiderHipHeight() const { return (SeatHeight + 10.f) * ModelScale; }

	/** Current engine speed and selected gear (HUD/debug). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Motorcycle")
	float GetEngineRPM() const { return EngineRPM; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Motorcycle")
	int32 GetGear() const { return Gear; }

	/** Suspension travel (cm at the axles, positive = compressed); debug and tests. */
	float GetFrontTravel() const { return FrontTravel; }
	float GetRearTravel() const { return RearTravel; }

	/** Uniform scale of the whole model. The layout is drawn as a full-size enduro; 0.95 fits the cast (seat
	 *  height 93 cm, so a stopped rider just reaches the ground with one foot). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float ModelScale = 0.95f;

	/** Wheel radius (cm, before ModelScale); the hub height above the ground. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float WheelRadius = 36.f;

	/** Seat top height above the ground (cm, before ModelScale). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float SeatHeight = 98.f;

	/** Full handlebar lock (degrees about the steering axis). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float MaxSteerAngle = 28.f;

	/** How far the bike leans onto the rider's foot at a stop (degrees). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float FootDownLean = 12.f;

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
	/** A bent tube through Points: rods with a ball at every bend. */
	void AddTube(USceneComponent* Parent, const TArray<FVector>& Points, float Diameter, UMaterialInterface* Material);
	/** A cylinder transform spanning A..B, for instanced spokes/rings. */
	FTransform MakeRodTransform(const FVector& A, const FVector& B, float Diameter) const;
	/** One instanced mesh for repeated details (tyre ring, spokes, fins, chain, ...). */
	UInstancedStaticMeshComponent* AddInstances(UStaticMesh* Mesh, USceneComponent* Parent,
		const TArray<FTransform>& Transforms, UMaterialInterface* Material);
	USceneComponent* AddPivot(USceneComponent* Parent, const FVector& Location);
	USceneComponent* BuildWheel(USceneComponent* Parent, const FVector& Hub, bool bRear,
		UMaterialInterface* Rubber, UMaterialInterface* Rim, UMaterialInterface* Dark,
		UMaterialInterface* Metal, UMaterialInterface* Gold);
	/** A chain run of instanced links from A to B on the swingarm; returns the links' component. */
	UInstancedStaticMeshComponent* BuildChainRun(const FVector& A, const FVector& B, UMaterialInterface* Plate,
		UMaterialInterface* Pin, int32 RunIndex);
	UMaterialInstanceDynamic* MakeMaterial(UMaterialInterface* Base, const FLinearColor& Tint, float Roughness,
		float Metallic, float EmissiveStrength = -1.f);
	void Build();
	void UpdateDrivetrain(float DeltaTime, const FDABikePose& Pose, float Acceleration);
	void UpdateSuspension(float DeltaTime, const FDABikePose& Pose, float Acceleration, bool bBraking);
	void UpdateRiderStyle(float DeltaTime, const FDABikePose& Pose, float Acceleration, bool bBraking);
	void TriggerExhaustPop(bool bFlash);
	/** Steering rotation of the front end about the raked steering axis. */
	FQuat SteerRotation() const;
	/** Body-space point -> rider-mount space at the model's rest scale (ignores the pop-in). */
	FVector BodyToMount(const FVector& BodyPoint) const;

	UPROPERTY() TObjectPtr<UStaticMesh> CubeMesh;
	UPROPERTY() TObjectPtr<UStaticMesh> CylinderMesh;
	UPROPERTY() TObjectPtr<UStaticMesh> SphereMesh;
	UPROPERTY() TObjectPtr<UStaticMesh> ConeMesh;

	/** Lean / pitch about the tyre contacts on the ground. */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> Tilt;
	/** Engine vibration (bike and rider shake, but the pop-in scale is below this). */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> Vibe;
	/** The sprung chassis: heave and pitch from the two suspensions; carries the rider mount. */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> Sprung;
	/** Every scaled bike part (ModelScale and the pop-in; the rider is not scaled). */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> Body;
	/** Rear wheel, chain runs and caliper: swings about the swingarm pivot. */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> Swingarm;
	/** Steering: clamps, stanchions, bars, plate, headlight and fender turn about the steering axis. */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> FrontPivot;
	/** Fork sliders, front wheel and caliper: telescope along the fork over the stanchions. */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> FrontLower;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> FrontWheel;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> RearWheel;
	/** Shock: aimed from its top mount at the swingarm link; the spring part stretches with the travel. */
	UPROPERTY(Transient) TObjectPtr<USceneComponent> ShockAim;
	UPROPERTY(Transient) TObjectPtr<USceneComponent> ShockSpring;
	/** Chain links of the top and bottom runs, slid along their run as the chain moves. */
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> ChainLinksTop;
	UPROPERTY(Transient) TObjectPtr<UInstancedStaticMeshComponent> ChainLinksBottom;
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
	float SteerDegrees = 0.f;
	float ChainTravel = 0.f;
	FVector ChainStart[2] = { FVector::ZeroVector, FVector::ZeroVector };
	FVector ChainDir[2] = { FVector::ForwardVector, FVector::ForwardVector };

	// Suspension (cm at the axles, positive = compressed) and the distance rolled (bump phase).
	float FrontTravel = 0.f;
	float FrontTravelVelocity = 0.f;
	float RearTravel = 0.f;
	float RearTravelVelocity = 0.f;
	float Rolled = 0.f;
	float VibePhase = 0.f;
	float BrakeAlpha = 0.f;
	float ExhaustFlashTimer = 0.f;
	bool bWasAirborne = false;
	float LastForwardSpeed = 0.f;
	float Time = 0.f;
	float NightAlphaSmoothed = 0.f;

	// Rider style (FDARiderTargets).
	float AirTime = 0.f;
	float LandHold = 0.f;
	float StandAlpha = 0.f;
	float TuckAlpha = 0.f;
	float FootDownAlpha = 0.f;
	bool bFootDownWanted = false;
	float DriveAlpha = 0.f;
	float RiderSink = 0.f;
	float RiderSinkVelocity = 0.f;
	float LeanShown = 0.f;

	// Drivetrain (audio side of the bike; movement stays on the character).
	int32 Gear = 1;
	float EngineRPM = 1400.f;
	float ShiftTimer = 0.f;
	float BackfireCooldown = 0.f;
};
