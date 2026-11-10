// Duel Academy Island - water surface math shared by gameplay (buoyancy, swimming, wading) and, formula for
// formula, by the water material (M_DA_Water in Content/Python/duel_academy/materials.py).
//
// Engine independent on purpose: only CoreMinimal types and FMath, no UObject / reflection, so
// Tools/tests/test_water_engine.py can compile this exact file against the stand-in CoreMinimal.h in
// Tools/tests/water and compare it with an independent Python implementation.
//
// Wave model (a set of up to DAWater::MaxWaves Gerstner waves):
//     k = 2*pi / L,  omega = k * c,  theta = k * dot(D, p.xy) - omega * t + phi
//     offset.xy = sum(D * (s * A * m) * cos(theta))
//     offset.z  = sum(A * m * sin(theta))
//     normal    = normalize(-sum(D.x k A m cos), -sum(D.y k A m cos), 1 - sum(k s A m sin))
//     fold      = sum(k s A m sin(theta))                  (whitecaps where this is large)
// p = undisplaced world position (cm), t = game time (s), m = amplitude scale at p: the wave mask (R channel
// of T_WaveMask, bilinear + clamp) times a fade that flattens the sea towards the coarse far rings of SM_Ocean.

#pragma once

#include "CoreMinimal.h"

/** One Gerstner wave. Lengths in cm, Speed = phase speed in cm/s, Phase in radians. */
struct FDAWave
{
	double DirX = 1.0;
	double DirY = 0.0;
	double Wavelength = 4000.0;
	double Amplitude = 0.0;
	/** Choppiness 0..1: the horizontal orbit radius as a fraction of the amplitude. */
	double Steepness = 0.0;
	double Speed = 0.0;
	double Phase = 0.0;
};

/** Sum of a wave set at one undisplaced position. Normal is not normalised (Z > 0 for sane wave sets). */
struct FDAWaveSample
{
	double OffsetX = 0.0;
	double OffsetY = 0.0;
	double OffsetZ = 0.0;
	double NormalX = 0.0;
	double NormalY = 0.0;
	double NormalZ = 1.0;
	double Fold = 0.0;
};

namespace DAWater
{
	inline constexpr int32 MaxWaves = 6;
	inline constexpr double TwoPi = 6.283185307179586476925;
	/** cm/s^2 */
	inline constexpr double Gravity = 981.0;
	/** Fixed-point iterations that invert the horizontal displacement (see HeightAt). */
	inline constexpr int32 InverseIterations = 3;
	/** Default flattening of the sea (Chebyshev distance from the world origin, cm). SM_Ocean's fine 5 m grid
	 *  ends at +-1.54 km and the wave mask is already zero there, so this is only the safety net that keeps
	 *  the coarse rings beyond flat without a mask. Mirrored by WaveFadeStart / WaveFadeEnd in M_DA_Water. */
	inline constexpr double DefaultFadeStart = 160000.0;
	inline constexpr double DefaultFadeEnd = 178000.0;
	/** A point this far (cm) above a river's surface is no longer "in" the river (bridge decks). */
	inline constexpr double RiverHeadroom = 300.0;

	/** Deep-water phase speed (cm/s) for a wavelength in cm - the default when a wave has no Speed. */
	inline double DeepWaterSpeed(double WavelengthCm)
	{
		return FMath::Sqrt(Gravity * FMath::Max(WavelengthCm, 1.0) / TwoPi);
	}

	/** Sum of the wave set at the undisplaced position (X, Y), every amplitude multiplied by Scale. */
	inline FDAWaveSample Evaluate(const FDAWave* Waves, int32 Num, double X, double Y, double Time, double Scale)
	{
		FDAWaveSample Out;
		if (!Waves || Num <= 0 || Scale <= 0.0)
		{
			return Out;
		}
		double SlopeX = 0.0;
		double SlopeY = 0.0;
		const int32 Count = FMath::Min(Num, MaxWaves);
		for (int32 i = 0; i < Count; ++i)
		{
			const FDAWave& W = Waves[i];
			if (W.Amplitude == 0.0 || W.Wavelength <= 1.0)
			{
				continue;
			}
			const double K = TwoPi / W.Wavelength;
			const double Theta = K * (W.DirX * X + W.DirY * Y) - K * W.Speed * Time + W.Phase;
			const double S = FMath::Sin(Theta);
			const double C = FMath::Cos(Theta);
			const double A = W.Amplitude * Scale;
			const double B = W.Steepness * A;
			Out.OffsetX += W.DirX * B * C;
			Out.OffsetY += W.DirY * B * C;
			Out.OffsetZ += A * S;
			SlopeX += W.DirX * K * A * C;
			SlopeY += W.DirY * K * A * C;
			Out.Fold += K * B * S;
		}
		Out.NormalX = -SlopeX;
		Out.NormalY = -SlopeY;
		Out.NormalZ = 1.0 - Out.Fold;
		return Out;
	}

