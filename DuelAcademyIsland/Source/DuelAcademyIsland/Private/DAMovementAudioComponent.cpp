// Duel Academy Island - procedural on-foot movement audio.

#include "DAMovementAudioComponent.h"

#include "Components/CapsuleComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "DAAvatarComponent.h"
#include "DAIslandSubsystem.h"
#include "DAStudentCharacter.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Sound/SoundAttenuation.h"

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

	/** Chamberlin state-variable band-pass; stable for the low-Q resonances used here. */
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

	enum class EEventType : uint8
	{
		Step = 0,
		Land = 1,
		Jump = 2,
		SplashIn = 3,
		SplashOut = 4,
		Stroke = 5,
		Tread = 6
	};

	FORCEINLINE uint8 Quantise01(float Value)
	{
		return static_cast<uint8>(FMath::Clamp(Value, 0.f, 1.f) * 255.f + 0.5f);
	}

	FORCEINLINE float Dequantise01(uint8 Value)
	{
		return static_cast<float>(Value) * (1.0f / 255.0f);
	}

	uint32 PackEvent(EEventType Type, EDAMovementSurface Surface, bool bLeft, float Intensity, float Water01, uint8 Variant)
	{
		uint32 Packed = static_cast<uint32>(Type) & 0x7u;
		Packed |= (static_cast<uint32>(Surface) & 0xfu) << 3;
		Packed |= (bLeft ? 1u : 0u) << 7;
		Packed |= static_cast<uint32>(Quantise01(Intensity)) << 8;
		Packed |= static_cast<uint32>(Quantise01(Water01)) << 16;
		Packed |= static_cast<uint32>(Variant) << 24;
		return Packed;
	}

	EEventType EventTypeOf(uint32 Event) { return static_cast<EEventType>(Event & 0x7u); }
	EDAMovementSurface EventSurfaceOf(uint32 Event) { return static_cast<EDAMovementSurface>((Event >> 3) & 0xfu); }
	bool EventIsLeft(uint32 Event) { return ((Event >> 7) & 1u) != 0; }
	float EventIntensity(uint32 Event) { return Dequantise01(static_cast<uint8>((Event >> 8) & 0xffu)); }
	float EventWater(uint32 Event) { return Dequantise01(static_cast<uint8>((Event >> 16) & 0xffu)); }

	struct FBubble
	{
		float Start = 0.f;
		float Duration = 0.f;
		float Freq0 = 0.f;
		float Sweep = 0.f;
		float Amp = 0.f;
	};

	struct FSurfaceSpec
	{
		float LowFreq = 70.f;
		float LowGain = 0.2f;
		float LowDecay = 26.f;
		float BandLo = 180.f;
		float BandHi = 2500.f;
		float NoiseGain = 0.2f;
		float NoiseDecay = 24.f;
		float ClickGain = 0.03f;
		float ClickDecay = 90.f;
		float Res1Hz = 0.f;
		float Res1Q = 1.f;
		float Res2Hz = 0.f;
		float Res2Q = 1.f;
		float ResGain = 0.f;
		float ResDecay = 20.f;
		float Duration = 0.3f;
		float Grain = 0.f;
	};

	FSurfaceSpec SpecFor(EDAMovementSurface Surface)
	{
		FSurfaceSpec S;
		switch (Surface)
		{
		case EDAMovementSurface::Grass:
			S = { 70.f, 0.20f, 28.f, 180.f, 2100.f, 0.20f, 26.f, 0.02f, 90.f, 1200.f, 2.0f, 2500.f, 3.0f, 0.03f, 30.f, 0.28f, 0.f };
			break;
		case EDAMovementSurface::Dirt:
			S = { 76.f, 0.22f, 24.f, 250.f, 3800.f, 0.24f, 22.f, 0.05f, 70.f, 0.f, 1.f, 0.f, 1.f, 0.f, 20.f, 0.30f, 0.15f };
			break;
		case EDAMovementSurface::Gravel:
			S = { 82.f, 0.18f, 22.f, 500.f, 5600.f, 0.30f, 30.f, 0.09f, 80.f, 0.f, 1.f, 0.f, 1.f, 0.f, 20.f, 0.32f, 0.55f };
			break;
		case EDAMovementSurface::Sand:
			S = { 60.f, 0.15f, 20.f, 120.f, 1600.f, 0.13f, 16.f, 0.02f, 100.f, 0.f, 1.f, 0.f, 1.f, 0.f, 20.f, 0.32f, 0.f };
			break;
		case EDAMovementSurface::Stone:
			S = { 92.f, 0.27f, 32.f, 600.f, 5200.f, 0.20f, 38.f, 0.11f, 110.f, 1800.f, 1.6f, 3200.f, 2.5f, 0.10f, 35.f, 0.24f, 0.f };
			break;
		case EDAMovementSurface::Wood:
			S = { 82.f, 0.25f, 26.f, 240.f, 2800.f, 0.16f, 26.f, 0.07f, 90.f, 420.f, 5.0f, 1150.f, 6.0f, 0.65f, 24.f, 0.34f, 0.f };
			break;
		case EDAMovementSurface::Metal:
			S = { 105.f, 0.16f, 20.f, 800.f, 7000.f, 0.15f, 20.f, 0.08f, 100.f, 2500.f, 9.0f, 4700.f, 12.0f, 0.45f, 12.f, 0.55f, 0.f };
			break;
		case EDAMovementSurface::Carpet:
			S = { 58.f, 0.11f, 18.f, 90.f, 900.f, 0.09f, 14.f, 0.f, 100.f, 0.f, 1.f, 0.f, 1.f, 0.f, 20.f, 0.30f, 0.f };
			break;
		case EDAMovementSurface::ShallowWater:
			S = { 76.f, 0.09f, 16.f, 350.f, 7000.f, 0.34f, 11.f, 0.02f, 100.f, 900.f, 0.8f, 2400.f, 1.2f, 0.10f, 14.f, 0.52f, 0.f };
			break;
		case EDAMovementSurface::DeepWater:
		default:
			S = { 70.f, 0.06f, 14.f, 300.f, 6500.f, 0.30f, 9.f, 0.01f, 100.f, 700.f, 0.8f, 1800.f, 1.2f, 0.08f, 10.f, 0.62f, 0.f };
			break;
		}
		return S;
	}

	/** One short impact voice: body thump, surface noise, click and (optionally) bubbles. */
	struct FImpactVoice
	{
		bool bActive = false;
		float Age = 0.f;
		float Duration = 0.3f;
		float Attack = 0.006f;
		float Pitch = 1.f;
		float LowPhase = 0.f;
		float LowFreq = 70.f;
		float LowGain = 0.f;
		float LowEnv = 0.f;
		float LowDecay = 0.f;
		float NoiseGain = 0.f;
		float NoiseEnv = 0.f;
		float NoiseDecay = 0.f;
		float ClickGain = 0.f;
		float ClickEnv = 0.f;
		float ClickDecay = 0.f;
		float ResGain = 0.f;
		float ResEnv = 0.f;
		float ResDecay = 0.f;
		float WaterGain = 0.f;
		float WaterEnv = 0.f;
		float WaterDecay = 0.f;
		float Grain = 0.f;
		float GrainPhase = 0.f;
		FBubble Bubbles[3];

		FOnePole Hi;
		FOnePole Lo;
		FOnePole ClickLP;
		FOnePole WaterHi;
		FOnePole WaterLo;
		FBandPass Res1;
		FBandPass Res2;

		void Start(EDAMovementSurface Surface, float Intensity, bool bLeft, float Water01, bool bHeavy,
			float SampleRate, float MaxPitch, FXorShift32& Rng)
		{
			const FSurfaceSpec S = SpecFor(Surface);
			const float I = FMath::Clamp(Intensity, 0.05f, 1.25f);
			const float Heavy = bHeavy ? 1.0f : 0.0f;
			const float Wet = FMath::Clamp(FMath::Max(Water01, (Surface == EDAMovementSurface::ShallowWater
				|| Surface == EDAMovementSurface::DeepWater) ? 1.f : 0.f), 0.f, 1.f);

			bActive = true;
			Age = 0.f;
			Pitch = FMath::Lerp(0.94f, MaxPitch, Rng.Next()) * (bHeavy ? 0.90f : 1.0f)
				* (bLeft ? 0.985f : 1.015f);
			Duration = S.Duration * (0.88f + 0.24f * Rng.Next()) * (bHeavy ? 1.25f : 1.0f);
			Attack = 0.003f + 0.009f * Rng.Next();

			LowFreq = S.LowFreq * Pitch;
			LowGain = S.LowGain * I * (bHeavy ? 1.85f : 1.0f);
			LowEnv = 1.f;
			LowDecay = FMath::Exp(-S.LowDecay * (bHeavy ? 0.72f : 1.0f) / SampleRate);
			LowPhase = 0.f;

			Hi.Init(S.BandHi, SampleRate);
			Lo.Init(S.BandLo, SampleRate);
			NoiseGain = S.NoiseGain * I * (bHeavy ? 1.25f : 1.0f) * (1.f + 0.35f * Wet);
			NoiseEnv = 1.f;
			NoiseDecay = FMath::Exp(-S.NoiseDecay / SampleRate);

			ClickLP.Init(2600.f, SampleRate);
			ClickGain = S.ClickGain * I * (1.f + 0.45f * Wet);
			ClickEnv = 1.f;
			ClickDecay = FMath::Exp(-S.ClickDecay / SampleRate);

			ResGain = S.ResGain * I;
			ResEnv = 1.f;
			ResDecay = FMath::Exp(-S.ResDecay / SampleRate);
			Res1.Init(S.Res1Hz, S.Res1Q, SampleRate);
			Res2.Init(S.Res2Hz, S.Res2Q, SampleRate);

			WaterHi.Init(7000.f, SampleRate);
			WaterLo.Init(260.f, SampleRate);
			WaterGain = Wet * I * 0.22f;
			WaterEnv = 1.f;
			WaterDecay = FMath::Exp(-(Surface == EDAMovementSurface::DeepWater ? 8.f : 12.f) / SampleRate);

			Grain = S.Grain;
			GrainPhase = Rng.Next() * TwoPi;

			for (FBubble& B : Bubbles)
			{
				B = FBubble();
			}
			if (Wet > 0.02f)
			{
				const int32 Count = FMath::Clamp(2 + FMath::RoundToInt(Wet * 2.f), 2, 3);
				for (int32 i = 0; i < Count; ++i)
				{
					FBubble& B = Bubbles[i];
					B.Start = (0.015f + 0.16f * Rng.Next()) * (bHeavy ? 1.4f : 1.f);
					B.Duration = 0.035f + 0.075f * Rng.Next();
					B.Freq0 = FMath::Lerp(280.f, 950.f, Rng.Next());
					B.Sweep = 0.8f + 1.8f * Rng.Next();
					B.Amp = (0.10f + 0.20f * Rng.Next()) * I * Wet;
				}
			}
		}

		FORCEINLINE float Render(float Dt, FXorShift32& Rng)
		{
			if (!bActive)
			{
				return 0.f;
			}
			Age += Dt;
			if (Age >= Duration)
			{
				bActive = false;
				return 0.f;
			}

			LowEnv *= LowDecay;
			NoiseEnv *= NoiseDecay;
			ClickEnv *= ClickDecay;
			ResEnv *= ResDecay;
			WaterEnv *= WaterDecay;

			const float White = Rng.Signed();
			const float Band = Hi.Process(White) - Lo.Process(White);
			const float Click = White - ClickLP.Process(White);
			const float ResInput = Click * 0.82f + Band * 0.18f;
			const float Res = Res1.Process(ResInput) * 0.72f + Res2.Process(ResInput) * 0.52f;
			const float Wet = WaterHi.Process(White) - WaterLo.Process(White);

			LowPhase = FMath::Fmod(LowPhase + TwoPi * LowFreq * Dt, TwoPi);
			const float Thump = FMath::Sin(LowPhase);

			float BandGain = NoiseGain * NoiseEnv;
			if (Grain > 0.f)
			{
				// Loose gravel / dirt: rapid micro-impulses inside the noise burst.
				const float GrainMod = 0.62f + 0.38f * FMath::Sin(GrainPhase + Age * (180.f + 90.f * Grain));
				BandGain *= FMath::Lerp(1.f, GrainMod, Grain);
			}

			const float AttackGain = FMath::Clamp(Age / FMath::Max(Attack, 1e-4f), 0.f, 1.f);
			float Out = Thump * LowGain * LowEnv
				+ Band * BandGain
				+ Click * ClickGain * ClickEnv
				+ Res * ResGain * ResEnv
				+ Wet * WaterGain * WaterEnv;

			for (const FBubble& B : Bubbles)
			{
				if (B.Duration <= 0.f || Age < B.Start || Age >= B.Start + B.Duration)
				{
					continue;
				}
				const float U = (Age - B.Start) / B.Duration;
				const float Tau = Age - B.Start;
				const float Phase = TwoPi * (B.Freq0 * Tau + 0.5f * B.Freq0 * B.Sweep * Tau * Tau);
				Out += FMath::Sin(Phase) * FMath::Sin(PI * U) * B.Amp;
			}
			return Out * AttackGain;
		}
	};
}

