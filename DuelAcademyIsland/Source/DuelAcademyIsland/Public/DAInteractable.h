// Duel Academy Island - signs, card shop, duel fields.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DATypes.h"
#include "DAInteractableInterface.h"
#include "DAInteractable.generated.h"

class USceneComponent;
class UStaticMeshComponent;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UBillboardComponent;

/**
 * Interactable point placed by the build script.
 *   Sign      - shows Title / Text in the dialogue panel
 *   CardShop  - opens a booster pack (5 random cards from the academy card list)
 *   DuelField - opens the starter-deck picker and starts a full duel
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

	/** Duel field opponent (portrait id, display name and AI deck id). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	FString OpponentId = TEXT("jaden");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	FString OpponentName = TEXT("Jaden Yuki");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	FString OpponentDeckId = TEXT("jaden");

	// IDAInteractableInterface
	virtual FString GetInteractPrompt() const override;
	virtual FString GetInteractName() const override;
	virtual FVector GetInteractLocation() const override { return GetActorLocation(); }
	virtual float GetInteractRadius() const override { return Radius; }
	virtual bool CanInteract(const ADAStudentCharacter* By) const override;
	virtual void Interact(ADAStudentCharacter* By) override;

private:
	void OpenBoosterPack(ADAStudentCharacter* By);
	void StartDuel(ADAStudentCharacter* By);

	UPROPERTY(VisibleAnywhere, Category = "Duel Academy")
	TObjectPtr<USceneComponent> Root;

	UPROPERTY(VisibleAnywhere, Category = "Duel Academy")
	TObjectPtr<UStaticMeshComponent> Marker;

#if WITH_EDITORONLY_DATA
	UPROPERTY(VisibleAnywhere, Category = "Duel Academy")
	TObjectPtr<UBillboardComponent> EditorIcon;
#endif

	float MarkerTime = 0.f;
	int32 PacksOpened = 0;
};
