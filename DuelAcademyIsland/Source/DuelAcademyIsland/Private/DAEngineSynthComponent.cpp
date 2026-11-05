// Duel Academy Island - procedural motorcycle engine audio.

#include "DAEngineSynthComponent.h"

#include "Components/AudioComponent.h"
#include "Engine/Attenuation.h"
#include "Engine/World.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Sound/SoundAttenuation.h"
#include "TimerManager.h"

#include <atomic>

namespace
{
	constexpr float TwoPi = 2.0f * PI;

	FORCEINLINE float OnePoleCoeff(float CutoffHz, float SampleRate)
	{
		return 1.0f - FMath::Exp(-TwoPi * FMath::Clamp(CutoffHz, 1.0f, SampleRate * 0.45f) / SampleRate);
	}

	struct FOnePole
	{
		float Coeff = 0.0f;
		float State = 0.0f;

		void Init(float CutoffHz, float SampleRate) { Coeff = OnePoleCoeff(CutoffHz, SampleRate); }
		FORCEINLINE float Process(float X) { State += (X - State) * Coeff; return State; }
	};

	/** Chamberlin state-variable band-pass; stable enough for the low-Q exhaust formants we use. */
	struct FBandPass
	{
		float F = 0.1f;
		float Damp = 0.9f;
		float Low = 0.0f;
		float Band = 0.0f;

		void Init(float CenterHz, float Q, float SampleRate)
		{
			const float C = FMath::Clamp(CenterHz, 30.0f, SampleRate * 0.42f);
			F = 2.0f * FMath::Sin(PI * C / SampleRate);
			// Chamberlin SVF: the damping term is 1/Q. (The old 2*(1-Q^0.25)
			// curve goes negative above Q=1, which turns the filter into an oscillator.)
			Damp = 1.0f / FMath::Clamp(Q, 0.5f, 20.0f);
		}

		FORCEINLINE float Process(float X)
		{
			Low += F * Band;
			const float High = X - Low - Damp * Band;
			Band += F * High;
			return Band;
		}
	};

	/** Tiny xorshift RNG: audio-thread safe, no shared engine RNG state. */
	struct FXorShift32
	{
		uint32 State = 0x9E3779B9u;

		FORCEINLINE uint32 NextUInt()
		{
			State ^= State << 13;
			State ^= State >> 17;
			State ^= State << 5;
			return State;
		}

		FORCEINLINE float Next() { return static_cast<float>(NextUInt() >> 8) * (1.0f / 16777216.0f); }
		FORCEINLINE float Signed() { return Next() * 2.0f - 1.0f; }
	};
}

/**
 * Game-thread -> audio-render-thread parameter block. Every field is atomic so
 * a tick can update the whole state without locks or tearing; the generator
 * takes one relaxed snapshot at the start of each audio callback.
 */
class FDAEngineAudioState
{
public:
	void Set(const FDAEngineAudioParams& P)
	{
		RPM.store(P.RPM, std::memory_order_relaxed);
		Throttle.store(P.Throttle, std::memory_order_relaxed);
		Speed.store(P.Speed, std::memory_order_relaxed);
		Speed01.store(P.Speed01, std::memory_order_relaxed);
		Gear.store(P.Gear, std::memory_order_relaxed);
		Grounded.store(P.bGrounded, std::memory_order_relaxed);
		Braking.store(P.bBraking, std::memory_order_relaxed);
	}

	FDAEngineAudioParams Get() const
	{
		FDAEngineAudioParams P;
		P.RPM = RPM.load(std::memory_order_relaxed);
		P.Throttle = Throttle.load(std::memory_order_relaxed);
		P.Speed = Speed.load(std::memory_order_relaxed);
		P.Speed01 = Speed01.load(std::memory_order_relaxed);
		P.Gear = Gear.load(std::memory_order_relaxed);
		P.bGrounded = Grounded.load(std::memory_order_relaxed);
		P.bBraking = Braking.load(std::memory_order_relaxed);
		return P;
	}

	void SetRunning(bool bInRunning) { bRunning.store(bInRunning, std::memory_order_relaxed); }
	bool IsRunning() const { return bRunning.load(std::memory_order_relaxed); }

	void TriggerStart() { StartSequence.fetch_add(1, std::memory_order_relaxed); }
	void TriggerStop() { StopSequence.fetch_add(1, std::memory_order_relaxed); }
	void TriggerShift() { ShiftSequence.fetch_add(1, std::memory_order_relaxed); }
	void TriggerPop() { PopSequence.fetch_add(1, std::memory_order_relaxed); }

