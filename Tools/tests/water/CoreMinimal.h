// Stand-in for Unreal's CoreMinimal.h: just the types and FMath functions DAWaterWaves.h uses, with UE semantics
// (cm, doubles). Tools/tests/test_water_engine.py compiles the real header against this file.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

typedef int32_t int32;
typedef uint8_t uint8;

struct FMath
{
	template <class T> static T Clamp(T V, T A, T B) { return V < A ? A : (V > B ? B : V); }
	template <class T> static T Max(T A, T B) { return A > B ? A : B; }
	template <class T> static T Min(T A, T B) { return A < B ? A : B; }
	template <class T> static T Square(T A) { return A * A; }
	template <class T> static T Abs(T A) { return A < 0 ? -A : A; }
	static double Sin(double X) { return std::sin(X); }
	static double Cos(double X) { return std::cos(X); }
	static double Sqrt(double X) { return std::sqrt(X); }
};

struct FVector4
{
	double X = 0, Y = 0, Z = 0, W = 0;
	FVector4() {}
	FVector4(double InX, double InY, double InZ, double InW) : X(InX), Y(InY), Z(InZ), W(InW) {}
};
