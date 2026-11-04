// Duel Academy Island - global island settings + day/night cycle.

#include "DAIslandManager.h"

#include "DACalendarSubsystem.h"
#include "Components/BillboardComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/LightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/GameInstance.h"
#include "Engine/Light.h"
#include "Engine/SkyLight.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/Skeleton.h"
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
	SanitizeTimeSettings();
	// Preview the chosen hour in the editor viewport.
	ApplyTimeOfDay();
}

void ADAIslandManager::BeginPlay()
{
	Super::BeginPlay();
	GatherNightLights();
	SanitizeTimeSettings();

	// The calendar owns the campaign date. Follow its visual-hour notifications
	// (load, story date jumps, sleeps) instead of guessing midnight crossings
	// from the clock alone, which left the "Day N" label behind the calendar.
	if (UGameInstance* GameInstance = GetGameInstance())
	{
		if (UDACalendarSubsystem* Calendar = GameInstance->GetSubsystem<UDACalendarSubsystem>())
		{
			BoundCalendar = Calendar;
			Calendar->OnVisualHourChanged.AddDynamic(this, &ADAIslandManager::HandleCalendarVisualHour);
			SetCalendarTime(Calendar->GetAbsoluteDay(), static_cast<float>(Calendar->GetHour()));
		}
		else
		{
			ApplyTimeOfDay();
		}
	}
	else
	{
		ApplyTimeOfDay();
	}
}

void ADAIslandManager::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UDACalendarSubsystem* Calendar = BoundCalendar.Get())
	{
		Calendar->OnVisualHourChanged.RemoveDynamic(this, &ADAIslandManager::HandleCalendarVisualHour);
	}
	BoundCalendar.Reset();
	Super::EndPlay(EndPlayReason);
}

void ADAIslandManager::SanitizeTimeSettings()
{
	if (!FMath::IsFinite(Hour))
	{
		Hour = 16.25f;
	}
	else
	{
		Hour = FMath::Fmod(FMath::Max(Hour, 0.f), 24.f);
	}
	if (!FMath::IsFinite(DayLengthMinutes) || DayLengthMinutes <= 0.f)
	{
		DayLengthMinutes = 24.f;
	}
	else
	{
		// Editor metadata already clamps this to >= 1 minute; recover absurd save
		// or blueprint values that would otherwise roll whole days every frame.
		DayLengthMinutes = FMath::Max(DayLengthMinutes, 0.01f);
	}
	if (!FMath::IsFinite(TimeSpeed) || TimeSpeed <= 0.f)
	{
		TimeSpeed = 1.f;
	}
	else
	{
		TimeSpeed = FMath::Clamp(TimeSpeed, 1.f, 240.f);
	}
	if (!FMath::IsFinite(MaxSunElevation))
	{
		MaxSunElevation = 64.f;
	}
	if (!FMath::IsFinite(SunIlluminance) || SunIlluminance < 0.f)
	{
		SunIlluminance = 10.f;
	}
	if (!FMath::IsFinite(MoonIlluminance) || MoonIlluminance < 0.f)
	{
		MoonIlluminance = 0.6f;
	}
	if (!FMath::IsFinite(SkyLightDay) || SkyLightDay < 0.f)
	{
		SkyLightDay = 1.f;
	}
	if (!FMath::IsFinite(SkyLightNight) || SkyLightNight < 0.f)
	{
		SkyLightNight = 2.5f;
	}
}

void ADAIslandManager::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	if (!bTimePaused && FMath::IsFinite(DeltaSeconds) && FMath::IsFinite(DayLengthMinutes) && DayLengthMinutes > 0.f)
	{
		if (!FMath::IsFinite(TimeSpeed) || TimeSpeed <= 0.f)
		{
			TimeSpeed = 1.f;
		}
		if (!FMath::IsFinite(Hour))
		{
			Hour = 0.f;
		}

		const double DeltaHours = static_cast<double>(DeltaSeconds) * static_cast<double>(TimeSpeed) * 24.0
			/ (static_cast<double>(DayLengthMinutes) * 60.0);
		const double NewHour = static_cast<double>(Hour) + DeltaHours;
		if (FMath::IsFinite(NewHour))
		{
			// Count whole days arithmetically. The old loop subtracted 24h per
			// iteration, so a tiny day length or a long hitch could hang a frame.
			const double WholeDays = FMath::FloorToDouble(NewHour / 24.0);
			// With a calendar bound, Day is the campaign day and only the
			// calendar may move it; the visual clock just wraps its hours.
			if (WholeDays > 0.0 && !BoundCalendar.IsValid())
			{
				const int64 Room = static_cast<int64>(TNumericLimits<int32>::Max()) - static_cast<int64>(Day);
				const int32 Add = WholeDays >= static_cast<double>(Room)
					? static_cast<int32>(FMath::Max<int64>(0, Room))
					: static_cast<int32>(WholeDays);
				Day += Add;
			}
			Hour = static_cast<float>(FMath::Fmod(NewHour, 24.0));
		}
	}
	ApplyTimeOfDay();
}