	uint32 StartSeq() const { return StartSequence.load(std::memory_order_relaxed); }
	uint32 StopSeq() const { return StopSequence.load(std::memory_order_relaxed); }
	uint32 ShiftSeq() const { return ShiftSequence.load(std::memory_order_relaxed); }
	uint32 PopSeq() const { return PopSequence.load(std::memory_order_relaxed); }

private:
	std::atomic<float> RPM{ 1400.0f };
	std::atomic<float> Throttle{ 0.0f };
	std::atomic<float> Speed{ 0.0f };
	std::atomic<float> Speed01{ 0.0f };
	std::atomic<float> Gear{ 1.0f };
	std::atomic<bool> Grounded{ true };
	std::atomic<bool> Braking{ false };
	std::atomic<bool> bRunning{ false };
	std::atomic<uint32> StartSequence{ 0 };
	std::atomic<uint32> StopSequence{ 0 };
	std::atomic<uint32> ShiftSequence{ 0 };
	std::atomic<uint32> PopSequence{ 0 };
};

namespace
{
	/** One voice of the bike: engine, gearbox, tyres, wind and starter. */
	class FDAMotorcycleSynth final : public ISoundGenerator
	{
	public:
		FDAMotorcycleSynth(const FSoundGeneratorInitParams& InParams,
			const TSharedRef<FDAEngineAudioState, ESPMode::ThreadSafe>& InState)
			: State(InState)
			, SampleRate(FMath::Max(InParams.SampleRate, 8000.0f))
			, NumChannels(FMath::Max(InParams.NumChannels, 1))
		{
			Rng.State = 0x9E3779B9u ^ static_cast<uint32>(InParams.InstanceID) ^ (static_cast<uint32>(InParams.AudioComponentId) << 7);
			// A generator can be re-created (audio device reset, stow/remount). The
			// old stop/shift/pop events must not fire again, but the start that
			// created us must: when the engine is already running, leave the last
			// start sequence one behind.
			LastStartSeq = State->StartSeq();
			LastStopSeq = State->StopSeq();
			LastShiftSeq = State->ShiftSeq();
			LastPopSeq = State->PopSeq();
			if (State->IsRunning())
			{
				--LastStartSeq;
			}
			InitFilters();
			PumpState();
		}

		virtual int32 OnGenerateAudio(float* OutAudio, int32 NumSamples) override
		{
			if (!OutAudio || NumSamples <= 0)
			{
				return 0;
			}

			PumpState();

			const int32 Frames = NumSamples / NumChannels;
			for (int32 Frame = 0; Frame < Frames; ++Frame)
			{
				const float Sample = RenderSample();
				for (int32 Channel = 0; Channel < NumChannels; ++Channel)
				{
					OutAudio[Frame * NumChannels + Channel] = Sample;
				}
			}
			return Frames * NumChannels;
		}

		virtual int32 GetDesiredNumSamplesToRenderPerCallback() const override
		{
			return FMath::Max(256, 512 * NumChannels);
		}

		virtual int32 GetNumChannels() const override { return NumChannels; }

	private:
		void InitFilters()
		{
			ExhaustNoiseLP.Init(950.0f, SampleRate);
			IntakeHi.Init(1600.0f, SampleRate);
			IntakeLo.Init(260.0f, SampleRate);
			WindHi.Init(6200.0f, SampleRate);
			WindLo.Init(220.0f, SampleRate);
			TireHi.Init(760.0f, SampleRate);
			TireLo.Init(85.0f, SampleRate);
			PopLP.Init(1100.0f, SampleRate);
			ClickLP.Init(2100.0f, SampleRate);
			StarterLP.Init(1500.0f, SampleRate);
			DcBlock.Init(18.0f, SampleRate);
			ExhaustRes.Init(700.0f, 5.0f, SampleRate);
			ExhaustRes2.Init(1700.0f, 3.5f, SampleRate);
			BodyRes.Init(110.0f, 2.0f, SampleRate);
		}