/**
 * Game-thread -> audio-render-thread parameter block. Scalars are atomics so a
 * tick can update the whole snapshot without locks or tearing; impact events
 * travel through a small single-producer/single-consumer ring.
 */
class FDAMovementAudioState
{
public:
	static constexpr uint32 EventCapacity = 64;

	void Set(const FDAMovementAudioParams& P)
	{
		Speed.store(P.Speed, std::memory_order_relaxed);
		Speed01.store(P.Speed01, std::memory_order_relaxed);
		Phase.store(P.Phase, std::memory_order_relaxed);
		Cadence.store(P.Cadence, std::memory_order_relaxed);
		WaterDepth.store(P.WaterDepth, std::memory_order_relaxed);
		VerticalSpeed.store(P.VerticalSpeed, std::memory_order_relaxed);
		Grounded.store(P.bGrounded, std::memory_order_relaxed);
		Swimming.store(P.bSwimming, std::memory_order_relaxed);
		Wading.store(P.bWading, std::memory_order_relaxed);
		Moving.store(P.bMoving, std::memory_order_relaxed);
		Riding.store(P.bRiding, std::memory_order_relaxed);
		Indoors.store(P.bIndoors, std::memory_order_relaxed);
		Sprinting.store(P.bSprinting, std::memory_order_relaxed);
		Surface.store(static_cast<uint8>(P.Surface), std::memory_order_relaxed);
	}

