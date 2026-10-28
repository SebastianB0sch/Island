// Duel Academy Island - named location zone (banner, map marker, fast travel target).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DALocationVolume.generated.h"

class UBoxComponent;
class UTextRenderComponent;

/**
 * A named area of the island. The subsystem polls which zone the player is in
 * (smallest containing zone wins), the HUD shows its banner, map marker and
 * fast-travel entry. Spawned and configured by the editor build script.
 */
UCLASS(Blueprintable)
class DUELACADEMYISLAND_API ADALocationVolume : public AActor
{
	GENERATED_BODY()

public:
	ADALocationVolume();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString LocationId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString DisplayName = TEXT("Location");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString Subtitle;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy", meta = (MultiLine = true))
	FString Description;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FLinearColor ThemeColor = FLinearColor(1.f, 0.8f, 0.2f);

	/** Half extents of the (yaw-rotated) zone box in cm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FVector ZoneExtent = FVector(5000.0, 5000.0, 3000.0);

	/** Fast-travel arrival point (world space) and facing. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FVector SpawnLocation = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float SpawnYaw = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	bool bShowOnMap = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	bool bFastTravel = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	int32 SortOrder = 0;

	bool ContainsPoint(const FVector& WorldPoint) const;
	double GetZoneVolume() const { return ZoneExtent.X * ZoneExtent.Y * ZoneExtent.Z; }

private:
	UPROPERTY(VisibleAnywhere, Category = "Duel Academy")
	TObjectPtr<UBoxComponent> Box;

#if WITH_EDITORONLY_DATA
	UPROPERTY(VisibleAnywhere, Category = "Duel Academy")
	TObjectPtr<UTextRenderComponent> EditorLabel;
#endif
};
