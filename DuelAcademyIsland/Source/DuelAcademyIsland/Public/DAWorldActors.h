// Duel Academy Island - small data-driven world actors spawned by the editor build script:
// instanced scatter, floating (bobbing) meshes, smoke/steam/mist emitters, lighthouse beam,
// ambient sound emitters, automatic doors.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DAWorldActors.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class UInstancedStaticMeshComponent;
class UStaticMeshComponent;
class UStaticMesh;
class USpotLightComponent;
class UPointLightComponent;
class UAudioComponent;
class USoundBase;
class UMaterialInterface;

/**
 * Thousands of instances of one mesh (trees, rocks, lamps, props). The
 * instances live in a default HISM component, so they are saved with the level.
 */
UCLASS()
class DUELACADEMYISLAND_API ADAInstancedScatter : public AActor
{
	GENERATED_BODY()

public:
	ADAInstancedScatter();

	/** Replace all instances (world-space transforms) - called by the build script. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetInstances(UStaticMesh* Mesh, const TArray<FTransform>& Transforms, int32 CullStart, int32 CullEnd, bool bCollision, bool bCastShadow);

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	int32 GetInstanceCount() const;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UHierarchicalInstancedStaticMeshComponent> Instances;
};

/**
 * A mesh that floats on the water (ferry, rowboats, buoys). With wave data in the level (ADAIslandManager,
 * water.json) it rides the real surface: the wave height is sampled at the bow, stern, port and starboard of
 * the hull (from the mesh bounds) and heave, pitch and roll follow through a damped spring - a ferry answers
 * slowly and averages short waves away, a buoy bobs with every crest. Without wave data, or on flat water
 * (rivers, ponds), it keeps the old sine bob.
 */
UCLASS()
class DUELACADEMYISLAND_API ADAFloatingActor : public AActor
{
	GENERATED_BODY()

public:
	ADAFloatingActor();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UStaticMeshComponent> Mesh;

	/** Vertical bob amplitude in cm (sine bob); riding real waves, the heave is limited to HeaveLimit times this. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Amplitude = 10.f;

	/** Seconds per bob cycle (sine bob). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Period = 5.f;

	/** Max roll / pitch sway in degrees (sine bob); riding real waves, the tilt is limited to TiltLimit times this. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Sway = 1.5f;

	/** Ride the wave surface when the level has wave data. Off = always the sine bob. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Buoyancy")
	bool bUseWaves = true;

	/** Heave limit while riding waves, as a multiple of Amplitude. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Buoyancy", meta = (ClampMin = "0"))
	float HeaveLimit = 8.f;

	/** Pitch / roll limit while riding waves, as a multiple of Sway. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Buoyancy", meta = (ClampMin = "0"))
	float TiltLimit = 5.f;

	/** Seconds the hull takes to answer a wave; <= 0 = from its length (0.5 s for a buoy .. 4.5 s for the ferry). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Buoyancy")
	float ResponseTime = 0.f;

	/** Damping ratio of the heave / tilt springs (1 = critical, lower = livelier). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Buoyancy", meta = (ClampMin = "0.1", ClampMax = "2"))
	float Damping = 0.7f;

private:
	void TickSineBob();
	bool TickBuoyancy(float DeltaSeconds);

	FVector BaseLocation = FVector::ZeroVector;
	FRotator BaseRotation = FRotator::ZeroRotator;
	float Phase = 0.f;
	float Time = 0.f;

	/** Hull footprint from the mesh bounds: centre offset and half length / half width (actor space, cm). */
	FVector HullCenter = FVector::ZeroVector;
	float HullHalfLength = 100.f;
	float HullHalfWidth = 50.f;
	/** Spring state: heave (cm), pitch and roll (degrees) and their velocities. */
	float Heave = 0.f;
	float HeaveVel = 0.f;
	float PitchDeg = 0.f;
	float PitchVel = 0.f;
	float RollDeg = 0.f;
	float RollVel = 0.f;
	TWeakObjectPtr<class ADAIslandManager> CachedManager;
};

UENUM(BlueprintType)
enum class EDAEmitterKind : uint8
{
	Smoke,
	Steam,
	Mist,
	Sparks,
	/** Fountain spray: droplets hopping up where the water lands and falling back under gravity. */
	Spray,
	/** Fountain jet: a stream of droplets fired from a nozzle on a ballistic path (JetVelocity), stretched along
	 *  their motion, ending in a small splash where they meet the water at FloorZ. */
	Jet,
	/** Slow glowing motes drifting and blinking near the actor, at night only. */
	Fireflies
};

/**
 * Cheap volumetric-looking puffs without Niagara assets: an instanced sphere
 * whose instances rise, grow and fade (per-instance custom data 0 = opacity,
 * read by M_DA_Smoke; M_DA_Spray for the Spray kind's droplets).
 */
UCLASS()
class DUELACADEMYISLAND_API ADAEmitter : public AActor
{
	GENERATED_BODY()

public:
	ADAEmitter();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	EDAEmitterKind Kind = EDAEmitterKind::Steam;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float EffectScale = 1.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Rate = 1.f;