	FDAMovementAudioParams Get() const
	{
		FDAMovementAudioParams P;
		P.Speed = Speed.load(std::memory_order_relaxed);
		P.Speed01 = Speed01.load(std::memory_order_relaxed);
		P.Phase = Phase.load(std::memory_order_relaxed);
		P.Cadence = Cadence.load(std::memory_order_relaxed);
		P.WaterDepth = WaterDepth.load(std::memory_order_relaxed);
		P.VerticalSpeed = VerticalSpeed.load(std::memory_order_relaxed);
		P.bGrounded = Grounded.load(std::memory_order_relaxed);
		P.bSwimming = Swimming.load(std::memory_order_relaxed);
		P.bWading = Wading.load(std::memory_order_relaxed);
		P.bMoving = Moving.load(std::memory_order_relaxed);
		P.bRiding = Riding.load(std::memory_order_relaxed);
		P.bIndoors = Indoors.load(std::memory_order_relaxed);
		P.bSprinting = Sprinting.load(std::memory_order_relaxed);
		P.Surface = static_cast<EDAMovementSurface>(Surface.load(std::memory_order_relaxed));
		return P;
	}

	void PostEvent(uint32 Event)
	{
		const uint32 Seq = EventSequence.load(std::memory_order_relaxed);
		EventData[Seq % EventCapacity].store(Event, std::memory_order_relaxed);
		EventSequence.store(Seq + 1, std::memory_order_release);
	}

	uint32 GetEventSequence() const { return EventSequence.load(std::memory_order_acquire); }
	uint32 GetEvent(uint32 Seq) const { return EventData[Seq % EventCapacity].load(std::memory_order_relaxed); }

private:
	std::atomic<float> Speed{ 0.f };
	std::atomic<float> Speed01{ 0.f };
	std::atomic<float> Phase{ 0.f };
	std::atomic<float> Cadence{ 0.f };
	std::atomic<float> WaterDepth{ 0.f };
	std::atomic<float> VerticalSpeed{ 0.f };
	std::atomic<bool> Grounded{ true };
	std::atomic<bool> Swimming{ false };
	std::atomic<bool> Wading{ false };
	std::atomic<bool> Moving{ false };
	std::atomic<bool> Riding{ false };
	std::atomic<bool> Indoors{ false };
	std::atomic<bool> Sprinting{ false };
	std::atomic<uint8> Surface{ static_cast<uint8>(EDAMovementSurface::Grass) };
	std::atomic<uint32> EventSequence{ 0 };
	std::atomic<uint32> EventData[EventCapacity];
};