void ADAIslandManager::SetHour(float NewHour)
{
	if (!FMath::IsFinite(NewHour) || NewHour < 0.f)
	{
		return;
	}

	// Without a calendar, keep the clock's session day label in step with
	// forward jumps. The N key now goes through SetCalendarTime, so this path
	// is only the standalone fallback. A jump of more than half a day is treated
	// as crossing midnight; explicit >= 24 values count whole days.
	const float PreviousHour = Hour;
	const double WholeDays = FMath::FloorToDouble(static_cast<double>(NewHour) / 24.0);
	const float WrappedHour = static_cast<float>(FMath::Fmod(static_cast<double>(NewHour), 24.0));
	if (!BoundCalendar.IsValid())
	{
		if (WholeDays >= 1.0)
		{
			const int64 Room = static_cast<int64>(TNumericLimits<int32>::Max()) - static_cast<int64>(Day);
			const int32 Add = WholeDays >= static_cast<double>(Room)
				? static_cast<int32>(FMath::Max<int64>(0, Room))
				: static_cast<int32>(WholeDays);
			Day += Add;
		}
		else if (WrappedHour < PreviousHour && PreviousHour - WrappedHour >= 12.f)
		{
			++Day;
		}
	}
	Hour = FMath::Clamp(WrappedHour, 0.f, 24.f - KINDA_SMALL_NUMBER);
	ApplyTimeOfDay();
}

void ADAIslandManager::SetCalendarTime(int32 AbsoluteDay, float NewHour)
{
	if (!FMath::IsFinite(NewHour))
	{
		return;
	}
	const int64 DayNumber = static_cast<int64>(AbsoluteDay) + 1;
	Day = static_cast<int32>(FMath::Clamp<int64>(DayNumber, 1, static_cast<int64>(TNumericLimits<int32>::Max())));
	const float WrappedHour = static_cast<float>(FMath::Fmod(static_cast<double>(FMath::Max(NewHour, 0.f)), 24.0));
	Hour = FMath::Clamp(WrappedHour, 0.f, 24.f - KINDA_SMALL_NUMBER);
	ApplyTimeOfDay();
}

void ADAIslandManager::HandleCalendarVisualHour(int32 NewHour)
{
	const UDACalendarSubsystem* Calendar = BoundCalendar.Get();
	if (Calendar)
	{
		SetCalendarTime(Calendar->GetAbsoluteDay(), static_cast<float>(NewHour));
	}
}

void ADAIslandManager::AdjustTimeSpeed(float Factor)
{
	if (!FMath::IsFinite(Factor) || Factor <= 0.f)
	{
		return;
	}
	if (!FMath::IsFinite(TimeSpeed))
	{
		TimeSpeed = 1.f;
	}
	TimeSpeed = FMath::Clamp(TimeSpeed * Factor, 1.f, 240.f);
}

void ADAIslandManager::ApplyTimeOfDay()
{
	// OnConstruction can run before BeginPlay, so keep this safe for authored
	// or serialized values that were never sanitised yet.
	const float SafeHour = FMath::IsFinite(Hour) ? FMath::Clamp(Hour, 0.f, 24.f - KINDA_SMALL_NUMBER) : 0.f;
	const float SafeMaxElevation = FMath::IsFinite(MaxSunElevation) ? MaxSunElevation : 64.f;

	// Sun path: rises in the east (+X), peaks over the south (+Y in UE, the island's north is -Y), sets west.
	const float Phase = (SafeHour - 6.f) / 24.f * 2.f * PI;
	const float Elevation = SafeMaxElevation * FMath::Sin(Phase);
	const float SunYaw = 180.f + (SafeHour - 6.f) / 12.f * 180.f;

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
		UKismetMaterialLibrary::SetScalarParameterValue(this, ParameterCollection, TEXT("TimeOfDay"), SafeHour);
		// Key light for the anime cast's cel material (rim light / hair highlight, M_DA_Cel): the direction
		// *towards* the sun by day and the moon by night, so the rim always sits on the side the light comes from.
		const FRotator SunRot(-Elevation, SunYaw, 0.f);
		const FRotator MoonRot(-MoonElevation, SunYaw + 160.f, 0.f);
		const FVector ToSun = -SunRot.Vector();
		const FVector ToMoon = -MoonRot.Vector();
		const FVector ToKey = (ToSun * (1.f - NightFactor) + ToMoon * NightFactor).GetSafeNormal(KINDA_SMALL_NUMBER, FVector::UpVector);
		UKismetMaterialLibrary::SetVectorParameterValue(this, ParameterCollection, TEXT("SunDirection"),
			FLinearColor(ToKey.X, ToKey.Y, ToKey.Z, 1.f - 0.6f * NightFactor));
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
	const float SafeHour = FMath::IsFinite(Hour) ? FMath::Clamp(Hour, 0.f, 24.f - KINDA_SMALL_NUMBER) : 0.f;
	const int32 H = FMath::Clamp(FMath::FloorToInt(SafeHour), 0, 23);
	const int32 M = FMath::Clamp(FMath::FloorToInt((SafeHour - static_cast<float>(H)) * 60.f), 0, 59);
	return FString::Printf(TEXT("Day %d  %02d:%02d"), Day, H, M);
}

bool ADAIslandManager::MergeSkeletonBones(USkeletalMesh* Mesh)
{
#if WITH_EDITOR
	if (!Mesh)
	{
		return false;
	}
	USkeleton* Skeleton = Mesh->GetSkeleton();
	if (!Skeleton)
	{
		return false;
	}
	const bool bMerged = Skeleton->MergeAllBonesToBoneTree(Mesh, false);
	const bool bChanged = bMerged || Skeleton->RecreateBoneTree(Mesh);
	if (bChanged)
	{
		Skeleton->Modify();
		Skeleton->MarkPackageDirty();
	}
	return bChanged;
#else
	return false;
#endif
}
