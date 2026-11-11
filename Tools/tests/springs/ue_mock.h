// Minimal stand-ins for the UE types the spring solver and the rider IK use (UE semantics: Z up, cm, Q1*Q2 applies Q2 first,
// FTransform A*B applies A then B).
#pragma once
#include <cmath>
#include <vector>
#include <string>
#include <map>
#include <algorithm>
#include <functional>
#include <cstdint>
#define TEXT(x) x
#define INDEX_NONE (-1)
#define KINDA_SMALL_NUMBER (1.e-4f)
#define UE_ARRAY_COUNT(a) (int32)(sizeof(a) / sizeof((a)[0]))
typedef int32_t int32; typedef uint16_t uint16; typedef char TCHAR; typedef uint16 FBoneIndexType;
struct FMath {
  template <class T> static T Clamp(T v, T a, T b) { return v < a ? a : (v > b ? b : v); }
  template <class T> static T Max(T a, T b) { return a > b ? a : b; }
  template <class T> static T Min(T a, T b) { return a < b ? a : b; }
  template <class T> static T Square(T a) { return a * a; }
  template <class T, class U> static T Lerp(const T& a, const T& b, U t) { return a + (b - a) * t; }
  static float RadiansToDegrees(float r) { return r * 57.29577951f; }
  static float DegreesToRadians(float d) { return d / 57.29577951f; }
  static float Acos(float x) { return std::acos(x); }
  static double Atan2(double y, double x) { return std::atan2(y, x); }
  static double Asin(double x) { return std::asin(x); }
  static float Sin(float x) { return std::sin(x); }
  static float Cos(float x) { return std::cos(x); }
  static float Abs(float x) { return std::fabs(x); }
  static double Sqrt(double x) { return std::sqrt(x); }
  static float SmoothStep(float a, float b, float x) { float t = Clamp((x - a) / (b - a), 0.f, 1.f); return t * t * (3 - 2 * t); }
};
struct FVector {
  double X = 0, Y = 0, Z = 0;
  FVector() {}
  FVector(double x, double y, double z) : X(x), Y(y), Z(z) {}
  static const FVector ZeroVector;
  FVector operator+(const FVector& o) const { return {X + o.X, Y + o.Y, Z + o.Z}; }
  FVector operator-(const FVector& o) const { return {X - o.X, Y - o.Y, Z - o.Z}; }
  FVector operator-() const { return {-X, -Y, -Z}; }
  FVector operator*(double s) const { return {X * s, Y * s, Z * s}; }
  FVector operator/(double s) const { return {X / s, Y / s, Z / s}; }
  FVector& operator+=(const FVector& o) { X += o.X; Y += o.Y; Z += o.Z; return *this; }
  double Size() const { return std::sqrt(X * X + Y * Y + Z * Z); }
  double SizeSquared() const { return X * X + Y * Y + Z * Z; }
  FVector GetSafeNormal() const { double s = Size(); return s < 1e-8 ? FVector() : *this / s; }
  bool IsNearlyZero() const { return SizeSquared() < 1e-8; }
  bool IsZero() const { return X == 0 && Y == 0 && Z == 0; }
  void Normalize() { *this = GetSafeNormal(); }
  static double DotProduct(const FVector& a, const FVector& b) { return a.X * b.X + a.Y * b.Y + a.Z * b.Z; }
  static FVector CrossProduct(const FVector& a, const FVector& b) { return {a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X}; }
  static double Dist(const FVector& a, const FVector& b) { return (a - b).Size(); }
  static double DistSquared(const FVector& a, const FVector& b) { return (a - b).SizeSquared(); }
};
inline const FVector FVector::ZeroVector = FVector();
inline FVector operator*(double s, const FVector& v) { return v * s; }
struct FQuat {
  double X = 0, Y = 0, Z = 0, W = 1;
  FQuat() {}
  FQuat(double x, double y, double z, double w) : X(x), Y(y), Z(z), W(w) {}
  FQuat(const FVector& axis, double ang) { double s = std::sin(ang / 2); X = axis.X * s; Y = axis.Y * s; Z = axis.Z * s; W = std::cos(ang / 2); }
  static const FQuat Identity;
  FQuat operator*(const FQuat& q) const {
    return {W * q.X + X * q.W + Y * q.Z - Z * q.Y, W * q.Y - X * q.Z + Y * q.W + Z * q.X,
            W * q.Z + X * q.Y - Y * q.X + Z * q.W, W * q.W - X * q.X - Y * q.Y - Z * q.Z};
  }
  FVector RotateVector(const FVector& v) const {
    FVector q(X, Y, Z); FVector t = FVector::CrossProduct(q, v) * 2.0; return v + t * W + FVector::CrossProduct(q, t);
  }
  FQuat Inverse() const { return {-X, -Y, -Z, W}; }
  FQuat GetNormalized() const { double n = std::sqrt(X * X + Y * Y + Z * Z + W * W); return {X / n, Y / n, Z / n, W / n}; }
  double GetAngle() const { return 2.0 * std::acos(std::min(1.0, std::fabs(W))); }
  static FQuat FindBetweenNormals(const FVector& a, const FVector& b) {
    double w = 1.0 + FVector::DotProduct(a, b); FVector c;
    if (w < 1e-8) { w = 0; c = std::fabs(a.X) > std::fabs(a.Z) ? FVector(-a.Y, a.X, 0) : FVector(0, -a.Z, a.Y); }
    else c = FVector::CrossProduct(a, b);
    return FQuat(c.X, c.Y, c.Z, w).GetNormalized();
  }
  static FQuat Slerp(const FQuat& a, const FQuat& b0, double t) {
    FQuat b = b0; double d = a.X * b.X + a.Y * b.Y + a.Z * b.Z + a.W * b.W;
    if (d < 0) { b = {-b.X, -b.Y, -b.Z, -b.W}; d = -d; }
    if (d > 0.9995) return FQuat(a.X + (b.X - a.X) * t, a.Y + (b.Y - a.Y) * t, a.Z + (b.Z - a.Z) * t, a.W + (b.W - a.W) * t).GetNormalized();
    double th = std::acos(d), s = std::sin(th), wa = std::sin((1 - t) * th) / s, wb = std::sin(t * th) / s;
    return {a.X * wa + b.X * wb, a.Y * wa + b.Y * wb, a.Z * wa + b.Z * wb, a.W * wa + b.W * wb};
  }
};
inline const FQuat FQuat::Identity = FQuat();
struct FTransform {
  FQuat R; FVector T; FVector S{1, 1, 1};
  FTransform() {}
  FTransform(const FQuat& r, const FVector& t) : R(r), T(t) {}
  static const FTransform Identity;
  FVector GetLocation() const { return T; }
  void SetLocation(const FVector& t) { T = t; }
  FQuat GetRotation() const { return R; }
  void SetRotation(const FQuat& r) { R = r; }
  FVector GetScale3D() const { return S; }
  FVector TransformPosition(const FVector& p) const { return R.RotateVector(FVector(p.X * S.X, p.Y * S.Y, p.Z * S.Z)) + T; }
  FVector InverseTransformPosition(const FVector& p) const { FVector q = R.Inverse().RotateVector(p - T); return {q.X / S.X, q.Y / S.Y, q.Z / S.Z}; }
  FVector InverseTransformVectorNoScale(const FVector& v) const { return R.Inverse().RotateVector(v); }
  FTransform operator*(const FTransform& B) const {   // this (child local) then B (parent)
    FTransform o; o.R = B.R * R; o.S = FVector(S.X * B.S.X, S.Y * B.S.Y, S.Z * B.S.Z); o.T = B.TransformPosition(T); return o;
  }
};
inline const FTransform FTransform::Identity = FTransform();
struct FString {
  std::string s;
  FString() {}
  FString(const char* c) : s(c) {}
  FString(const std::string& c) : s(c) {}
  bool StartsWith(const char* p) const { return s.rfind(p, 0) == 0; }
  bool Contains(const char* p) const { return s.find(p) != std::string::npos; }
  bool FindLastChar(char c, int32& i) const { auto p = s.rfind(c); if (p == std::string::npos) return false; i = (int32)p; return true; }
  void LeftInline(int32 n) { s = s.substr(0, n); }
  void LeftChopInline(int32 n) { s = s.substr(0, s.size() - n); }
  int32 Len() const { return (int32)s.size(); }
  char operator[](int32 i) const { return s[i]; }
  bool operator==(const FString& o) const { return s == o.s; }
  bool operator!=(const FString& o) const { return s != o.s; }
};
struct FChar { static bool IsDigit(char c) { return c >= '0' && c <= '9'; } };
struct FName { std::string n; FName() {} FName(const char* c) : n(c) {} FName(const std::string& c) : n(c) {} FString ToString() const { return FString(n); } };
template <int N> struct TInlineAllocator {};
template <class T, class A = void> struct TArray {
  std::vector<T> v;
  int32 Num() const { return (int32)v.size(); }
  void SetNum(int32 n) { v.resize(n); }
  void Reset() { v.clear(); }
  void Add(const T& x) { v.push_back(x); }
  bool IsValidIndex(int32 i) const { return i >= 0 && i < Num(); }
  T& Last() { return v.back(); }
  const T& Last() const { return v.back(); }
  T& operator[](int32 i) { return v[i]; }
  const T& operator[](int32 i) const { return v[i]; }
  template <class P> void Sort(P p) { std::sort(v.begin(), v.end(), p); }
  typename std::vector<T>::iterator begin() { return v.begin(); }
  typename std::vector<T>::iterator end() { return v.end(); }
  typename std::vector<T>::const_iterator begin() const { return v.begin(); }
  typename std::vector<T>::const_iterator end() const { return v.end(); }
};
template <class T> T&& MoveTemp(T& t) { return static_cast<T&&>(t); }
template <class K, class V> struct TPair { K Key; V Value; TPair() {} TPair(K k, V v) : Key(k), Value(v) {} };
struct FCompactPoseBoneIndex { int32 i; explicit FCompactPoseBoneIndex(int32 x) : i(x) {} int32 GetInt() const { return i; } };
struct FCompactPose {
  std::vector<FTransform> L;
  const FTransform& operator[](FCompactPoseBoneIndex b) const { return L[b.i]; }
};
template <class P> struct FCSPose {
  P Pose; std::vector<int32> Parent; std::map<int32, FTransform> Set;
  const P& GetPose() const { return Pose; }
  FTransform GetComponentSpaceTransform(FCompactPoseBoneIndex b) const {
    auto it = Set.find(b.i); if (it != Set.end()) return it->second;
    return Parent[b.i] < 0 ? Pose.L[b.i] : Pose.L[b.i] * GetComponentSpaceTransform(FCompactPoseBoneIndex(Parent[b.i]));
  }
  void SetComponentSpaceTransform(FCompactPoseBoneIndex b, const FTransform& t) { Set[b.i] = t; }
};
struct FReferenceSkeleton {
  std::vector<std::string> Names; std::vector<int32> Parents; TArray<FTransform> Ref;
  int32 GetNum() const { return (int32)Names.size(); }
  int32 GetParentIndex(int32 i) const { return Parents[i]; }
  FName GetBoneName(int32 i) const { return FName(Names[i]); }
  const TArray<FTransform>& GetRefBonePose() const { return Ref; }
  int32 FindBoneIndex(const char* n) const { for (int32 i = 0; i < GetNum(); ++i) if (Names[i] == n) return i; return INDEX_NONE; }
};