	/** Largest possible fold of a wave set (sum of k*s*A): the material normalises its whitecaps by it. */
	inline double MaxFold(const FDAWave* Waves, int32 Num)
	{
		double Sum = 0.0;
		const int32 Count = Waves ? FMath::Min(Num, MaxWaves) : 0;
		for (int32 i = 0; i < Count; ++i)
		{
			if (Waves[i].Wavelength > 1.0)
			{
				Sum += TwoPi / Waves[i].Wavelength * FMath::Abs(Waves[i].Steepness * Waves[i].Amplitude);
			}
		}
		return Sum;
	}

	/** Hermite 0..1 ramp between E0 and E1 (E1 > E0). */
	inline double SmoothStep(double E0, double E1, double X)
	{
		const double T = FMath::Clamp((X - E0) / FMath::Max(E1 - E0, 1.0e-9), 0.0, 1.0);
		return T * T * (3.0 - 2.0 * T);
	}

	/**
	 * Bilinear, clamped lookup of a Size x Size uint8 map covering [Min, Max] (row 0 = MinY, column 0 = MinX,
	 * texel centres at (i + 0.5) / Size) - the same footprint a clamped, bilinear GPU sampler has. Returns 0..1;
	 * 1 when there is no map.
	 */
	inline double SampleMask(const uint8* Data, int32 Size, double MinX, double MinY, double MaxX, double MaxY, double X, double Y)
	{
		if (!Data || Size <= 0 || MaxX <= MinX || MaxY <= MinY)
		{
			return 1.0;
		}
		const double FX = FMath::Clamp((X - MinX) / (MaxX - MinX) * Size - 0.5, 0.0, static_cast<double>(Size - 1));
		const double FY = FMath::Clamp((Y - MinY) / (MaxY - MinY) * Size - 0.5, 0.0, static_cast<double>(Size - 1));
		const int32 X0 = FMath::Min(static_cast<int32>(FX), Size - 1);
		const int32 Y0 = FMath::Min(static_cast<int32>(FY), Size - 1);
		const int32 X1 = FMath::Min(X0 + 1, Size - 1);
		const int32 Y1 = FMath::Min(Y0 + 1, Size - 1);
		const double TX = FX - X0;
		const double TY = FY - Y0;
		const double V00 = Data[Y0 * Size + X0];
		const double V10 = Data[Y0 * Size + X1];
		const double V01 = Data[Y1 * Size + X0];
		const double V11 = Data[Y1 * Size + X1];
		return ((V00 * (1.0 - TX) + V10 * TX) * (1.0 - TY) + (V01 * (1.0 - TX) + V11 * TX) * TY) / 255.0;
	}

	/** A wave set plus everything that scales it over the map. Plain view: it owns nothing. */
	struct FWaveField
	{
		const FDAWave* Waves = nullptr;
		int32 NumWaves = 0;
		/** Optional Size x Size amplitude map (see SampleMask); null = 1 everywhere. */
		const uint8* Mask = nullptr;
		int32 MaskSize = 0;
		double MaskMinX = 0.0;
		double MaskMinY = 0.0;
		double MaskMaxX = 0.0;
		double MaskMaxY = 0.0;
		/** Amplitudes fade to zero between these Chebyshev distances from the origin; FadeEnd <= 0 = no fade. */
		double FadeStart = 0.0;
		double FadeEnd = 0.0;

		bool HasWaves() const
		{
			return Waves != nullptr && NumWaves > 0;
		}

		/** Amplitude scale m at an undisplaced position. */
		double ScaleAt(double X, double Y) const
		{
			double M = SampleMask(Mask, MaskSize, MaskMinX, MaskMinY, MaskMaxX, MaskMaxY, X, Y);
			if (FadeEnd > 0.0)
			{
				M *= 1.0 - SmoothStep(FadeStart, FadeEnd, FMath::Max(FMath::Abs(X), FMath::Abs(Y)));
			}
			return M;
		}

		/** The wave sum at the undisplaced position (X, Y). */
		FDAWaveSample SampleAt(double X, double Y, double Time) const
		{
			return Evaluate(Waves, NumWaves, X, Y, Time, ScaleAt(X, Y));
		}