namespace
{
	/** One generator instance: impact voices plus cloth, breath, wind and water. */
	class FDAMovementSynth final : public ISoundGenerator
	{
	public:
		FDAMovementSynth(const FSoundGeneratorInitParams& InParams,
			const TSharedRef<FDAMovementAudioState, ESPMode::ThreadSafe>& InState)
			: State(InState)
			, SampleRate(FMath::Max(InParams.SampleRate, 8000.0f))
			, NumChannels(FMath::Max(InParams.NumChannels, 1))
		{
			Rng.State = 0x9E3779B9u ^ static_cast<uint32>(InParams.InstanceID) ^ (static_cast<uint32>(InParams.AudioComponentId) << 7);
			// Events posted before this generator existed belong to an old audio
			// device / component and must not replay on a restart.
			LastEventSequence = State->GetEventSequence();
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
		static constexpr int32 MaxVoices = 6;

		void InitFilters()
		{
			ClothHi.Init(3800.f, SampleRate);
			ClothLo.Init(420.f, SampleRate);
			WindHi.Init(7600.f, SampleRate);
			WindLo.Init(1100.f, SampleRate);
			WaterHi.Init(6200.f, SampleRate);
			WaterLo.Init(240.f, SampleRate);
			BreathHi.Init(1700.f, SampleRate);
			BreathLo.Init(280.f, SampleRate);
			DcBlock.Init(24.f, SampleRate);
		}

		void PumpState()
		{
			const FDAMovementAudioParams P = State->Get();
			TargetSpeed = FMath::Max(0.f, P.Speed);
			TargetSpeed01 = FMath::Clamp(P.Speed01, 0.f, 1.f);
			TargetPhase = FMath::Frac(FMath::Max(0.f, P.Phase));
			TargetCadence = FMath::Max(0.f, P.Cadence);
			TargetWaterDepth = P.WaterDepth;
			TargetVertical = P.VerticalSpeed;
			bGrounded = P.bGrounded;
			bSwimming = P.bSwimming;
			bWading = P.bWading;
			bMoving = P.bMoving;
			bRiding = P.bRiding;
			bIndoors = P.bIndoors;
			bSprinting = P.bSprinting;
			TargetSurface = P.Surface;

			const uint32 Seq = State->GetEventSequence();
			uint32 Guard = 0;
			while (LastEventSequence < Seq && Guard++ < FDAMovementAudioState::EventCapacity)
			{
				HandleEvent(State->GetEvent(LastEventSequence));
				++LastEventSequence;
			}
			if (LastEventSequence < Seq)
			{
				LastEventSequence = Seq;   // the audio thread stalled; do not replay a wrapped ring forever
			}
		}

		void HandleEvent(uint32 Event)
		{
			const EEventType Type = EventTypeOf(Event);
			const EDAMovementSurface Surface = EventSurfaceOf(Event);
			const bool bLeft = EventIsLeft(Event);
			const float Intensity = EventIntensity(Event);
			const float Water = EventWater(Event);
			const bool bHeavy = Type == EEventType::Land || Type == EEventType::SplashIn;

			int32 Slot = INDEX_NONE;
			for (int32 i = 0; i < MaxVoices; ++i)
			{
				if (!Voices[i].bActive)
				{
					Slot = i;
					break;
				}
			}
			if (Slot == INDEX_NONE)
			{
				float Oldest = -1.f;
				for (int32 i = 0; i < MaxVoices; ++i)
				{
					if (Voices[i].Age > Oldest)
					{
						Oldest = Voices[i].Age;
						Slot = i;
					}
				}
			}
			if (Slot == INDEX_NONE)
			{
				return;
			}

			EDAMovementSurface VoiceSurface = Surface;
			float VoiceIntensity = Intensity;
			float VoiceWater = Water;
			switch (Type)
			{
			case EEventType::Jump:
				VoiceIntensity *= 0.45f;
				VoiceWater = 0.f;
				break;
			case EEventType::SplashOut:
				VoiceSurface = EDAMovementSurface::ShallowWater;
				VoiceIntensity *= 0.65f;
				VoiceWater = 0.75f;
				break;
			case EEventType::Stroke:
			case EEventType::Tread:
				VoiceSurface = EDAMovementSurface::DeepWater;
				VoiceWater = 1.f;
				break;
			case EEventType::SplashIn:
				VoiceSurface = EDAMovementSurface::ShallowWater;
				VoiceWater = 1.f;
				break;
			default:
				break;
			}

			Voices[Slot].Start(VoiceSurface, VoiceIntensity, bLeft, VoiceWater, bHeavy,
				SampleRate, 1.06f, Rng);
		}

		FORCEINLINE float RenderSample()
		{
			const float Dt = 1.0f / SampleRate;
			Time += Dt;

			CurrentSpeed += (TargetSpeed - CurrentSpeed) * SpeedSmooth;
			CurrentSpeed01 += (TargetSpeed01 - CurrentSpeed01) * SpeedSmooth;
			CurrentWaterDepth += (TargetWaterDepth - CurrentWaterDepth) * WaterSmooth;

			if (bRiding)
			{
				for (FImpactVoice& Voice : Voices)
				{
					Voice.bActive = false;
				}
				return 0.f;
			}

			const float Speed01 = FMath::Clamp(CurrentSpeed01, 0.f, 1.f);
			const bool bLand = !bSwimming;
			const bool bNearWater = !bIndoors && CurrentWaterDepth > -180.f && CurrentWaterDepth < 260.f;

			const float White = Rng.Signed();
			const float Cloth = ClothHi.Process(White) - ClothLo.Process(White);
			const float Wind = WindHi.Process(White) - WindLo.Process(White);
			const float Water = WaterHi.Process(White) - WaterLo.Process(White);
			const float Breath = BreathHi.Process(White) - BreathLo.Process(White);

			const float ClothGain = (bMoving && bLand)
				? (0.006f + 0.020f * Speed01) * (0.74f + 0.26f * FMath::Sin(TwoPi * 2.f * TargetPhase))
				: 0.0012f;
			const float WindGain = (bIndoors ? 0.12f : 1.f) * (0.0035f + 0.024f * Speed01 * Speed01);
			const float BreathRate = 0.22f + 0.22f * Speed01;
			BreathPhase = FMath::Fmod(BreathPhase + TwoPi * BreathRate * Dt, TwoPi);
			const float BreathShape = FMath::Max(0.f, FMath::Sin(BreathPhase));
			const float BreathGain = (0.0025f + 0.020f * Speed01) * BreathShape * BreathShape;

			const float WaterLfo = FMath::Clamp(
				0.55f + 0.30f * FMath::Sin(TwoPi * 0.11f * Time)
				+ 0.15f * FMath::Sin(TwoPi * 0.27f * Time + 1.3f), 0.f, 1.f);
			float WaterGain = 0.f;
			if (bSwimming)
			{
				WaterGain = 0.025f + 0.060f * Speed01;
			}
			else if (bWading)
			{
				WaterGain = 0.015f + 0.035f * Speed01;
			}
			else if (bNearWater)
			{
				WaterGain = 0.003f + 0.004f * WaterLfo;
			}
			WaterGain *= (0.70f + 0.30f * WaterLfo);

			float Mix = Cloth * ClothGain + Wind * WindGain + Breath * BreathGain + Water * WaterGain;
			for (FImpactVoice& Voice : Voices)
			{
				Mix += Voice.Render(Dt, Rng);
			}

			Mix -= DcBlock.Process(Mix);
			return FMath::Clamp(FMath::Tanh(Mix * 1.15f) * 0.90f, -1.f, 1.f);
		}

		TSharedRef<FDAMovementAudioState, ESPMode::ThreadSafe> State;

		const float SampleRate;
		const int32 NumChannels;

		float TargetSpeed = 0.f;
		float TargetSpeed01 = 0.f;
		float TargetPhase = 0.f;
		float TargetCadence = 0.f;
		float TargetWaterDepth = 0.f;
		float TargetVertical = 0.f;
		EDAMovementSurface TargetSurface = EDAMovementSurface::Grass;
		bool bGrounded = true;
		bool bSwimming = false;
		bool bWading = false;
		bool bMoving = false;
		bool bRiding = false;
		bool bIndoors = false;
		bool bSprinting = false;

		float CurrentSpeed = 0.f;
		float CurrentSpeed01 = 0.f;
		float CurrentWaterDepth = 0.f;
		float SpeedSmooth = 0.001f;
		float WaterSmooth = 0.001f;
		float BreathPhase = 0.f;
		float Time = 0.f;

		uint32 LastEventSequence = 0;

		FImpactVoice Voices[MaxVoices];

		FOnePole ClothHi;
		FOnePole ClothLo;
		FOnePole WindHi;
		FOnePole WindLo;
		FOnePole WaterHi;
		FOnePole WaterLo;
		FOnePole BreathHi;
		FOnePole BreathLo;
		FOnePole DcBlock;

		FXorShift32 Rng;
	};
}

// ------------------------------------------------------------------------ component

UDAMovementAudioComponent::UDAMovementAudioComponent(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
	PrimaryComponentTick.TickGroup = TG_PostPhysics;
	bAutoDestroy = false;
	bStopWhenOwnerDestroyed = true;
	bAllowSpatialization = true;
	bOverrideAttenuation = true;
	bIsUISound = false;
	NumChannels = 1;
	PreferredBufferLength = 512;

	// A person's feet, not a motorcycle: tight near field, quick natural falloff.
	AttenuationOverrides.bAttenuate = true;
	AttenuationOverrides.bSpatialize = true;
	AttenuationOverrides.bAttenuateWithLPF = true;
	AttenuationOverrides.DistanceAlgorithm = EAttenuationDistanceModel::NaturalSound;
	AttenuationOverrides.AttenuationShape = EAttenuationShape::Sphere;
	AttenuationOverrides.AttenuationShapeExtents = FVector(140.0f, 0.0f, 0.0f);
	AttenuationOverrides.FalloffDistance = 1800.0f;
	AttenuationOverrides.dBAttenuationAtMax = -60.0f;
	AttenuationOverrides.LPFRadiusMin = 240.0f;
	AttenuationOverrides.LPFRadiusMax = 1800.0f;
	AttenuationOverrides.LPFFrequencyAtMin = 16000.0f;
	AttenuationOverrides.LPFFrequencyAtMax = 5200.0f;

	AudioState = MakeShared<FDAMovementAudioState, ESPMode::ThreadSafe>();
}

UDAMovementAudioComponent::~UDAMovementAudioComponent() = default;

void UDAMovementAudioComponent::BeginPlay()
{
	Super::BeginPlay();
	if (!AudioState.IsValid())
	{
		AudioState = MakeShared<FDAMovementAudioState, ESPMode::ThreadSafe>();
	}
	Start();
	SetVolumeMultiplier(1.10f);
}

void UDAMovementAudioComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	Stop();
	Super::EndPlay(EndPlayReason);
}

void UDAMovementAudioComponent::SetMovementState(const FDAMovementAudioParams& Params)
{
	if (AudioState.IsValid())
	{
		AudioState->Set(Params);
	}
}

void UDAMovementAudioComponent::PostFootstep(EDAMovementSurface Surface, float Intensity, bool bLeft, float Water01)
{
	if (!AudioState.IsValid())
	{
		return;
	}
	LastSurface = Surface;
	++FootstepCount;
	AudioState->PostEvent(PackEvent(EEventType::Step, Surface, bLeft, Intensity, Water01,
		static_cast<uint8>(FMath::RandRange(0, 255))));
}

