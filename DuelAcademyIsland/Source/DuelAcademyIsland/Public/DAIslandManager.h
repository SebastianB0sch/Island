// Duel Academy Island - global island settings + day/night cycle.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DAIslandManager.generated.h"

class ADirectionalLight;
class ASkyLight;
class AExponentialHeightFog;
class UTexture2D;
class UMaterialParameterCollection;
class ULightComponent;
class UBillboardComponent;
class USkeletalMesh;

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

	// ---------------------------------------------------------------- API
	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	float GetNightFactor() const { return NightFactor; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	bool IsNight() const { return bNightLightsOn; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetHour(float NewHour);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void AdjustTimeSpeed(float Factor);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void ToggleTimePaused() { bTimePaused = !bTimePaused; }

	float GetWaterSurfaceZ(const FVector& WorldLocation) const;
	bool IsInLake(const FVector& WorldLocation, float Margin = 1.f) const;

	/** "Day 1 - 16:15" style clock text. */
	FString GetClockText() const;

private:
	void ApplyTimeOfDay();
	void GatherNightLights();
	void SetNightLights(bool bOn);

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
};
