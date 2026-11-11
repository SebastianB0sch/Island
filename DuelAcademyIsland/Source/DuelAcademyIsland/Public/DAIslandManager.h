// Duel Academy Island - global island settings + day/night cycle.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DAWaterWaves.h"
#include "DAIslandManager.generated.h"

class ADirectionalLight;
class ASkyLight;
class AExponentialHeightFog;
class UTexture2D;
class UMaterialParameterCollection;
class ULightComponent;
class UBillboardComponent;
class USkeletalMesh;
class UDACalendarSubsystem;

/** Which body of water a location belongs to (ADAIslandManager::QueryWater). */
UENUM(BlueprintType)
enum class EDAWaterBody : uint8
{
	Sea,
	Lake,
	/** Rivers, streams and ponds: shallow wading water, never deep enough to swim. */
	River
};

/**
 * One Gerstner wave of a wave set, as written to SourceAssets/Data/water.json by the pipeline and mirrored in
 * the M_DA_Water material instance. The maths lives in DAWaterWaves.h.
 */
USTRUCT(BlueprintType)
struct FDAGerstnerWave
{
	GENERATED_BODY()

	/** Travel direction (world XY, normalised when used). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	FVector2D Direction = FVector2D(1.0, 0.0);

	/** Crest to crest, cm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water", meta = (ClampMin = "1"))
	float Wavelength = 4000.f;

	/** Rest level to crest, cm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	float Amplitude = 0.f;

	/** Choppiness 0..1 (horizontal orbit radius / amplitude). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water", meta = (ClampMin = "0", ClampMax = "1"))
	float Steepness = 0.f;

	/** Phase speed, cm/s (<= 0: the deep-water speed of the wavelength). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	float Speed = 0.f;

	/** Radians. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	float Phase = 0.f;
};

/** A river / stream / pond chain: its water covers HalfWidth either side of the centre line. */
USTRUCT(BlueprintType)
struct FDARiver
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	FName Id;

	/** Centre line running downstream: X, Y, Z = water surface (cm), W = half width (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	TArray<FVector4> Points;

	/** XY bounds of the water (grown by the half widths); refreshed by ADAIslandManager::RefreshWaterCaches. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Water")
	FVector2D BoundsMin = FVector2D::ZeroVector;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Water")
	FVector2D BoundsMax = FVector2D::ZeroVector;
};

/** Answer of ADAIslandManager::QueryWater. */
struct FDAWaterInfo
{
	EDAWaterBody Body = EDAWaterBody::Sea;
	/** Rest level of that body at the location (cm). */
	float StillZ = 0.f;
	/** Actual surface height at the location's XY right now (rest level + waves). */
	float SurfaceZ = 0.f;
	/** Unit surface normal (straight up on still water). */
	FVector Normal = FVector::UpVector;
	/** True when a wave set moves this body (false: flat water, or no water.json data). */
	bool bWaves = false;
};

/**
 * One per level (spawned by the editor build script). Drives the sun/moon,
 * sky light, fog and night-only lights, and holds island-wide data the HUD
 * and gameplay need (map texture + bounds, lake / sea levels).
 */
UCLASS(Blueprintable)
class DUELACADEMYISLAND_API ADAIslandManager : public AActor
{
	GENERATED_BODY()

public:
	ADAIslandManager();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnConstruction(const FTransform& Transform) override;

	/** Editor repair: merge every bone of Mesh into its skeleton's bone tree (saves the skeleton). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Editor")
	static bool MergeSkeletonBones(USkeletalMesh* Mesh);

	// ---------------------------------------------------------------- scene references
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Sky")
	TObjectPtr<ADirectionalLight> Sun;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Sky")
	TObjectPtr<ADirectionalLight> Moon;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Sky")
	TObjectPtr<ASkyLight> SkyLight;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Sky")
	TObjectPtr<AExponentialHeightFog> HeightFog;

	/** Scalar parameters "NightFactor" (0 day .. 1 night) and "TimeOfDay" (hours) are written here. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Sky")
	TObjectPtr<UMaterialParameterCollection> ParameterCollection;

	// ---------------------------------------------------------------- time of day
	/** Current time of day in hours (0-24). Editable in the editor to preview lighting. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Time", meta = (ClampMin = "0", ClampMax = "24"))
	float Hour = 16.25f;

	/** Real-time minutes for a full 24 h day. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Time", meta = (ClampMin = "1"))
	float DayLengthMinutes = 24.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Time")
	bool bTimePaused = false;

	/** Extra multiplier controlled by the player ([ and ] keys). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Time")
	float TimeSpeed = 1.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Sky")
	float SunIlluminance = 10.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Sky")
	float MoonIlluminance = 0.6f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Sky")
	float MaxSunElevation = 64.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Sky")
	float SkyLightDay = 1.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Sky")
	float SkyLightNight = 2.5f;

	// ---------------------------------------------------------------- map / water
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Map")
	TObjectPtr<UTexture2D> MapTexture;

	/** World XY (cm) covered by MapTexture: Min = top-left (west/north), Max = bottom-right. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Map")
	FVector2D MapMin = FVector2D(-153600.0, -153600.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Map")
	FVector2D MapMax = FVector2D(153600.0, 153600.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	float SeaLevel = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	FVector LakeCenter = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	FVector2D LakeRadii = FVector2D(19000.0, 15000.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	float LakeYaw = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	float LakeLevel = 3000.f;

	// ---------------------------------------------------------------- waves / rivers (SourceAssets/Data/water.json)
	/** Master switch for the gameplay side of the waves (the material keeps animating). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	bool bWavesEnabled = true;

	/** Gerstner set of the open sea (at most 6 are used - the material has 6 slots). Empty = flat sea. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	TArray<FDAGerstnerWave> OceanWaves;

	/** Gerstner set of the lake (wind ripples). Empty = flat lake. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	TArray<FDAGerstnerWave> LakeWaves;

	/** The sea flattens between these distances from the world origin (cm, max(|x|, |y|)): a safety net beyond
	 *  SM_Ocean's fine grid (the wave mask is already zero at its edge). Same numbers as WaveFadeStart /
	 *  WaveFadeEnd of M_DA_Water. End <= 0 = never. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	float WaveFadeStart = 160000.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	float WaveFadeEnd = 178000.f;

	/** Sea amplitude scale 0..255 (R of T_WaveMask), WaveMaskSize^2 bytes, row 0 = WaveMaskMin.Y. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Water")
	TArray<uint8> WaveMask;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Water")
	int32 WaveMaskSize = 0;

	/** World XY (cm) covered by WaveMask. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	FVector2D WaveMaskMin = FVector2D(-153600.0, -153600.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	FVector2D WaveMaskMax = FVector2D(153600.0, 153600.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Water")
	TArray<FDARiver> Rivers;

	/** Forget every wave set, the wave mask and all rivers (the build script calls this before refilling). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Water")
	void ClearWaterData();

	/**
	 * Replace one wave set. Packed = 7 floats per wave: dir x, dir y, wavelength (cm), amplitude (cm),
	 * steepness (0..1), phase speed (cm/s, <= 0 = deep-water speed), phase (rad).
	 */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Water")
	void SetWaveSet(bool bLake, const TArray<float>& Packed);

