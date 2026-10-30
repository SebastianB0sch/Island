// Duel Academy Island - named scene anchor (camera / player / NPC marks).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DASceneAnchor.generated.h"

class USceneComponent;
class UBillboardComponent;
class UTextRenderComponent;

UENUM(BlueprintType)
enum class EDASceneAnchorKind : uint8
{
	Camera  UMETA(DisplayName = "Camera"),
	Player  UMETA(DisplayName = "Player"),
	Npc     UMETA(DisplayName = "NPC"),
	LookAt  UMETA(DisplayName = "Look-at target"),
	Stage   UMETA(DisplayName = "Stage / podium"),
	Prop    UMETA(DisplayName = "Prop marker")
};

/**
 * A named mark used by the story/cutscene layer (A03/A09) and by validation.
 *
 * Camera anchors carry a FOV; all anchors can carry a look-at target. The
 * story command queue references AnchorId, never a raw world coordinate, so
 * moving a room only changes this actor and anchors.json.
 */
UCLASS(Blueprintable)
class DUELACADEMYISLAND_API ADASceneAnchor : public AActor
{
	GENERATED_BODY()

public:
	ADASceneAnchor();

	virtual void OnConstruction(const FTransform& Transform) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Anchor")
	FString AnchorId = TEXT("anchor");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Anchor")
	EDASceneAnchorKind Kind = EDASceneAnchorKind::Camera;

	/** Camera field of view in degrees. Ignored by non-camera anchors. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Anchor", meta = (ClampMin = "10", ClampMax = "120"))
	float FOV = 50.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Anchor")
	bool bUseLookAt = false;

	/** World-space target (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Anchor")
	FVector LookAtTarget = FVector::ZeroVector;

	/** Free-form tags: "opening", "E01", "gym_assembly", "cutscene", ... */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Anchor")
	TArray<FString> AnchorTags;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Anchor")
	FString Description;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Anchor")
	FVector GetAnchorLocation() const { return GetActorLocation(); }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Anchor")
	FRotator GetAnchorRotation() const { return GetActorRotation(); }

	/** Look-at target, or a point one metre in front of the anchor when unset. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Anchor")
	FVector GetLookAtLocation() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Anchor")
	FTransform GetViewTransform() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Anchor")
	bool HasTag(const FString& Tag) const;

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Anchor")
	TObjectPtr<USceneComponent> Root;

#if WITH_EDITORONLY_DATA
	UPROPERTY(VisibleAnywhere, Category = "Duel Academy|Anchor")
	TObjectPtr<UBillboardComponent> EditorIcon;

	UPROPERTY(VisibleAnywhere, Category = "Duel Academy|Anchor")
	TObjectPtr<UTextRenderComponent> EditorLabel;
#endif
};