		void PumpState()
		{
			const FDAEngineAudioParams P = State->Get();
			TargetRPM = P.RPM;
			TargetThrottle = FMath::Clamp(P.Throttle, 0.0f, 1.0f);
			TargetSpeed01 = FMath::Clamp(P.Speed01, 0.0f, 1.0f);
			TargetGear = FMath::Clamp(P.Gear, 1.0f, 6.0f);
			bGrounded = P.bGrounded;
			bRunningNow = State->IsRunning();

			const uint32 StartSeq = State->StartSeq();
			if (StartSeq != LastStartSeq)
			{
				LastStartSeq = StartSeq;
				bCranking = true;
				CrankTime = 0.0f;
				CrankPhase = 0.0f;
				CrankChuff = 0.0f;
				RevFlare = 0.0f;
				CatchEnv = 0.0f;
				ShiftCut = 0.0f;
				ShiftClunk = 0.0f;
				HardPopEnv = 0.0f;
				PopEnv = 0.0f;
				RunGain = 0.0f;
				FirePhase = 0.0f;
				PulseEnv = 0.0f;
				IntakeEnv = 0.0f;
				ValveEnv = 0.0f;
			}

			const uint32 StopSeq = State->StopSeq();
			if (StopSeq != LastStopSeq)
			{
				LastStopSeq = StopSeq;
				bCranking = false;
				PopEnv = FMath::Max(PopEnv, 0.35f);
			}

			const uint32 ShiftSeq = State->ShiftSeq();
			if (ShiftSeq != LastShiftSeq)
			{
				LastShiftSeq = ShiftSeq;
				ShiftCut = 0.13f;
				ShiftClunk = 1.0f;
			}

			const uint32 PopSeq = State->PopSeq();
			if (PopSeq != LastPopSeq)
			{
				LastPopSeq = PopSeq;
				HardPopEnv = 1.0f;
			}

			if (P.bGrounded && !bWasGrounded)
			{
				LandEnv = 1.0f;
			}
			bWasGrounded = P.bGrounded;

			const float Dt = 1.0f / SampleRate;
			RpmSmooth = 1.0f - FMath::Exp(-Dt / 0.055f);
			ThrottleSmooth = 1.0f - FMath::Exp(-Dt / 0.035f);
			SpeedSmooth = 1.0f - FMath::Exp(-Dt / 0.12f);
			PulseDecay = FMath::Exp(-Dt * 26.0f);
			IntakeDecay = FMath::Exp(-Dt * 19.0f);
			ValveDecay = FMath::Exp(-Dt * 95.0f);
			HardPopDecay = FMath::Exp(-Dt * 14.0f);
			PopDecay = FMath::Exp(-Dt * 22.0f);
			LandDecay = FMath::Exp(-Dt * 10.0f);
			ShiftClunkDecay = FMath::Exp(-Dt * 25.0f);
			CrankChuffDecay = FMath::Exp(-Dt * 18.0f);
			RunGainCoef = 1.0f - FMath::Exp(-Dt / 0.20f);

			const float Rpm01 = FMath::Clamp((CurrentRPM - 1000.0f) / 7000.0f, 0.0f, 1.0f);
			ExhaustRes.Init(560.0f + 620.0f * Rpm01, 5.0f, SampleRate);
			ExhaustRes2.Init(1550.0f + 750.0f * Rpm01, 3.5f, SampleRate);
			BodyRes.Init(100.0f + 40.0f * Rpm01, 2.0f, SampleRate);
		}