void UDAMovementAudioComponent::PostLanding(EDAMovementSurface Surface, float Impact01, float Water01)
{
	if (!AudioState.IsValid())
	{
		return;
	}
	LastSurface = Surface;
	AudioState->PostEvent(PackEvent(EEventType::Land, Surface, false, Impact01, Water01,
		static_cast<uint8>(FMath::RandRange(0, 255))));
}

void UDAMovementAudioComponent::PostSplash(float Intensity, bool bEntering)
{
	if (!AudioState.IsValid())
	{
		return;
	}
	AudioState->PostEvent(PackEvent(bEntering ? EEventType::SplashIn : EEventType::SplashOut,
		EDAMovementSurface::ShallowWater, false, Intensity, 1.f,
		static_cast<uint8>(FMath::RandRange(0, 255))));
}

void UDAMovementAudioComponent::PostJump(float Intensity)
{
	if (!AudioState.IsValid())
	{
		return;
	}
	AudioState->PostEvent(PackEvent(EEventType::Jump, LastSurface, false, Intensity, 0.f,
		static_cast<uint8>(FMath::RandRange(0, 255))));
}

void UDAMovementAudioComponent::PostSwimStroke(bool bLeft, float Intensity, float Water01)
{
	if (!AudioState.IsValid())
	{
		return;
	}
	AudioState->PostEvent(PackEvent(EEventType::Stroke, EDAMovementSurface::DeepWater, bLeft, Intensity,
		FMath::Clamp(Water01, 0.f, 1.f), static_cast<uint8>(FMath::RandRange(0, 255))));
}

float UDAMovementAudioComponent::EstimateCadence(float Speed)
{
	// Same human cadence shape the avatar uses: ~1.0 cycle/s at a 1.5 m/s walk,
	// rising to ~1.36 at a 4.2 m/s run, then a gentle increase above that.
	const float S = FMath::Max(0.f, Speed);
	if (S <= 150.f)
	{
		return 1.0f * FMath::Sqrt(S / 150.f);
	}
	if (S < 420.f)
	{
		return FMath::Lerp(1.0f, 1.36f, (S - 150.f) / 270.f);
	}
	return 1.36f * FMath::Pow(S / 420.f, 0.30f);
}

EDAMovementSurface UDAMovementAudioComponent::ClassifySurfaceMaterial(const FString& MaterialName, float SlopeDegrees,
	float HeightAboveWater, bool bIndoors)
{
	const FString Name = MaterialName.ToLower();
	auto Has = [&Name](const TCHAR* Token) { return Name.Contains(Token); };

	if (Has(TEXT("carpet")) || Has(TEXT("felt")) || Has(TEXT("fabric")) || Has(TEXT("rug")))
	{
		return EDAMovementSurface::Carpet;
	}
	if (Has(TEXT("water")) || Has(TEXT("ocean")) || Has(TEXT("lake")) || Has(TEXT("hotwater")))
	{
		return EDAMovementSurface::ShallowWater;
	}
	if (Has(TEXT("sand")))
	{
		return EDAMovementSurface::Sand;
	}
	if (Has(TEXT("grass")) || Has(TEXT("lawn")) || Has(TEXT("hedge")) || Has(TEXT("foliage"))
		|| Has(TEXT("leaves")) || Has(TEXT("ivy")))
	{
		return EDAMovementSurface::Grass;
	}
	if (Has(TEXT("pier")) || Has(TEXT("board")) || Has(TEXT("plank")) || Has(TEXT("wood"))
		|| Has(TEXT("bamboo")) || Has(TEXT("crate")) || Has(TEXT("bark")))
	{
		return EDAMovementSurface::Wood;
	}
	if (Has(TEXT("metal")) || Has(TEXT("rust")) || Has(TEXT("steel")) || Has(TEXT("iron"))
		|| Has(TEXT("gold")) || Has(TEXT("ship")) || Has(TEXT("hull")) || Has(TEXT("lighthouse"))
		|| Has(TEXT("vending")) || Has(TEXT("helipad")) || Has(TEXT("warehouse")))
	{
		return EDAMovementSurface::Metal;
	}
	if (Has(TEXT("rock")) || Has(TEXT("volcanic")) || Has(TEXT("soil")) || Has(TEXT("dirt")) || Has(TEXT("ash")))
	{
		return EDAMovementSurface::Gravel;
	}
	if (Has(TEXT("asphalt")) || Has(TEXT("concrete")) || Has(TEXT("stone")) || Has(TEXT("marble"))
		|| Has(TEXT("paving")) || Has(TEXT("tile")) || Has(TEXT("academy")) || Has(TEXT("wall"))
		|| Has(TEXT("roof")) || Has(TEXT("gym")) || Has(TEXT("court")) || Has(TEXT("arena"))
		|| Has(TEXT("onsen")) || Has(TEXT("trim")))
	{
		return EDAMovementSurface::Stone;
	}
	if (Has(TEXT("terrain")))
	{
		if (HeightAboveWater < 120.f && SlopeDegrees < 24.f)
		{
			return EDAMovementSurface::Sand;
		}
		if (SlopeDegrees > 34.f)
		{
			return EDAMovementSurface::Gravel;
		}
		if (HeightAboveWater > 9000.f)
		{
			return EDAMovementSurface::Dirt;
		}
		return EDAMovementSurface::Grass;
	}
	if (bIndoors)
	{
		return EDAMovementSurface::Wood;
	}
	if (HeightAboveWater < 120.f && SlopeDegrees < 24.f)
	{
		return EDAMovementSurface::Sand;
	}
	return SlopeDegrees > 34.f ? EDAMovementSurface::Gravel : EDAMovementSurface::Grass;
}

float UDAMovementAudioComponent::WaterBlendFor(float Depth) const
{
	return FMath::Clamp((Depth - 2.f) * (1.f / 28.f), 0.f, 1.f);
}

void UDAMovementAudioComponent::UpdateSurface(FDAMovementAudioParams& Params)
{
	UWorld* World = GetWorld();
	AActor* Owner = GetOwner();
	if (!World || !Owner)
	{
		CachedSurface = Params.bWading ? EDAMovementSurface::ShallowWater
			: (Params.bIndoors ? EDAMovementSurface::Wood : EDAMovementSurface::Grass);
		return;
	}

	const ACharacter* Character = Cast<ACharacter>(Owner);
	const float Half = Character && Character->GetCapsuleComponent()
		? Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() : 90.f;
	const FVector Start = Owner->GetActorLocation();
	const FVector End = Start - FVector(0.f, 0.f, Half + 90.f);

	FHitResult Hit;
	FCollisionQueryParams Query(SCENE_QUERY_STAT(DAMovementSurface), false, Owner);
	if (World->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Query) && Hit.bBlockingHit)
	{
		int32 Section = 0;
		UPrimitiveComponent* HitComponent = Hit.GetComponent();
		UMaterialInterface* Material = HitComponent
			? HitComponent->GetMaterialFromCollisionFaceIndex(Hit.FaceIndex, Section) : nullptr;
		if (!Material && HitComponent)
		{
			Material = HitComponent->GetMaterial(0);
		}
		const FString MaterialName = Material ? Material->GetName() : FString();
		const float Slope = FMath::RadiansToDegrees(
			FMath::Acos(FMath::Clamp(static_cast<float>(Hit.ImpactNormal.Z), -1.f, 1.f)));
		const float HeightAboveWater = bHasWater ? static_cast<float>(Hit.ImpactPoint.Z) - CachedWaterZ : 0.f;
		CachedSurface = ClassifySurfaceMaterial(MaterialName, Slope, HeightAboveWater, Params.bIndoors);
	}
	else
	{
		CachedSurface = Params.bIndoors ? EDAMovementSurface::Wood
			: (Params.bWading ? EDAMovementSurface::ShallowWater : EDAMovementSurface::Grass);
	}

	if (Params.bWading)
	{
		CachedSurface = EDAMovementSurface::ShallowWater;
	}
	Params.Surface = CachedSurface;
	SurfaceTimer = 0.18f;
}

