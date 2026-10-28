// Duel Academy Island - global island settings + day/night cycle.

#include "DAIslandManager.h"

#include "Components/BillboardComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/LightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/Light.h"
#include "Engine/SkyLight.h"
#include "EngineUtils.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialParameterCollection.h"

namespace
{
	float SmoothStep01(float E0, float E1, float X)
	{
		const float T = FMath::Clamp((X - E0) / (E1 - E0), 0.f, 1.f);
		return T * T * (3.f - 2.f * T);
	}
}

ADAIslandManager::ADAIslandManager()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	Icon = CreateDefaultSubobject<UBillboardComponent>(TEXT("Icon"));
	RootComponent = Icon;
	Icon->bIsScreenSizeScaled = true;
}

void ADAIslandManager::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	// Preview the chosen hour in the editor viewport.
	ApplyTimeOfDay();
}

void ADAIslandManager::BeginPlay()
{
	Super::BeginPlay();
	GatherNightLights();
	ApplyTimeOfDay();
}

void ADAIslandManager::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bTimePaused && DayLengthMinutes > 0.f)
	{
		Hour += DeltaSeconds * TimeSpeed * 24.f / (DayLengthMinutes * 60.f);
		while (Hour >= 24.f)
		{
			Hour -= 24.f;
			++Day;
		}
	}
	ApplyTimeOfDay();
}

void ADAIslandManager::SetHour(float NewHour)
{
	Hour = FMath::Fmod(FMath::Max(NewHour, 0.f), 24.f);
	ApplyTimeOfDay();
}

void ADAIslandManager::AdjustTimeSpeed(float Factor)
{
	TimeSpeed = FMath::Clamp(TimeSpeed * Factor, 1.f, 240.f);
}

void ADAIslandManager::ApplyTimeOfDay()
{
	// Sun path: rises in the east (+X), peaks over the south (+Y in UE, the island's north is -Y), sets west.
	const float Phase = (Hour - 6.f) / 24.f * 2.f * PI;
	const float Elevation = MaxSunElevation * FMath::Sin(Phase);
	const float SunYaw = 180.f + (Hour - 6.f) / 12.f * 180.f;

	if (Sun)
	{
		Sun->SetActorRotation(FRotator(-Elevation, SunYaw, 0.f));
		if (ULightComponent* LC = Sun->GetLightComponent())
		{
			LC->SetIntensity(SunIlluminance * SmoothStep01(-4.f, 6.f, Elevation));
		}
	}

	const float MoonElevation = FMath::Clamp(-Elevation * 0.8f + 8.f, -60.f, 70.f);
	if (Moon)
	{
		Moon->SetActorRotation(FRotator(-MoonElevation, SunYaw + 160.f, 0.f));
		if (ULightComponent* LC = Moon->GetLightComponent())
		{
			LC->SetIntensity(MoonIlluminance * SmoothStep01(-2.f, 10.f, MoonElevation) * (1.f - SmoothStep01(-6.f, 4.f, Elevation)));
		}
	}

	NightFactor = 1.f - SmoothStep01(-6.f, 5.f, Elevation);

	if (SkyLight)
	{
		if (USkyLightComponent* SC = SkyLight->GetLightComponent())
		{
			SC->SetIntensity(FMath::Lerp(SkyLightDay, SkyLightNight, NightFactor));
		}
	}

	if (HeightFog)
	{
		if (UExponentialHeightFogComponent* FC = HeightFog->GetComponent())
		{
			const FLinearColor DayFog(0.55f, 0.68f, 0.85f);
			const FLinearColor NightFog(0.02f, 0.03f, 0.07f);
			FC->SetFogInscatteringColor(FMath::Lerp(DayFog, NightFog, NightFactor));
		}
	}

	if (ParameterCollection && GetWorld())
	{
		UKismetMaterialLibrary::SetScalarParameterValue(this, ParameterCollection, TEXT("NightFactor"), NightFactor);
		UKismetMaterialLibrary::SetScalarParameterValue(this, ParameterCollection, TEXT("TimeOfDay"), Hour);
	}

	if (HasActorBegunPlay())
	{
		const bool bWantLights = NightFactor > 0.45f;
		if (!bNightLightsInitialised || bWantLights != bNightLightsOn)
		{
			SetNightLights(bWantLights);
		}
	}
}

void ADAIslandManager::GatherNightLights()
{
	NightLights.Reset();
	for (TActorIterator<AActor> It(GetWorld()); It; ++It)
	{
		AActor* A = *It;
		if (!A || !A->ActorHasTag(TEXT("DA_NightOnly")))
		{
			continue;
		}
		TArray<ULightComponent*> Lights;
		A->GetComponents<ULightComponent>(Lights);
		for (ULightComponent* L : Lights)
		{
			NightLights.Add({ L });
		}
	}
}

void ADAIslandManager::SetNightLights(bool bOn)
{
	bNightLightsOn = bOn;
	bNightLightsInitialised = true;
	for (const FNightLight& NL : NightLights)
	{
		if (ULightComponent* L = NL.Light.Get())
		{
			L->SetVisibility(bOn);
		}
	}
}

bool ADAIslandManager::IsInLake(const FVector& P, float Margin) const
{
	const double DX = P.X - LakeCenter.X;
	const double DY = P.Y - LakeCenter.Y;
	const double Rad = FMath::DegreesToRadians(static_cast<double>(LakeYaw));
	const double C = FMath::Cos(Rad);
	const double S = FMath::Sin(Rad);
	const double LX = DX * C + DY * S;
	const double LY = -DX * S + DY * C;
	const double Q = FMath::Square(LX / FMath::Max(LakeRadii.X, 1.0)) + FMath::Square(LY / FMath::Max(LakeRadii.Y, 1.0));
	return Q < static_cast<double>(Margin) * Margin;
}

float ADAIslandManager::GetWaterSurfaceZ(const FVector& WorldLocation) const
{
	return IsInLake(WorldLocation, 1.1f) ? LakeLevel : SeaLevel;
}

FString ADAIslandManager::GetClockText() const
{
	const int32 H = FMath::FloorToInt(Hour);
	const int32 M = FMath::FloorToInt((Hour - H) * 60.f);
	return FString::Printf(TEXT("Day %d  %02d:%02d"), Day, H, M);
}