		FORCEINLINE float RenderSample()
		{
			const float Dt = 1.0f / SampleRate;
			Time += Dt;

			CurrentRPM += (TargetRPM - CurrentRPM) * RpmSmooth;
			CurrentThrottle += (TargetThrottle - CurrentThrottle) * ThrottleSmooth;
			CurrentSpeed01 += (TargetSpeed01 - CurrentSpeed01) * SpeedSmooth;

			const float Rpm01 = FMath::Clamp((CurrentRPM - 1000.0f) / 7000.0f, 0.0f, 1.0f);
			const float IdleWeight = 1.0f - FMath::SmoothStep(0.02f, 0.42f, Rpm01);

			// --- electric starter, then the catch and flare ---------------------
			if (bCranking)
			{
				CrankTime += Dt;
				CrankPhase += 4.0f * Dt;
				if (CrankPhase >= 1.0f)
				{
					CrankPhase -= 1.0f;
					CrankChuff = 1.0f;
				}
				if (CrankTime > 0.62f)
				{
					bCranking = false;
					RevFlare = 1.0f;
					CatchEnv = 1.0f;
					FirePhase = 0.0f;
					PulseEnv = 0.0f;
					IntakeEnv = 0.0f;
				}
			}
			RevFlare = FMath::Max(0.0f, RevFlare - Dt * 1.3f);
			CatchEnv *= FMath::Exp(-Dt * 3.5f);
			CrankChuff *= CrankChuffDecay;

			const bool bRunning = bRunningNow;
			const float RunTarget = bCranking ? 0.16f : (bRunning ? 1.0f : 0.0f);
			RunGain += (RunTarget - RunGain) * RunGainCoef;

			float EffectiveRPM = CurrentRPM;
			EffectiveRPM += IdleWeight * (26.0f * FMath::Sin(TwoPi * 2.7f * Time)
				+ 11.0f * FMath::Sin(TwoPi * 4.3f * Time + 1.2f));
			EffectiveRPM += RevFlare * 1150.0f;
			if (bCranking)
			{
				EffectiveRPM = 300.0f + 70.0f * FMath::Sin(TwoPi * 5.2f * CrankTime);
			}
			EffectiveRPM = FMath::Clamp(EffectiveRPM, 180.0f, 9200.0f);

			// --- firing pulses ---------------------------------------------------
			const float FiringHz = EffectiveRPM / 120.0f;
			FirePhase += FiringHz * Dt;
			if (FirePhase >= 1.0f)
			{
				FirePhase -= 1.0f;
				FireAmp = 1.0f + IdleWeight * 0.22f * Rng.Signed() + 0.045f * Rng.Signed();
				PulseEnv = 1.0f;
				IntakeEnv = 1.0f;
				ValveEnv = 1.0f;
			}
			PulseEnv *= PulseDecay;
			IntakeEnv *= IntakeDecay;
			ValveEnv *= ValveDecay;

			ShiftCut = FMath::Max(0.0f, ShiftCut - Dt);
			ShiftClunk *= ShiftClunkDecay;
			HardPopEnv *= HardPopDecay;
			PopEnv *= PopDecay;
			LandEnv *= LandDecay;

			// --- closed-throttle overrun crackle ---------------------------------
			if (!bCranking && bRunning && CurrentThrottle < 0.05f && CurrentSpeed01 > 0.28f && bGrounded)
			{
				PopCooldown -= Dt;
				if (PopCooldown <= 0.0f)
				{
					PopCooldown = 0.12f + 0.45f * Rng.Next();
					PopEnv = FMath::Max(PopEnv, 0.25f + 0.55f * Rng.Next());
				}
			}
			else
			{
				PopCooldown = FMath::Max(PopCooldown, 0.18f);
			}

			// --- the note --------------------------------------------------------
			const float Ignition = bCranking ? 0.0f
				: (ShiftCut > 0.0f ? 0.22f
					: (EffectiveRPM > 8050.0f
						? 0.55f + 0.45f * (0.5f + 0.5f * FMath::Sin(TwoPi * 17.0f * Time))
						: 1.0f));

			const float W = TwoPi * FirePhase;
			const float PulseShape = 0.18f + 0.82f * FMath::Exp(-FirePhase * 6.2f);
			const float Bright = 0.35f + 0.65f * CurrentThrottle;
			const float Upper = Rpm01 * Rpm01;
			float Tone = FMath::Sin(W)
				+ 0.62f * FMath::Sin(2.0f * W + 0.30f)
				+ (0.30f + 0.30f * Bright) * FMath::Sin(3.0f * W + 1.10f)
				+ (0.18f + 0.22f * Bright) * FMath::Sin(4.0f * W + 2.20f)
				+ (0.10f + 0.18f * Bright) * FMath::Sin(5.0f * W + 0.40f)
				+ (0.06f + 0.14f * Bright) * FMath::Sin(6.0f * W + 2.80f)
				+ (0.04f + 0.10f * Bright) * FMath::Sin(8.0f * W + 1.60f)
				+ Upper * (0.14f * FMath::Sin(9.0f * W + 0.90f)
					+ 0.11f * FMath::Sin(10.0f * W + 2.40f)
					+ 0.09f * FMath::Sin(12.0f * W + 1.30f)
					+ 0.07f * FMath::Sin(14.0f * W + 0.20f)
					+ 0.05f * FMath::Sin(16.0f * W + 2.00f))
				+ IdleWeight * 0.16f * FMath::Sin(0.5f * W + 0.70f);
			Tone *= FireAmp * PulseShape;
			Tone = FMath::Tanh(Tone * (1.25f + 0.95f * CurrentThrottle));

			const float White = Rng.Signed();
			const float ExhaustNoiseRaw = ExhaustNoiseLP.Process(White);
			const float IntakeNoiseRaw = IntakeHi.Process(White) - IntakeLo.Process(White);
			const float WindRaw = WindHi.Process(White) - WindLo.Process(White);
			const float TireRaw = TireHi.Process(White) - TireLo.Process(White);
			const float PopRaw = PopLP.Process(White);
			const float ClickRaw = White - ClickLP.Process(White);
			const float StarterNoise = StarterLP.Process(White);

			const float ResGain = 0.55f + 0.45f * CurrentThrottle;
			// Feed the exhaust formants with both the firing pulse and the note itself:
			// the pulse sets the thump, the note excites the metal "bark" at the header.
			const float ResInput = PulseEnv * 0.75f + Tone * 0.35f;
			const float Res1 = ExhaustRes.Process(ResInput);
			const float Res2 = ExhaustRes2.Process(ResInput);
			const float Body = BodyRes.Process(PulseEnv);

			// Knobby tyre hum: 14 tread blocks per wheel revolution.
			const float WheelHz = 9.0f + 128.0f * CurrentSpeed01;
			WheelPhase = FMath::Fmod(WheelPhase + TwoPi * WheelHz * Dt, TwoPi);
			const float TireHum = (FMath::Sin(WheelPhase) + 0.4f * FMath::Sin(2.0f * WheelPhase + 0.9f))
				* 0.018f * CurrentSpeed01;

			const float EngineGain = (0.20f + 0.10f * Rpm01 + 0.20f * CurrentThrottle) * RunGain * Ignition;
			const float ExhaustGain = (0.035f + 0.16f * CurrentThrottle + 0.045f * Rpm01) * RunGain * Ignition;
			const float IntakeGain = (0.02f + 0.15f * CurrentThrottle) * Rpm01 * RunGain * Ignition;
			const float ValveGain = (0.006f + 0.020f * Rpm01) * RunGain * Ignition;
			const float WindGain = 0.018f + 0.10f * CurrentSpeed01 * CurrentSpeed01;
			const float TireGain = 0.070f * CurrentSpeed01 * (bGrounded ? 1.0f : 0.20f);
			const float ChainGain = 0.012f * CurrentSpeed01 * (bGrounded ? 1.0f : 0.0f);
			const float StarterGain = bCranking ? 0.20f : 0.0f;

			float Mix = Tone * EngineGain;
			Mix += Res1 * EngineGain * 0.95f * ResGain;
			Mix += Res2 * EngineGain * 0.42f * ResGain;
			Mix += Body * EngineGain * 0.80f;
			Mix += ExhaustNoiseRaw * ExhaustGain * (0.40f + 0.60f * PulseEnv);
			Mix += IntakeNoiseRaw * IntakeGain * (0.35f + 0.65f * IntakeEnv);
			Mix += ClickRaw * ValveEnv * ValveGain * 2.2f;
			Mix += WindRaw * WindGain;
			Mix += TireRaw * TireGain;
			Mix += TireHum * (bGrounded ? 1.0f : 0.0f);
			Mix += FMath::Sin(TwoPi * (420.0f + 260.0f * CurrentSpeed01) * Time) * ChainGain;
			// A faint gearbox whine that rises with road speed and the selected gear.
			Mix += FMath::Sin(TwoPi * (240.0f + 95.0f * TargetGear + 180.0f * CurrentSpeed01) * Time)
				* 0.007f * CurrentSpeed01 * (bGrounded ? 1.0f : 0.0f);
			Mix += (FMath::Sin(TwoPi * 320.0f * Time) * 0.55f + StarterNoise * 0.25f) * StarterGain;
			Mix += CrankChuff * StarterNoise * 0.55f;
			Mix += (ClickRaw * 0.50f + PopRaw * 1.20f + FMath::Sin(TwoPi * 68.0f * Time) * 0.50f)
				* (HardPopEnv * 0.55f + PopEnv * 0.25f);
			Mix += (ClickRaw * 0.40f + PopRaw * 0.80f) * ShiftClunk * 0.35f;
			Mix += (PopRaw * 0.90f + FMath::Sin(TwoPi * 72.0f * Time) * 0.70f) * CatchEnv * 0.50f;
			Mix += (FMath::Sin(TwoPi * 62.0f * Time) * 0.25f + PopRaw * 0.20f) * LandEnv;

			// Remove DC and subsonic energy: an engine note should not push the
			// speaker cone out or eat headroom, and the bike is not a subwoofer.
			Mix -= DcBlock.Process(Mix);

			return FMath::Clamp(FMath::Tanh(Mix * 1.10f) * 0.85f, -1.0f, 1.0f);
		}

