// Duel Academy Island - a live, procedural motorcycle engine (no imported audio assets).

#pragma once

#include "CoreMinimal.h"
#include "Components/SynthComponent.h"
#include "Engine/EngineTypes.h"
#include "DAEngineSynthComponent.generated.h"

class FDAEngineAudioState;

/** Per-frame drivetrain state handed to the synth (game thread -> audio render thread). */
struct FDAEngineAudioParams
{
	/** Engine speed, rpm. */
	float RPM = 1400.f;
	/** Rider throttle, 0..1. */
	float Throttle = 0.f;
	/** Ground speed, cm/s (absolute). */
	float Speed = 0.f;
	/** Ground speed normalised against the bike's top speed, 0..1. */
	float Speed01 = 0.f;
	/** Selected gear, 1..5 (for the gearbox whine). */
	float Gear = 1.f;
	bool bGrounded = true;
	bool bBraking = false;
};

/**
 * Runtime engine/exhaust/wind synthesiser. The bike feeds it rpm, throttle and
 * speed every tick; the audio render thread turns that into a single-cylinder
 * four-stroke note: firing pulses and their harmonics, exhaust/intake noise,
 * valve clatter, gearbox/chain whine, tyre and wind noise, overrun crackle,
 * a starter-motor crank and a settling idle.
 *
 * It produces no assets and ticks no UObject: parameters travel through lock-free
 * atomics and the generator lives entirely on the audio render thread.
 */
UCLASS(ClassGroup = (DuelAcademy), meta = (BlueprintSpawnableComponent))
class DUELACADEMYISLAND_API UDAEngineSynthComponent : public USynthComponent
{
	GENERATED_BODY()

public:
	UDAEngineSynthComponent(const FObjectInitializer& ObjectInitializer);
	virtual ~UDAEngineSynthComponent() override;

	/** Latest engine state; call every tick while the bike is deployed. */
	void SetEngineState(const FDAEngineAudioParams& Params);

	/** Start the electric starter and let the engine catch (also clears a pending stop). */
	void StartEngine();

	/** Let the engine die away, then stop the synth after the fade. */
	void StopEngine(float FadeSeconds = 0.4f);

	/** A gear change: momentary ignition cut and a mechanical clunk. */
	void TriggerShift();

	/** An exhaust pop/backfire (the bike also flashes the exhaust flame). */
	void TriggerExhaustPop();

	/** Test seam: render a short engine performance offline and save it as a mono WAV.
	 *  Returns false if the rendering produced silence, non-finite samples or no dynamics. */
	static bool RenderOfflineTest(const FString& WavPath, FString& OutSummary);

protected:
	virtual bool Init(int32& SampleRate) override;
	virtual ISoundGeneratorPtr CreateSoundGenerator(const FSoundGeneratorInitParams& InParams) override;

private:
	void FinishStop();

	TSharedPtr<FDAEngineAudioState, ESPMode::ThreadSafe> AudioState;
	FTimerHandle StopTimer;
};
