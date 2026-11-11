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
};

/**
 * Where a motorcycle rider's body goes this frame (UDAMotorcycleComponent -> UDAAvatarComponent).
 * Points are in the rider mount's space, the avatar's attach parent while riding (cm; +X forward,
 * +Y the bike's right, +Z up). They follow the steering, both suspensions and the lean.
 */
struct FDARiderTargets
{
	bool bValid = false;
	/** Seat surface under the rider's hips (already slid sideways for a foot-down stop). */
	FVector Seat = FVector::ZeroVector;
	/** Handlebar grip centres. */
	FVector GripLeft = FVector::ZeroVector;
	FVector GripRight = FVector::ZeroVector;
	/** Foot-peg tops, where the ball of each foot rests. */
	FVector PegLeft = FVector::ZeroVector;
	FVector PegRight = FVector::ZeroVector;
	/** The ground beside the left peg, where the left foot goes down at a stop. */
	FVector GroundLeft = FVector::ZeroVector;
	/** 0..1: the left foot is off its peg and on the ground (stopped). */
	float FootDown = 0.f;
	/** 0..1: standing on the pegs, knees and elbows bent (airborne, landings). */
	float Stand = 0.f;
	/** 0..1: chest down over the tank (boosting at speed). */
	float Tuck = 0.f;
	/** -1..1: weight back, braced on the bars (hard braking) .. forward over the tank (hard acceleration). */
	float Drive = 0.f;
	/** Upper-body roll relative to the bike (degrees, positive towards the bike's right). */
	float BodyRoll = 0.f;
	/** Extra neck/head roll (degrees, positive towards the bike's right) that keeps the eyes nearer level. */
	float HeadRoll = 0.f;
	/** cm the hips sink below their seated / standing height (legs soaking up a landing). */
	float Sink = 0.f;

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
	/** Custom depth stencil value of the anime cast meshes (PP_DA_Cel bands their lighting). */
	inline constexpr int32 CastStencil = 1;
	inline constexpr const TCHAR* HologramMaterial = TEXT("/Game/DuelAcademy/Materials/M_DA_Hologram.M_DA_Hologram");
	inline constexpr const TCHAR* CardBackMaterial = TEXT("/Game/DuelAcademy/Materials/MI_M_CardBack.MI_M_CardBack");
	inline constexpr const TCHAR* SmokeMaterial = TEXT("/Game/DuelAcademy/Materials/M_DA_Smoke.M_DA_Smoke");
	inline constexpr const TCHAR* SprayMaterial = TEXT("/Game/DuelAcademy/Materials/M_DA_Spray.M_DA_Spray");
	inline constexpr const TCHAR* BeamMaterial = TEXT("/Game/DuelAcademy/Materials/MI_M_Beam.MI_M_Beam");
	inline constexpr const TCHAR* SoundFolder = TEXT("/Game/DuelAcademy/Audio/");
}