		/**
		 * The surface as seen at a fixed world XY. Gerstner waves also move the water sideways, so the point of
		 * the sheet that sits over (X, Y) started somewhere else: q = (X, Y) - offset.xy(q), solved by
		 * InverseIterations fixed-point steps. Returns the wave sum at q.
		 */
		FDAWaveSample SurfaceAt(double X, double Y, double Time) const
		{
			if (!HasWaves())
			{
				return FDAWaveSample();
			}
			double QX = X;
			double QY = Y;
			for (int32 i = 0; i < InverseIterations; ++i)
			{
				const FDAWaveSample S = SampleAt(QX, QY, Time);
				QX = X - S.OffsetX;
				QY = Y - S.OffsetY;
			}
			return SampleAt(QX, QY, Time);
		}

		/** Height of the water above its rest level at a fixed world XY. */
		double HeightAt(double X, double Y, double Time) const
		{
			return SurfaceAt(X, Y, Time).OffsetZ;
		}
	};

	/** Result of a river lookup. */
	struct FRiverHit
	{
		bool bInside = false;
		/** Water surface height at the closest point of the centre line. */
		double SurfaceZ = 0.0;
		/** Distance from the centre line minus the half width there (negative inside the water). */
		double EdgeDistance = 0.0;
		/** Unit direction of flow at the closest point. */
		double FlowX = 0.0;
		double FlowY = 0.0;
	};

	/** XY bounds of a river polyline grown by its half widths: (MinX, MinY, MaxX, MaxY). False when empty. */
	inline bool RiverBounds(const FVector4* Points, int32 Num, double& MinX, double& MinY, double& MaxX, double& MaxY)
	{
		if (!Points || Num <= 0)
		{
			return false;
		}
		MinX = MinY = 1.0e30;
		MaxX = MaxY = -1.0e30;
		for (int32 i = 0; i < Num; ++i)
		{
			const double R = FMath::Max(static_cast<double>(Points[i].W), 0.0);
			MinX = FMath::Min(MinX, static_cast<double>(Points[i].X) - R);
			MinY = FMath::Min(MinY, static_cast<double>(Points[i].Y) - R);
			MaxX = FMath::Max(MaxX, static_cast<double>(Points[i].X) + R);
			MaxY = FMath::Max(MaxY, static_cast<double>(Points[i].Y) + R);
		}
		return true;
	}

	/**
	 * Closest point of a river (points = [x, y, z_surface, half_width], running downstream) to (X, Y).
	 * bInside when the point lies within the half width there. Callers reject far points with RiverBounds first.
	 */
	inline FRiverHit QueryRiver(const FVector4* Points, int32 Num, double X, double Y)
	{
		FRiverHit Best;
		Best.EdgeDistance = 1.0e30;
		if (!Points || Num <= 0)
		{
			return Best;
		}
		if (Num == 1)
		{
			const double D = FMath::Sqrt(FMath::Square(X - Points[0].X) + FMath::Square(Y - Points[0].Y));
			Best.EdgeDistance = D - Points[0].W;
			Best.SurfaceZ = Points[0].Z;
			Best.bInside = Best.EdgeDistance <= 0.0;
			return Best;
		}
		for (int32 i = 0; i + 1 < Num; ++i)
		{
			const FVector4& A = Points[i];
			const FVector4& B = Points[i + 1];
			const double DX = B.X - A.X;
			const double DY = B.Y - A.Y;
			const double Len2 = DX * DX + DY * DY;
			const double T = Len2 > 1.0e-9 ? FMath::Clamp(((X - A.X) * DX + (Y - A.Y) * DY) / Len2, 0.0, 1.0) : 0.0;
			const double PX = A.X + DX * T;
			const double PY = A.Y + DY * T;
			const double Dist = FMath::Sqrt(FMath::Square(X - PX) + FMath::Square(Y - PY));
			const double Edge = Dist - (A.W + (B.W - A.W) * T);
			if (Edge < Best.EdgeDistance)
			{
				Best.EdgeDistance = Edge;
				Best.SurfaceZ = A.Z + (B.Z - A.Z) * T;
				const double Len = FMath::Sqrt(Len2);
				Best.FlowX = Len > 1.0e-6 ? DX / Len : 0.0;
				Best.FlowY = Len > 1.0e-6 ? DY / Len : 0.0;
			}
		}
		Best.bInside = Best.EdgeDistance <= 0.0;
		return Best;
	}
}