		TSharedRef<FDAEngineAudioState, ESPMode::ThreadSafe> State;

		const float SampleRate;
		const int32 NumChannels;

		// Smoothed controls (audio-rate).
		float CurrentRPM = 1400.0f;
		float CurrentThrottle = 0.0f;
		float CurrentSpeed01 = 0.0f;
		float TargetRPM = 1400.0f;
		float TargetThrottle = 0.0f;
		float TargetSpeed01 = 0.0f;
		float TargetGear = 1.0f;
		bool bGrounded = true;
		bool bWasGrounded = true;
		bool bRunningNow = false;

		float RpmSmooth = 0.001f;
		float ThrottleSmooth = 0.001f;
		float SpeedSmooth = 0.001f;
		float PulseDecay = 0.999f;
		float IntakeDecay = 0.999f;
		float ValveDecay = 0.99f;
		float HardPopDecay = 0.999f;
		float PopDecay = 0.999f;
		float LandDecay = 0.999f;
		float ShiftClunkDecay = 0.999f;
		float CrankChuffDecay = 0.999f;
		float RunGainCoef = 0.001f;

		// Engine state.
		float RunGain = 0.0f;
		float FirePhase = 0.0f;
		float FireAmp = 1.0f;
		float PulseEnv = 0.0f;
		float IntakeEnv = 0.0f;
		float ValveEnv = 0.0f;
		float RevFlare = 0.0f;
		float CatchEnv = 0.0f;
		float LandEnv = 0.0f;
		float ShiftCut = 0.0f;
		float ShiftClunk = 0.0f;
		float HardPopEnv = 0.0f;
		float PopEnv = 0.0f;
		float PopCooldown = 0.0f;
		float WheelPhase = 0.0f;
		float Time = 0.0f;

