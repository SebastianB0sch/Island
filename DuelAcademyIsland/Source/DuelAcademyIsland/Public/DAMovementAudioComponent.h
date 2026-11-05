// Duel Academy Island - procedural on-foot movement audio (no imported samples).
//
// Footsteps are synthesised live from the character's gait phase, the material
// underfoot and the water depth, so walking, sprinting, wading, swimming,
// jumping and landing all stay in sync with what the body is doing. A quiet
// body/clothing/breath layer and a speed-driven wind layer fill the gaps
// between contacts; the bike replaces the whole thing while riding.

#pragma once

#include "CoreMinimal.h"
#include "Components/SynthComponent.h"
#include "DAMovementAudioComponent.generated.h"

class FDAMovementAudioState;

UENUM(BlueprintType)
enum class EDAMovementSurface : uint8
{
	Grass,
	Dirt,
	Gravel,
	Sand,
	Stone,
	Wood,
	Metal,
	Carpet,
	ShallowWater,
	DeepWater,
	Count UMETA(Hidden)
};

/** Per-tick movement state handed to the synth (game thread -> audio render thread). */
struct FDAMovementAudioParams
{
	/** Horizontal ground speed, cm/s. */
	float Speed = 0.f;
	/** Speed normalised against a sprint, 0..1. */
	float Speed01 = 0.f;
	/** Locomotion contact phase, 0..1 (0 and 0.5 are the foot plants). */
	float Phase = 0.f;
	/** Gait cycles per second (two footsteps per cycle). */
	float Cadence = 0.f;
	/** How far the feet are below the water surface, cm (negative = above water). */
	float WaterDepth = 0.f;
	/** Vertical velocity, cm/s. */
	float VerticalSpeed = 0.f;
	bool bGrounded = true;
	bool bSwimming = false;
	bool bWading = false;
	bool bMoving = false;
	bool bRiding = false;
	bool bIndoors = false;
	bool bSprinting = false;
	EDAMovementSurface Surface = EDAMovementSurface::Grass;
};

/**
 * Footstep / body / water synthesiser for the player. The owner's movement,
 * gait phase and ground material drive a small set of impact voices plus
 * continuous cloth, breath and water layers. It produces no assets and does
 * no work on the audio thread beyond generating the current block.
 */
UCLASS(ClassGroup = (DuelAcademy), meta = (BlueprintSpawnableComponent))
class DUELACADEMYISLAND_API UDAMovementAudioComponent : public USynthComponent
{
	GENERATED_BODY()

public:
	UDAMovementAudioComponent(const FObjectInitializer& ObjectInitializer);
	virtual ~UDAMovementAudioComponent() override;

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	/** Latest movement state (normally called by TickComponent). */
	void SetMovementState(const FDAMovementAudioParams& Params);

	/** One foot contact. Intensity 0..1; Water01 blends a wet/splashy layer over the surface. */
	void PostFootstep(EDAMovementSurface Surface, float Intensity, bool bLeft, float Water01);

	/** A landing thump (Impact01 0..1), optionally in shallow water. */
	void PostLanding(EDAMovementSurface Surface, float Impact01, float Water01);

	/** Entering (bEntering) or leaving the water. */
	void PostSplash(float Intensity, bool bEntering);

	/** A jump take-off scuff / effort. */
	void PostJump(float Intensity);

	/** One swimming arm stroke (bLeft) or a sculling tread. */
	void PostSwimStroke(bool bLeft, float Intensity, float Water01);

	/** Test seam: render a walk/run/surface/water performance offline as a mono WAV. */
	static bool RenderOfflineTest(const FString& WavPath, FString& OutSummary);

	/** Pure material classifier (case-insensitive keywords + terrain geography). */
	static EDAMovementSurface ClassifySurfaceMaterial(const FString& MaterialName, float SlopeDegrees,
		float HeightAboveWater, bool bIndoors);

	/** Human cadence model used when the avatar cannot report a phase (cycles/s). */
	static float EstimateCadence(float Speed);

	/** Surface of the last footstep (debug / harnesses). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Audio")
	EDAMovementSurface GetLastSurface() const { return LastSurface; }

	/** Number of foot contacts posted since spawn (debug / harnesses). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Audio")
	int32 GetFootstepCount() const { return FootstepCount; }

protected:
	virtual bool Init(int32& SampleRate) override;
	virtual ISoundGeneratorPtr CreateSoundGenerator(const FSoundGeneratorInitParams& InParams) override;

private:
	void GatherAndPost(float DeltaSeconds);
	void UpdateSurface(FDAMovementAudioParams& Params);
	void UpdateFootsteps(FDAMovementAudioParams& Params, float DeltaSeconds);
	void UpdateAirAndWater(const FDAMovementAudioParams& Params);
	void UpdateSwimming(const FDAMovementAudioParams& Params, float DeltaSeconds);
	float WaterBlendFor(float Depth) const;

	TSharedPtr<FDAMovementAudioState, ESPMode::ThreadSafe> AudioState;

	EDAMovementSurface CachedSurface = EDAMovementSurface::Grass;
	EDAMovementSurface LastSurface = EDAMovementSurface::Grass;
	float SurfaceTimer = 0.f;
	float CachedWaterZ = 0.f;
	bool bHasWater = false;

	bool bWasGrounded = true;
	bool bWasSwimming = false;
	bool bWasWading = false;
	float LastAirVerticalSpeed = 0.f;

	bool bWasMoving = false;
	int32 LastStepIndex = INDEX_NONE;
	float StepTimer = 0.f;
	bool bNextStepLeft = true;
	float LastPhaseSample = 0.f;
	float PhaseStaleTime = 0.f;

	float SwimPhase = 0.f;
	int32 LastSwimArm = INDEX_NONE;
	float TreadTimer = 0.f;
	int32 FootstepCount = 0;
};
