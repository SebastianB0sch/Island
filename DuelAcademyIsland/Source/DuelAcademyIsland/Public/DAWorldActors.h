// Duel Academy Island - small data-driven world actors spawned by the editor build script:
// instanced scatter, floating (bobbing) meshes, smoke/steam/mist emitters, lighthouse beam,
// ambient sound emitters.

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

/** A mesh that gently bobs and rolls on the water (ferry, rowboats, buoys). */
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

	/** Vertical bob amplitude in cm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Amplitude = 10.f;

	/** Seconds per bob cycle. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Period = 5.f;

	/** Max roll / pitch sway in degrees. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Sway = 1.5f;

private:
	FVector BaseLocation = FVector::ZeroVector;
	FRotator BaseRotation = FRotator::ZeroRotator;
	float Phase = 0.f;
	float Time = 0.f;
};

UENUM(BlueprintType)
enum class EDAEmitterKind : uint8
{
	Smoke,
	Steam,
	Mist,
	Sparks
};

/**
 * Cheap volumetric-looking puffs without Niagara assets: an instanced sphere
 * whose instances rise, grow and fade (per-instance custom data 0 = opacity,
 * read by M_DA_Smoke).
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

	/** Optional material override (defaults to M_DA_Smoke). */
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
	};
	void Respawn(FPuff& P, bool bInitial);

	TArray<FPuff> Particles;
	FRandomStream Rng;
	float Rise = 300.f;
	float Spread = 100.f;
	float BaseSize = 1.f;
	float Lifetime = 4.f;
	float MaxOpacity = 0.6f;
	float CheckTimer = 0.f;
	bool bVisibleToPlayer = true;
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