	/** Spawn circle radius (cm). > 0: particles start on a circle of this radius round the actor (where a
	 *  fountain sheet lands) instead of a small disc, and Spray droplets are thrown outward from it. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Ring = 0.f;

	/** With Ring: only at this many evenly spaced spots on the circle (a ring of fountain jets); 0 = anywhere. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	int32 RingPoints = 0;

	/** Angle of the first spot (degrees, actor-local, from +X towards +Y). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float RingAngle = 0.f;

	/** Jet: initial velocity of the stream at the nozzle (world axes, cm/s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Jet")
	FVector JetVelocity = FVector(0.0, 0.0, 600.0);

	/** Jet: world Z (cm) of the water the stream falls back into; droplets end and splash there. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Jet")
	float FloorZ = 0.f;

	/** Jet: half angle (degrees) of the cone the droplets leave the nozzle in. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Jet", meta = (ClampMin = "0", ClampMax = "45"))
	float JetSpread = 2.5f;

	/** Optional material override (defaults to M_DA_Smoke; M_DA_Spray for Spray, Jet and Fireflies). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	TObjectPtr<UMaterialInterface> Material;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UInstancedStaticMeshComponent> Puffs;

private:
	struct FPuff
	{
		float Age = 0.f;
		float Life = 1.f;
		FVector Start = FVector::ZeroVector;
		FVector Velocity = FVector::ZeroVector;
		float Size0 = 1.f;
		float Size1 = 2.f;
		/** Jet: this particle is a splash droplet (hops where the stream lands) rather than part of the stream. */
		bool bSplash = false;
		/** Splash droplets wait (invisible) until a stream droplet lands. */
		bool bIdle = false;
		/** Fireflies: per-mote random number driving its drift and blink. */
		float Seed = 0.f;
	};
	void Respawn(FPuff& P, bool bInitial);
	void RespawnJet(FPuff& P, bool bInitial);
	void TriggerSplash(const FVector& Where);
	void TickFireflies(float DeltaSeconds);
	/** Transform of a droplet at Pos moving with Vel: a sphere stretched along its motion. */
	static FTransform DropletTransform(const FVector& Pos, const FVector& Vel, float Size, float StretchPerSpeed);

	TArray<FPuff> Particles;
	TArray<FTransform> Transforms;
	FRandomStream Rng;
	float Rise = 300.f;
	float Spread = 100.f;
	float BaseSize = 1.f;
	float Lifetime = 4.f;
	float MaxOpacity = 0.6f;
	/** cm/s^2 pulling particles down (Spray and Jet; the other kinds drift at constant velocity). */
	float Gravity = 0.f;
	float CheckTimer = 0.f;
	bool bVisibleToPlayer = true;
	/** Jet: nozzle velocity in actor space, flight time down to FloorZ, first splash particle, next one to use. */
	FVector JetLocalVelocity = FVector::ZeroVector;
	float JetFlightTime = 1.f;
	int32 FirstSplash = 0;
	int32 NextSplash = 0;
	/** Fireflies: 0 by day .. 1 at night (smoothed). */
	float NightGlow = 0.f;
};

/** Rotating lighthouse beam (spot light + additive cone), lit at night. */
UCLASS()
class DUELACADEMYISLAND_API ADALighthouseBeam : public AActor
{
	GENERATED_BODY()

public:
	ADALighthouseBeam();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Degrees per second. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float RotationSpeed = 40.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float BeamLength = 60000.f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<USceneComponent> Spinner;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<USpotLightComponent> SpotA;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<USpotLightComponent> SpotB;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UStaticMeshComponent> BeamA;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UStaticMeshComponent> BeamB;

private:
	float Intensity = 0.f;
};

/** Looping 3D ambience (ocean, wind, volcano...) with a simple spherical falloff. */
UCLASS()
class DUELACADEMYISLAND_API ADAAmbientSound : public AActor
{
	GENERATED_BODY()

public:
	ADAAmbientSound();

	virtual void BeginPlay() override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	TObjectPtr<USoundBase> Sound;

	/** Distance (cm) over which the sound fades out. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Radius = 4000.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Volume = 1.f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UAudioComponent> Audio;
};

UENUM(BlueprintType)
enum class EDADoorMode : uint8
{
	/** Hinged leaves that swing open (away from whoever approaches). */
	Swing,
	/** Leaves that slide sideways into the wall (shoji, automatic glass doors). */
	Slide
};

/**
 * Automatic door placed in every doorway by the build script. One or two leaves (the mesh's pivot is the
 * hinge, the leaf extends along +X); opens when a pawn (player or student) comes close and closes again
 * behind them. The leaves never block pawns, so nobody gets stuck on a door that is still opening.
 * Actor frame: origin = bottom centre of the doorway, local +Y = outside.
 */
UCLASS()
class DUELACADEMYISLAND_API ADADoor : public AActor
{
	GENERATED_BODY()

public:
	ADADoor();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Re-applies mesh / width / leaf layout after the properties were changed from code. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void RefreshDoor();

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	float GetOpenAlpha() const { return Alpha; }

	/** Mesh of ONE leaf: pivot at the hinge, leaf along +X, LeafWidth wide. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	TObjectPtr<UStaticMesh> LeafMesh;

	/** Clear width of the doorway (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Width = 90.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Height = 210.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	bool bDouble = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	EDADoorMode Mode = EDADoorMode::Swing;

	/** 0 = open away from the pawn, +1 = always towards outside (+Y), -1 = always towards inside. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	int32 SwingSide = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float OpenAngle = 92.f;

	/** Seconds for a full open / close. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float OpenTime = 0.55f;

	/** A pawn closer than this (cm, from the doorway centre) opens the door. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float TriggerRadius = 230.f;

	/** Doors this far from the player (cm) stop checking for students while closed. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float ActiveDistance = 4500.f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<USceneComponent> PivotA;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<USceneComponent> PivotB;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UStaticMeshComponent> LeafA;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UStaticMeshComponent> LeafB;

private:
	void ApplyPose();
	bool FindPawn(FVector& OutLocalPos) const;

	float Alpha = 0.f;
	float Target = 0.f;
	float Side = 1.f;
	float CheckTimer = 0.f;
};