	/** Sea amplitude mask: Base64 of Size * Size bytes, row 0 = Min.Y, column 0 = Min.X. False if malformed. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Water")
	bool SetWaveMaskBase64(const FString& Data, int32 Size, FVector2D Min, FVector2D Max);

	/** Add a river. PackedPoints = 4 floats per point, downstream: x, y, surface z, half width (cm). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Water")
	void AddRiver(FName Id, const TArray<float>& PackedPoints);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Water")
	int32 GetRiverCount() const { return Rivers.Num(); }

	/** True when a wave set (sea or lake) is loaded and the waves are enabled. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Water")
	bool HasWaveData() const;

	/** Height of the water (cm) above its rest level at a world location right now. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Water")
	float GetWaveOffset(const FVector& WorldLocation) const;

	/** Unit normal of the water surface at a world location right now. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Water")
	FVector GetWaterNormal(const FVector& WorldLocation) const;

	/** True inside the water of a river / stream / pond (and not well above it, e.g. on a bridge). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Water")
	bool IsInRiver(const FVector& WorldLocation) const;

	// ---------------------------------------------------------------- API
	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	float GetNightFactor() const { return NightFactor; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	bool IsNight() const { return bNightLightsOn; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetHour(float NewHour);

	/** Set the visual day and hour from the authoritative calendar (AbsoluteDay is 0-based). */
	void SetCalendarTime(int32 AbsoluteDay, float NewHour);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void AdjustTimeSpeed(float Factor);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void ToggleTimePaused() { bTimePaused = !bTimePaused; }

	/** Water surface height at the location's XY right now: river, lake or sea, waves included. */
	float GetWaterSurfaceZ(const FVector& WorldLocation) const;
	bool IsInLake(const FVector& WorldLocation, float Margin = 1.f) const;

	/** Everything about the water at a location: which body, rest level, current surface and normal. */
	FDAWaterInfo QueryWater(const FVector& WorldLocation, bool bWithWaves = true) const;

	/** Recompute the river bounds and the wave tables after the water properties changed. */
	void RefreshWaterCaches();

	/** "Day 7  16:15" style clock text: campaign day number plus visual hour. */
	FString GetClockText() const;

private:
	void ApplyTimeOfDay();
	void GatherNightLights();
	void SetNightLights(bool bOn);
	void SanitizeTimeSettings();
	const FDARiver* FindRiverAt(const FVector& WorldLocation, DAWater::FRiverHit& OutHit) const;
	DAWater::FWaveField MakeWaveField(bool bLake) const;

	UFUNCTION()
	void HandleCalendarVisualHour(int32 NewHour);

	UPROPERTY(VisibleAnywhere, Category = "Duel Academy")
	TObjectPtr<UBillboardComponent> Icon;

	struct FNightLight
	{
		TWeakObjectPtr<ULightComponent> Light;
	};
	TArray<FNightLight> NightLights;

	float NightFactor = 0.f;
	bool bNightLightsOn = false;
	bool bNightLightsInitialised = false;
	int32 Day = 1;

	TWeakObjectPtr<UDACalendarSubsystem> BoundCalendar;

	/** OceanWaves / LakeWaves converted for DAWaterWaves.h (RefreshWaterCaches). */
	TArray<FDAWave> OceanWaveCache;
	TArray<FDAWave> LakeWaveCache;
	bool bWaterCachesValid = false;
};