		// Starter.
		bool bCranking = false;
		float CrankTime = 0.0f;
		float CrankPhase = 0.0f;
		float CrankChuff = 0.0f;

		// Event counters (the audio thread consumes one increment per event).
		uint32 LastStartSeq = 0;
		uint32 LastStopSeq = 0;
		uint32 LastShiftSeq = 0;
		uint32 LastPopSeq = 0;

		FOnePole ExhaustNoiseLP;
		FOnePole IntakeHi;
		FOnePole IntakeLo;
		FOnePole WindHi;
		FOnePole WindLo;
		FOnePole TireHi;
		FOnePole TireLo;
		FOnePole PopLP;
		FOnePole ClickLP;
		FOnePole StarterLP;
		FOnePole DcBlock;
		FBandPass ExhaustRes;
		FBandPass ExhaustRes2;
		FBandPass BodyRes;

		FXorShift32 Rng;
	};
}

// ------------------------------------------------------------------------ component

UDAEngineSynthComponent::UDAEngineSynthComponent(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryComponentTick.bCanEverTick = false;
	bAutoDestroy = false;
	bStopWhenOwnerDestroyed = true;
	bAllowSpatialization = true;
	bOverrideAttenuation = true;
	bIsUISound = false;
	NumChannels = 1;
	PreferredBufferLength = 512;

	// A single-cylinder bike in the open air: generous near field, natural
	// dB falloff, so it fades naturally as the player rides away from it.
	AttenuationOverrides.bAttenuate = true;
	AttenuationOverrides.bSpatialize = true;
	AttenuationOverrides.bAttenuateWithLPF = true;
	AttenuationOverrides.DistanceAlgorithm = EAttenuationDistanceModel::NaturalSound;
	AttenuationOverrides.AttenuationShape = EAttenuationShape::Sphere;
	AttenuationOverrides.AttenuationShapeExtents = FVector(260.0f, 0.0f, 0.0f);
	AttenuationOverrides.FalloffDistance = 4200.0f;
	AttenuationOverrides.dBAttenuationAtMax = -60.0f;
	AttenuationOverrides.LPFRadiusMin = 600.0f;
	AttenuationOverrides.LPFRadiusMax = 4200.0f;
	AttenuationOverrides.LPFFrequencyAtMin = 16000.0f;
	AttenuationOverrides.LPFFrequencyAtMax = 4200.0f;

	AudioState = MakeShared<FDAEngineAudioState, ESPMode::ThreadSafe>();
}

UDAEngineSynthComponent::~UDAEngineSynthComponent() = default;

void UDAEngineSynthComponent::SetEngineState(const FDAEngineAudioParams& Params)
{
	if (AudioState.IsValid())
	{
		AudioState->Set(Params);
	}
}

void UDAEngineSynthComponent::StartEngine()
{
	if (!AudioState.IsValid())
	{
		return;
	}

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(StopTimer);
	}

	AudioState->SetRunning(true);
	AudioState->TriggerStart();

	if (!IsPlaying())
	{
		Start();
	}
	SetVolumeMultiplier(1.0f);
	FadeIn(0.06f, 1.0f, 0.0f, EAudioFaderCurve::Linear);
}