void UDAMovementAudioComponent::UpdateFootsteps(FDAMovementAudioParams& Params, float DeltaSeconds)
{
	if (!Params.bMoving || Params.bRiding)
	{
		bWasMoving = false;
		LastStepIndex = INDEX_NONE;
		StepTimer = 0.f;
		PhaseStaleTime = 0.f;
		return;
	}

	if (!bWasMoving)
	{
		bWasMoving = true;
		LastStepIndex = INDEX_NONE;
		StepTimer = 0.f;
		PhaseStaleTime = 0.f;
		LastPhaseSample = Params.Phase;
	}
	else if (FMath::Abs(Params.Phase - LastPhaseSample) < 0.0001f)
	{
		PhaseStaleTime += DeltaSeconds;
	}
	else
	{
		PhaseStaleTime = 0.f;
		LastPhaseSample = Params.Phase;
	}

	const float Intensity = FMath::Clamp(0.22f + 0.78f * FMath::Sqrt(FMath::Clamp(Params.Speed01, 0.f, 1.f)), 0.f, 1.f);
	const float Water01 = WaterBlendFor(Params.WaterDepth);
	// If a rig ever reports a frozen phase, fall back to the cadence timer
	// instead of walking in silence.
	const bool bUsePhase = Params.Cadence > 0.05f && FMath::IsFinite(Params.Phase) && PhaseStaleTime < 0.45f;

	if (bUsePhase)
	{
		const int32 StepIndex = FMath::FloorToInt(FMath::Frac(FMath::Max(0.f, Params.Phase)) * 2.f);
		if (StepIndex != LastStepIndex)
		{
			// Re-classify on the contact frame so a step from stone onto grass
			// (or into a puddle) changes timbre immediately.
			UpdateSurface(Params);
			PostFootstep(Params.Surface, Intensity, StepIndex == 0, Water01);
			LastStepIndex = StepIndex;
			StepTimer = 0.f;
		}
	}
	else
	{
		// No animation phase (procedural/background fallback): keep a timer at
		// the same cadence so movement is never silent.
		StepTimer -= DeltaSeconds;
		if (StepTimer <= 0.f)
		{
			const float Cadence = FMath::Clamp(Params.Cadence > 0.05f ? Params.Cadence : EstimateCadence(Params.Speed), 0.15f, 2.5f);
			StepTimer = 0.5f / Cadence;
			UpdateSurface(Params);
			PostFootstep(Params.Surface, Intensity, bNextStepLeft, Water01);
			bNextStepLeft = !bNextStepLeft;
		}
	}
}

void UDAMovementAudioComponent::UpdateAirAndWater(const FDAMovementAudioParams& Params)
{
	const bool bWaterImpact = Params.WaterDepth > 22.f;
	if (bWasGrounded && !Params.bGrounded)
	{
		if (Params.VerticalSpeed > 120.f)
		{
			PostJump(FMath::Clamp(Params.VerticalSpeed / 560.f, 0.f, 1.f));
		}
		LastAirVerticalSpeed = Params.VerticalSpeed;
	}
	else if (!Params.bGrounded && Params.VerticalSpeed < LastAirVerticalSpeed)
	{
		LastAirVerticalSpeed = Params.VerticalSpeed;
	}

	if (!bWasGrounded && Params.bGrounded)
	{
		const float Impact = FMath::Max(0.f, -LastAirVerticalSpeed);
		if (Impact > 120.f)
		{
			const float Hard = FMath::Clamp((Impact - 120.f) / 620.f, 0.f, 1.f);
			if (bWaterImpact)
			{
				PostSplash(0.55f + 0.65f * Hard, true);
			}
			else
			{
				PostLanding(Params.Surface, Hard, WaterBlendFor(Params.WaterDepth));
			}
		}
		LastAirVerticalSpeed = 0.f;
	}

	if (!bWasSwimming && Params.bSwimming)
	{
		PostSplash(1.f, true);
		SwimPhase = 0.f;
		LastSwimArm = INDEX_NONE;
	}
	else if (bWasSwimming && !Params.bSwimming)
	{
		PostSplash(0.55f, false);
	}

	if (!bWasWading && Params.bWading && !Params.bSwimming && !bWasSwimming && Params.WaterDepth > 8.f)
	{
		PostSplash(0.35f + 0.25f * WaterBlendFor(Params.WaterDepth), true);
	}

	bWasGrounded = Params.bGrounded;
	bWasSwimming = Params.bSwimming;
	bWasWading = Params.bWading;
}

void UDAMovementAudioComponent::UpdateSwimming(const FDAMovementAudioParams& Params, float DeltaSeconds)
{
	if (!Params.bSwimming)
	{
		SwimPhase = 0.f;
		LastSwimArm = INDEX_NONE;
		TreadTimer = 0.f;
		return;
	}

	const float Cadence = FMath::Clamp(Params.Speed / 200.f, 0.18f, 1.35f);
	if (Params.Speed < 26.f)
	{
		TreadTimer -= DeltaSeconds;
		if (TreadTimer <= 0.f)
		{
			TreadTimer = 0.85f + 0.25f * FMath::FRand();
			LastSwimArm = (LastSwimArm == INDEX_NONE) ? 0 : (LastSwimArm + 1) & 1;
			AudioState->PostEvent(PackEvent(EEventType::Tread, EDAMovementSurface::DeepWater,
				(LastSwimArm & 1) == 0, 0.30f, 1.f,
				static_cast<uint8>(FMath::RandRange(0, 255))));
		}
		return;
	}

	SwimPhase = FMath::Fmod(SwimPhase + Cadence * DeltaSeconds, 1.f);
	const int32 Arm = FMath::FloorToInt(SwimPhase * 2.f);
	if (Arm != LastSwimArm)
	{
		const float Intensity = FMath::Clamp(0.35f + 0.55f * FMath::Sqrt(FMath::Clamp(Params.Speed01, 0.f, 1.f)), 0.f, 1.f);
		PostSwimStroke(Arm == 0, Intensity, 1.f);
		LastSwimArm = Arm;
	}
}

