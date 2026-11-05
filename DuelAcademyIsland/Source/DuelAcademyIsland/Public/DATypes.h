// Duel Academy Island - shared types.

#pragma once

#include "CoreMinimal.h"
#include "DATypes.generated.h"

/** The three dorms of Duel Academy (+ the Society of Light's white uniform). */
UENUM(BlueprintType)
enum class EDADorm : uint8
{
	Slifer  UMETA(DisplayName = "Slifer Red"),
	Ra      UMETA(DisplayName = "Ra Yellow"),
	Obelisk UMETA(DisplayName = "Obelisk Blue"),
	White   UMETA(DisplayName = "Society of Light")
};

/** What happens when the player presses Interact on an ADAInteractable. */
UENUM(BlueprintType)
enum class EDAInteractKind : uint8
{
	Sign,
	CardShop,
	DuelField,
	Info,
	RoomBed,
	WalkHome
};

/** A message shown in the HUD's dialogue panel. */
USTRUCT(BlueprintType)
struct FDAMessage
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString Title;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString Body;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FLinearColor Accent = FLinearColor(1.f, 0.75f, 0.2f);

	/** Seconds the panel stays up (0 = until dismissed). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Duration = 8.f;
};

namespace DuelAcademy
{
	/** Jacket colour (linear) for a dorm. */
	inline FLinearColor DormColor(EDADorm Dorm)
	{
		switch (Dorm)
		{
		case EDADorm::Ra:      return FLinearColor(0.91f, 0.60f, 0.02f);
		case EDADorm::Obelisk: return FLinearColor(0.014f, 0.064f, 0.48f);
		case EDADorm::White:   return FLinearColor(0.88f, 0.88f, 0.88f);
		case EDADorm::Slifer:
		default:               return FLinearColor(0.52f, 0.007f, 0.005f);
		}
	}

	inline FString DormName(EDADorm Dorm)
	{
		switch (Dorm)
		{
		case EDADorm::Ra:      return TEXT("Ra Yellow");
		case EDADorm::Obelisk: return TEXT("Obelisk Blue");
		case EDADorm::White:   return TEXT("Society of Light");
		case EDADorm::Slifer:
		default:               return TEXT("Slifer Red");
		}
	}

	/** Content paths of assets created by the editor build script. */
	inline constexpr const TCHAR* AvatarFolder = TEXT("/Game/DuelAcademy/Meshes/Characters/");
	inline constexpr const TCHAR* HologramMaterial = TEXT("/Game/DuelAcademy/Materials/M_DA_Hologram.M_DA_Hologram");
	inline constexpr const TCHAR* CardBackMaterial = TEXT("/Game/DuelAcademy/Materials/MI_M_CardBack.MI_M_CardBack");
	inline constexpr const TCHAR* SmokeMaterial = TEXT("/Game/DuelAcademy/Materials/M_DA_Smoke.M_DA_Smoke");
	inline constexpr const TCHAR* BeamMaterial = TEXT("/Game/DuelAcademy/Materials/MI_M_Beam.MI_M_Beam");
	inline constexpr const TCHAR* SoundFolder = TEXT("/Game/DuelAcademy/Audio/");
}
