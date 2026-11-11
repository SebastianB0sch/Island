// Duel Academy Island - small actors that make the island feel alive, spawned by the editor build script
// from layout.json "specials": turning meshes (water wheels, windmill sails) and procedural bird flocks.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DALifeActors.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMeshComponent;

/**
 * A mesh turning at constant speed about one of its own axes (layout.json special "spinner"): the water
 * wheel of the mill, windmill sails. The wheel has no collision - nobody gets pushed around by it.
 */
UCLASS()
class DUELACADEMYISLAND_API ADASpinner : public AActor
{
	GENERATED_BODY()

public:
	ADASpinner();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UStaticMeshComponent> Mesh;

	/** Rotation axis in the mesh's own frame. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FVector Axis = FVector(0.0, 1.0, 0.0);

	/** Revolutions per minute (signed). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Rpm = 6.f;

	/** Stops turning (and ticking the transform) when the player is further away than this (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float ActiveDistance = 30000.f;

private:
	float CheckTimer = 0.f;
	bool bActive = true;
};

UENUM(BlueprintType)
enum class EDABirdKind : uint8
{
	/** Sea gulls: big, white, long glides between a few lazy wing beats. */
	Gull,
	/** Small brown songbirds: quick wing beats, tight restless loops. */
	Songbird
};

/**
 * A flock of birds circling inside a cylinder (layout.json special "birds"). No assets: each bird is an
 * elongated sphere and two flat boxes (the wings) drawn by two instanced components, moved on closed
 * wandering loops, banking into their turns and flapping. Asleep (hidden, not ticking the instances) when
 * the player is far away.
 */
UCLASS()
class DUELACADEMYISLAND_API ADABirdFlock : public AActor
{
	GENERATED_BODY()

public:
	ADABirdFlock();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	EDABirdKind Kind = EDABirdKind::Gull;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy", meta = (ClampMin = "1", ClampMax = "64"))
	int32 Count = 10;

	/** Radius (cm) of the cylinder the flock stays in, centred on the actor. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Radius = 6000.f;

	/** Height (cm) of the band above the actor the birds fly in. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Height = 2500.f;

	/** Flight speed in cm/s; <= 0 = the kind's own (gulls 900, songbirds 700). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Speed = 0.f;

	/** The flock sleeps when the player is further than this from the cylinder (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float ActiveDistance = 45000.f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UInstancedStaticMeshComponent> Bodies;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UInstancedStaticMeshComponent> Wings;

private:
	struct FBird
	{
		/** Centre of its loop (actor space) and the loop's radius. */
		FVector Home = FVector::ZeroVector;
		float Loop = 1000.f;
		/** Position on the loop (radians), direction (+1 / -1) and angular speed (rad/s). */
		float Angle = 0.f;
		float Turn = 1.f;
		float AngularSpeed = 0.5f;
		/** Random phases: loop wobble, climbing, wing beat. */
		float Seed = 0.f;
		float FlapPhase = 0.f;
		float Scale = 1.f;
	};

	TArray<FBird> Birds;
	TArray<FTransform> BodyTransforms;
	TArray<FTransform> WingTransforms;
	float Time = 0.f;
	float CheckTimer = 0.f;
	bool bAwake = true;
	/** Kind parameters (set in BeginPlay). */
	float BodyLength = 45.f;
	float WingSpan = 55.f;
	float FlapRate = 3.f;
	float GlideShare = 0.6f;
};