void UDAMovementAudioComponent::GatherAndPost(float DeltaSeconds)
{
	ACharacter* Character = Cast<ACharacter>(GetOwner());
	if (!Character)
	{
		return;
	}
	const UCharacterMovementComponent* Move = Character->GetCharacterMovement();
	const ADAStudentCharacter* Student = Cast<ADAStudentCharacter>(Character);
	const UDAAvatarComponent* Avatar = Character->FindComponentByClass<UDAAvatarComponent>();

	FDAMovementAudioParams Params;
	const FVector Velocity = Character->GetVelocity();
	Params.Speed = FMath::Max(0.f, static_cast<float>(Velocity.Size2D()));
	Params.Speed01 = FMath::Clamp(Params.Speed / 420.f, 0.f, 1.f);
	Params.VerticalSpeed = static_cast<float>(Velocity.Z);
	Params.bGrounded = Move ? Move->IsMovingOnGround() : true;
	Params.bSwimming = Student && Student->IsSwimming();
	Params.bRiding = Student && Student->IsRiding();
	Params.bIndoors = Student && (Student->IsInInterior() || Student->IsIndoors());
	Params.bSprinting = Student && Student->IsSprinting();

	if (Avatar)
	{
		Params.Phase = Avatar->GetLocomotionPhase();
		Params.Cadence = Avatar->GetLocomotionCadence();
	}
	if (Params.Cadence <= 0.05f)
	{
		Params.Cadence = EstimateCadence(Params.Speed);
	}
	Params.Phase = FMath::IsFinite(Params.Phase) ? FMath::Frac(FMath::Max(0.f, Params.Phase)) : 0.f;
	Params.Cadence = FMath::IsFinite(Params.Cadence) ? FMath::Clamp(Params.Cadence, 0.f, 3.f) : 0.f;
	Params.bMoving = Params.bGrounded && !Params.bSwimming && !Params.bRiding && Params.Speed > 20.f;

	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		const FVector Loc = Character->GetActorLocation();
		const float Half = Character->GetCapsuleComponent()
			? Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() : 90.f;
		CachedWaterZ = Sub->GetWaterSurfaceZ(Loc);
		bHasWater = true;
		Params.WaterDepth = CachedWaterZ - static_cast<float>(Loc.Z - Half);
		if (Student && Student->IsInInterior())
		{
			Params.WaterDepth = -10000.f;
		}
	}
	else
	{
		bHasWater = false;
		Params.WaterDepth = 0.f;
	}
	Params.bWading = Params.bGrounded && !Params.bSwimming && Params.WaterDepth > 5.f;
	Params.WaterDepth = FMath::IsFinite(Params.WaterDepth) ? FMath::Clamp(Params.WaterDepth, -10000.f, 2000.f) : 0.f;

	SurfaceTimer -= DeltaSeconds;
	if (SurfaceTimer <= 0.f || CachedSurface == EDAMovementSurface::Count)
	{
		UpdateSurface(Params);
	}
	Params.Surface = Params.bWading ? EDAMovementSurface::ShallowWater : CachedSurface;

	SetMovementState(Params);
	UpdateFootsteps(Params, DeltaSeconds);
	UpdateAirAndWater(Params);
	UpdateSwimming(Params, DeltaSeconds);
}

void UDAMovementAudioComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	if (!AudioState.IsValid() || !FMath::IsFinite(DeltaTime) || DeltaTime <= 0.f)
	{
		return;
	}
	// A hitch must not make the gait/event logic skip several seconds at once.
	GatherAndPost(FMath::Min(DeltaTime, 0.1f));
}

bool UDAMovementAudioComponent::Init(int32& SampleRate)
{
	NumChannels = 1;
	PreferredBufferLength = 512;
	return true;
}

ISoundGeneratorPtr UDAMovementAudioComponent::CreateSoundGenerator(const FSoundGeneratorInitParams& InParams)
{
	if (!AudioState.IsValid())
	{
		AudioState = MakeShared<FDAMovementAudioState, ESPMode::ThreadSafe>();
	}
	return MakeShared<FDAMovementSynth, ESPMode::ThreadSafe>(InParams, AudioState.ToSharedRef());
}