void UDAEngineSynthComponent::StopEngine(float FadeSeconds)
{
	if (!AudioState.IsValid())
	{
		return;
	}

	AudioState->SetRunning(false);
	AudioState->TriggerStop();
	FadeOut(FadeSeconds, 0.0f, EAudioFaderCurve::Linear);

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(StopTimer, this, &UDAEngineSynthComponent::FinishStop,
			FMath::Max(FadeSeconds, 0.05f) + 0.05f, false);
	}
	else
	{
		FinishStop();
	}
}

void UDAEngineSynthComponent::TriggerShift()
{
	if (AudioState.IsValid())
	{
		AudioState->TriggerShift();
	}
}

void UDAEngineSynthComponent::TriggerExhaustPop()
{
	if (AudioState.IsValid())
	{
		AudioState->TriggerPop();
	}
}

void UDAEngineSynthComponent::FinishStop()
{
	Stop();
}

bool UDAEngineSynthComponent::Init(int32& SampleRate)
{
	NumChannels = 1;
	PreferredBufferLength = 512;
	return true;
}

ISoundGeneratorPtr UDAEngineSynthComponent::CreateSoundGenerator(const FSoundGeneratorInitParams& InParams)
{
	if (!AudioState.IsValid())
	{
		AudioState = MakeShared<FDAEngineAudioState, ESPMode::ThreadSafe>();
	}
	return MakeShared<FDAMotorcycleSynth, ESPMode::ThreadSafe>(InParams, AudioState.ToSharedRef());
}

