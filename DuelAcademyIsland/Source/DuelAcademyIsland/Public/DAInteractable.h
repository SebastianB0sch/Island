// Duel Academy Island - signs, card shop, holographic duel fields.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DATypes.h"
#include "DAInteractableInterface.h"
#include "DAInteractable.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;
class UPointLightComponent;
class UBillboardComponent;

/** One holographic element of a running duel (card or monster part). */
USTRUCT()
struct FDAHoloPiece
{
	GENERATED_BODY()

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Mesh;

	FVector BaseLocation = FVector::ZeroVector;
	FVector BaseScale = FVector::OneVector;
	FRotator BaseRotation = FRotator::ZeroRotator;
	float Delay = 0.f;
	float Spin = 0.f;
	float Bob = 0.f;
	/** 0 = card, 1 = the player's monster, 2 = the rival's monster. */
	int32 Group = 0;
};

/**
 * Interactable point placed by the build script.
 *   Sign      - shows Title / Text in the dialogue panel
 *   CardShop  - opens a booster pack (5 random cards from the academy card list)
 *   DuelField - starts a short holographic duel show on the field
 *   Info      - like Sign, but no world marker
 */
UCLASS(Blueprintable)
class DUELACADEMYISLAND_API ADAInteractable : public AActor, public IDAInteractableInterface
{
	GENERATED_BODY()

public:
	ADAInteractable();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	EDAInteractKind Kind = EDAInteractKind::Sign;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString Title;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy", meta = (MultiLine = true))
	FString Text;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float Radius = 300.f;

	/** Show a floating holographic marker above duel fields / the card shop. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	bool bShowMarker = true;

	// IDAInteractableInterface
	virtual FString GetInteractPrompt() const override;
	virtual FString GetInteractName() const override;
	virtual FVector GetInteractLocation() const override { return GetActorLocation(); }
	virtual float GetInteractRadius() const override { return Radius; }
	virtual bool CanInteract(const ADAStudentCharacter* By) const override;
	virtual void Interact(ADAStudentCharacter* By) override;

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	bool IsDuelRunning() const { return DuelTime >= 0.f; }

private:
	void OpenBoosterPack(ADAStudentCharacter* By);
	void StartDuel(ADAStudentCharacter* By);
	void EndDuel();
	UStaticMeshComponent* AddHoloMesh(const TCHAR* EngineShape, UMaterialInterface* Material);

	UPROPERTY(VisibleAnywhere, Category = "Duel Academy")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, Category = "Duel Academy")
	TObjectPtr<UStaticMeshComponent> Marker;

#if WITH_EDITORONLY_DATA
	UPROPERTY(VisibleAnywhere, Category = "Duel Academy")
	TObjectPtr<UBillboardComponent> EditorIcon;
#endif

	UPROPERTY(Transient)
	TObjectPtr<UPointLightComponent> HoloLight;

	UPROPERTY(Transient)
	TArray<FDAHoloPiece> HoloPieces;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> HoloMID;

	TWeakObjectPtr<ADAStudentCharacter> Duelist;
	float DuelTime = -1.f;
	float MarkerTime = 0.f;
	int32 LifePointsA = 4000;
	int32 LifePointsB = 4000;
	int32 DuelStep = 0;
	int32 PacksOpened = 0;
};