bool UDAMovementAudioComponent::RenderOfflineTest(const FString& WavPath, FString& OutSummary)
{
	constexpr int32 SampleRate = 48000;
	constexpr int32 BlockSize = 512;
	constexpr float Seconds = 9.0f;
	const int32 TotalSamples = static_cast<int32>(SampleRate * Seconds);

	// Also prove the surface classifier handles the material set the island
	// actually uses, rather than only the happy path.
	struct FClassCase
	{
		const TCHAR* Name;
		float Slope;
		float Height;
		bool bIndoors;
		EDAMovementSurface Want;
	};
	const FClassCase Cases[] =
	{
		{ TEXT("MI_M_PierWood"), 0.f, 10.f, false, EDAMovementSurface::Wood },
		{ TEXT("MI_M_Boards"), 0.f, 10.f, false, EDAMovementSurface::Wood },
		{ TEXT("MI_M_HarborConcrete"), 0.f, 10.f, false, EDAMovementSurface::Stone },
		{ TEXT("MI_M_Asphalt"), 0.f, 10.f, false, EDAMovementSurface::Stone },
		{ TEXT("MI_M_Sand"), 0.f, 10.f, false, EDAMovementSurface::Sand },
		{ TEXT("MI_M_PlazaLawn"), 0.f, 10.f, false, EDAMovementSurface::Grass },
		{ TEXT("MI_M_Carpet"), 0.f, 10.f, true, EDAMovementSurface::Carpet },
		{ TEXT("MI_M_Metal"), 0.f, 10.f, false, EDAMovementSurface::Metal },
		{ TEXT("MI_M_Terrain"), 8.f, 300.f, false, EDAMovementSurface::Grass },
		{ TEXT("MI_M_Terrain"), 12.f, 30.f, false, EDAMovementSurface::Sand },
		{ TEXT("MI_M_Terrain"), 42.f, 300.f, false, EDAMovementSurface::Gravel },
		{ TEXT("MI_M_DarkWood"), 0.f, 10.f, true, EDAMovementSurface::Wood },
	};
	int32 ClassFailures = 0;
	for (const FClassCase& Case : Cases)
	{
		const EDAMovementSurface Got = ClassifySurfaceMaterial(Case.Name, Case.Slope, Case.Height, Case.bIndoors);
		if (Got != Case.Want)
		{
			++ClassFailures;
			UE_LOG(LogTemp, Warning, TEXT("DAMovementAudioTest: %s slope %.0f => %d, expected %d"),
				Case.Name, Case.Slope, static_cast<int32>(Got), static_cast<int32>(Case.Want));
		}
	}

	TSharedRef<FDAMovementAudioState, ESPMode::ThreadSafe> State =
		MakeShared<FDAMovementAudioState, ESPMode::ThreadSafe>();

	FSoundGeneratorInitParams Init;
	Init.SampleRate = static_cast<float>(SampleRate);
	Init.NumChannels = 1;
	Init.NumFramesPerCallback = BlockSize;
	Init.AudioComponentId = 0xDAF007;
	Init.InstanceID = 0xF007;
	TSharedRef<FDAMovementSynth, ESPMode::ThreadSafe> Synth =
		MakeShared<FDAMovementSynth, ESPMode::ThreadSafe>(Init, State);

	struct FTestEvent
	{
		float Time;
		EEventType Type;
		EDAMovementSurface Surface;
		bool bLeft;
		float Intensity;
		float Water;
	};
	const FTestEvent Events[] =
	{
		{ 0.12f, EEventType::Step, EDAMovementSurface::Grass, true, 0.55f, 0.f },
		{ 0.62f, EEventType::Step, EDAMovementSurface::Grass, false, 0.55f, 0.f },
		{ 1.12f, EEventType::Step, EDAMovementSurface::Grass, true, 0.55f, 0.f },
		{ 1.62f, EEventType::Step, EDAMovementSurface::Grass, false, 0.55f, 0.f },
		{ 2.10f, EEventType::Step, EDAMovementSurface::Stone, true, 1.0f, 0.f },
		{ 2.47f, EEventType::Step, EDAMovementSurface::Stone, false, 1.0f, 0.f },
		{ 2.84f, EEventType::Step, EDAMovementSurface::Stone, true, 1.0f, 0.f },
		{ 3.21f, EEventType::Step, EDAMovementSurface::Stone, false, 1.0f, 0.f },
		{ 3.58f, EEventType::Step, EDAMovementSurface::Stone, true, 1.0f, 0.f },
		{ 3.92f, EEventType::Step, EDAMovementSurface::Wood, true, 0.55f, 0.f },
		{ 4.42f, EEventType::Step, EDAMovementSurface::Wood, false, 0.55f, 0.f },
		{ 4.90f, EEventType::Step, EDAMovementSurface::ShallowWater, true, 0.45f, 0.9f },
		{ 5.40f, EEventType::Step, EDAMovementSurface::ShallowWater, false, 0.45f, 0.9f },
		{ 5.80f, EEventType::SplashIn, EDAMovementSurface::ShallowWater, false, 1.0f, 1.f },
		{ 6.05f, EEventType::Stroke, EDAMovementSurface::DeepWater, true, 0.8f, 1.f },
		{ 6.75f, EEventType::Stroke, EDAMovementSurface::DeepWater, false, 0.8f, 1.f },
		{ 7.25f, EEventType::Stroke, EDAMovementSurface::DeepWater, true, 0.8f, 1.f },
		{ 7.55f, EEventType::Tread, EDAMovementSurface::DeepWater, false, 0.3f, 1.f },
		{ 7.90f, EEventType::Land, EDAMovementSurface::Stone, false, 0.85f, 0.f },
		{ 8.20f, EEventType::Step, EDAMovementSurface::Stone, true, 0.45f, 0.f },
	};

	TArray<float> Samples;
	Samples.Reserve(TotalSamples);
	TArray<float> Block;
	Block.SetNumZeroed(BlockSize);
	double SumSq[5] = { 0.0, 0.0, 0.0, 0.0, 0.0 };
	int32 Count[5] = { 0, 0, 0, 0, 0 };
	float Peak = 0.f;
	int32 NonFinite = 0;
	int32 Clipped = 0;
	int32 NextEvent = 0;

	for (int32 Start = 0; Start < TotalSamples; Start += BlockSize)
	{
		const float T = static_cast<float>(Start) / SampleRate;
		FDAMovementAudioParams P;
		P.bGrounded = true;
		P.bMoving = true;

		if (T < 2.0f)
		{
			P.Speed = 150.f;
			P.Surface = EDAMovementSurface::Grass;
		}
		else if (T < 3.8f)
		{
			P.Speed = 420.f;
			P.Surface = EDAMovementSurface::Stone;
		}
		else if (T < 4.8f)
		{
			P.Speed = 150.f;
			P.Surface = EDAMovementSurface::Wood;
		}
		else if (T < 5.8f)
		{
			P.Speed = 80.f;
			P.Surface = EDAMovementSurface::ShallowWater;
			P.bWading = true;
			P.WaterDepth = 24.f;
		}
		else if (T < 7.4f)
		{
			P.Speed = 150.f;
			P.Surface = EDAMovementSurface::DeepWater;
			P.bSwimming = true;
			P.bGrounded = false;
			P.WaterDepth = 90.f;
		}
		else if (T < 7.9f)
		{
			P.Speed = 12.f;
			P.Surface = EDAMovementSurface::DeepWater;
			P.bSwimming = true;
			P.bGrounded = false;
			P.WaterDepth = 90.f;
		}
		else if (T < 8.1f)
		{
			P.Speed = 0.f;
			P.bGrounded = false;
			P.WaterDepth = 0.f;
			P.Surface = EDAMovementSurface::Stone;
		}
		else
		{
			P.Speed = 25.f;
			P.Surface = EDAMovementSurface::Stone;
		}
		P.Speed01 = FMath::Clamp(P.Speed / 420.f, 0.f, 1.f);
		P.Phase = FMath::Fmod(T * (T < 3.8f ? 1.0f : 1.35f), 1.f);
		P.Cadence = EstimateCadence(P.Speed);
		State->Set(P);

		while (NextEvent < static_cast<int32>(UE_ARRAY_COUNT(Events))
			&& Events[NextEvent].Time < T + static_cast<float>(BlockSize) / SampleRate)
		{
			const FTestEvent& E = Events[NextEvent++];
			State->PostEvent(PackEvent(E.Type, E.Surface, E.bLeft, E.Intensity, E.Water, 0));
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
			const int32 Segment = Time < 2.0f ? 0 : (Time < 3.8f ? 1 : (Time < 4.8f ? 2 : (Time < 7.4f ? 3 : 4)));
			SumSq[Segment] += static_cast<double>(Sample) * Sample;
			++Count[Segment];
		}
		Samples.Append(Block);
	}

	auto Rms = [&](int32 Segment)
	{
		return Count[Segment] > 0 ? static_cast<float>(FMath::Sqrt(SumSq[Segment] / Count[Segment])) : 0.f;
	};
	const float RmsWalk = Rms(0);
	const float RmsRun = Rms(1);
	const float RmsWood = Rms(2);
	const float RmsWater = Rms(3);
	const float RmsLand = Rms(4);

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
	const uint32 DataSize = static_cast<uint32>(DataBytes);
	Put32(0x46464952);                 // "RIFF"
	Put32(36 + DataSize);
	Put32(0x45564157);                 // "WAVE"
	Put32(0x20746d66);                 // "fmt "
	Put32(16);
	Put16(1);                          // PCM
	Put16(1);                          // mono
	Put32(SampleRate);
	Put32(SampleRate * 2);             // byte rate
	Put16(2);                          // block align
	Put16(16);                         // bits
	Put32(0x61746164);                 // "data"
	Put32(DataSize);
	for (const float Sample : Samples)
	{
		const int16 Pcm = static_cast<int16>(FMath::Clamp(Sample, -1.f, 1.f) * 32767.f);
		Put16(static_cast<uint16>(Pcm));
	}
	if (!FFileHelper::SaveArrayToFile(Wav, *WavPath))
	{
		return false;
	}

	const bool bDynamics = RmsWalk > 0.003f && RmsRun > 0.006f && RmsWood > 0.003f
		&& RmsWater > 0.007f && RmsLand > 0.003f;
	const bool bPassed = NonFinite == 0 && Clipped == 0 && Peak > 0.15f && Peak < 0.995f
		&& bDynamics && ClassFailures == 0;
	OutSummary = FString::Printf(
		TEXT("peak %.3f rms walk %.4f run %.4f wood %.4f water %.4f land %.4f clipped %d nonfinite %d classfail %d"),
		Peak, RmsWalk, RmsRun, RmsWood, RmsWater, RmsLand, Clipped, NonFinite, ClassFailures);
	return bPassed;
}