bool UDAEngineSynthComponent::RenderOfflineTest(const FString& WavPath, FString& OutSummary)
{
	constexpr int32 SampleRate = 48000;
	constexpr int32 BlockSize = 512;
	constexpr float Seconds = 8.0f;
	const int32 TotalSamples = static_cast<int32>(SampleRate * Seconds);

	TSharedRef<FDAEngineAudioState, ESPMode::ThreadSafe> State =
		MakeShared<FDAEngineAudioState, ESPMode::ThreadSafe>();
	State->SetRunning(true);
	State->TriggerStart();

	FSoundGeneratorInitParams Init;
	Init.SampleRate = static_cast<float>(SampleRate);
	Init.NumChannels = 1;
	Init.NumFramesPerCallback = BlockSize;
	Init.AudioComponentId = 0xDAB1CE;
	Init.InstanceID = 0xB1CE;
	TSharedRef<FDAMotorcycleSynth, ESPMode::ThreadSafe> Synth =
		MakeShared<FDAMotorcycleSynth, ESPMode::ThreadSafe>(Init, State);

	TArray<float> Samples;
	Samples.Reserve(TotalSamples);
	TArray<float> Block;
	Block.SetNumZeroed(BlockSize);

	double SumSq[4] = { 0.0, 0.0, 0.0, 0.0 };
	int32 Count[4] = { 0, 0, 0, 0 };
	float Peak = 0.f;
	int32 NonFinite = 0;
	int32 Clipped = 0;

	for (int32 Start = 0; Start < TotalSamples; Start += BlockSize)
	{
		const float T = static_cast<float>(Start) / SampleRate;

		FDAEngineAudioParams P;
		P.RPM = 1400.f;
		P.Throttle = 0.02f;
		P.Speed = 0.f;
		P.Speed01 = 0.f;
		P.Gear = 1.f;
		if (T >= 1.6f && T < 3.0f)
		{
			const float U = (T - 1.6f) / 1.4f;
			P.RPM = FMath::Lerp(1600.f, 6400.f, U);
			P.Throttle = FMath::Lerp(0.15f, 1.0f, U);
			P.Speed = FMath::Lerp(250.f, 1650.f, U);
			P.Speed01 = P.Speed / 2200.f;
			P.Gear = 3.f;
		}
		else if (T >= 3.0f && T < 5.0f)
		{
			P.RPM = 6900.f;
			P.Throttle = 1.0f;
			P.Speed = 2150.f;
			P.Speed01 = P.Speed / 2200.f;
			P.Gear = 5.f;
		}
		else if (T >= 5.0f && T < 6.0f)
		{
			P.RPM = 4300.f;
			P.Throttle = 0.0f;
			P.Speed = 1650.f;
			P.Speed01 = P.Speed / 2200.f;
			P.Gear = 4.f;
			P.bBraking = true;
		}
		else if (T >= 6.0f && T < 7.0f)
		{
			P.RPM = 2600.f;
			P.Throttle = 0.0f;
			P.Speed = 650.f;
			P.Speed01 = P.Speed / 2200.f;
			P.Gear = 2.f;
			P.bBraking = true;
		}
		else if (T >= 7.0f)
		{
			P.RPM = 1400.f;
			P.Throttle = 0.f;
		}
		State->Set(P);

		if (T >= 6.1f && T < 6.1f + 1.f / 120.f)
		{
			State->TriggerShift();
		}
		if ((T >= 5.1f && T < 5.1f + 1.f / 120.f) || (T >= 5.4f && T < 5.4f + 1.f / 120.f))
		{
			State->TriggerPop();
		}
		if (T >= 7.2f && T < 7.2f + 1.f / 120.f)
		{
			State->SetRunning(false);
			State->TriggerStop();
		}

		const int32 Generated = Synth->OnGenerateAudio(Block.GetData(), BlockSize);
		if (Generated != BlockSize)
		{
			return false;
		}

		for (int32 i = 0; i < BlockSize; ++i)
		{
			const float Sample = Block[i];
			if (!FMath::IsFinite(Sample))
			{
				++NonFinite;
				continue;
			}
			const float Abs = FMath::Abs(Sample);
			Peak = FMath::Max(Peak, Abs);
			if (Abs >= 0.999f)
			{
				++Clipped;
			}
			const float Time = T + static_cast<float>(i) / SampleRate;
			const int32 Segment = Time < 1.6f ? 0 : (Time < 5.0f ? 1 : (Time < 7.0f ? 2 : 3));
			SumSq[Segment] += static_cast<double>(Sample) * Sample;
			++Count[Segment];
		}
		Samples.Append(Block);
	}

	auto Rms = [&](int32 Segment)
	{
		return Count[Segment] > 0 ? static_cast<float>(FMath::Sqrt(SumSq[Segment] / Count[Segment])) : 0.f;
	};
	const float IdleRms = Rms(0);
	const float RevRms = Rms(1);
	const float OverrunRms = Rms(2);
	const float StopRms = Rms(3);

	// 16-bit mono WAV.
	TArray<uint8> Wav;
	const int32 DataBytes = Samples.Num() * 2;
	Wav.Reserve(44 + DataBytes);
	auto Put32 = [&Wav](uint32 V)
	{
		Wav.Add(static_cast<uint8>(V & 0xff));
		Wav.Add(static_cast<uint8>((V >> 8) & 0xff));
		Wav.Add(static_cast<uint8>((V >> 16) & 0xff));
		Wav.Add(static_cast<uint8>((V >> 24) & 0xff));
	};
	auto Put16 = [&Wav](uint16 V)
	{
		Wav.Add(static_cast<uint8>(V & 0xff));
		Wav.Add(static_cast<uint8>((V >> 8) & 0xff));
	};
	Wav.Append(reinterpret_cast<const uint8*>("RIFF"), 4);
	Put32(36 + DataBytes);
	Wav.Append(reinterpret_cast<const uint8*>("WAVE"), 4);
	Wav.Append(reinterpret_cast<const uint8*>("fmt "), 4);
	Put32(16);
	Put16(1);
	Put16(1);
	Put32(SampleRate);
	Put32(SampleRate * 2);
	Put16(2);
	Put16(16);
	Wav.Append(reinterpret_cast<const uint8*>("data"), 4);
	Put32(DataBytes);
	for (const float Sample : Samples)
	{
		const int32 Value = FMath::Clamp(static_cast<int32>(FMath::RoundToInt(Sample * 32767.f)), -32768, 32767);
		Put16(static_cast<uint16>(Value & 0xffff));
	}
	const bool bSaved = FFileHelper::SaveArrayToFile(Wav, *WavPath);

	OutSummary = FString::Printf(
		TEXT("peak=%.3f idleRms=%.4f revRms=%.4f overrunRms=%.4f stopRms=%.4f nonFinite=%d clipped=%d saved=%s path=%s"),
		Peak, IdleRms, RevRms, OverrunRms, StopRms, NonFinite, Clipped,
		bSaved ? TEXT("yes") : TEXT("no"), *WavPath);

	return bSaved && NonFinite == 0 && Peak > 0.05f && Peak <= 0.95f
		&& Clipped < TotalSamples / 100
		&& IdleRms > 0.004f && RevRms > IdleRms * 1.1f && RevRms < 0.60f;
}

