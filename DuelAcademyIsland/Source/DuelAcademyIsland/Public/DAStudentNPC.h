// Duel Academy Island - ambient student NPC (wanders, faces the player, chats).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "DATypes.h"
#include "DAInteractableInterface.h"
#include "DAStudentNPC.generated.h"

class UDAAvatarComponent;

UCLASS(Blueprintable)
class DUELACADEMYISLAND_API ADAStudentNPC : public ACharacter, public IDAInteractableInterface
{
	GENERATED_BODY()

public:
	ADAStudentNPC();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void Tick(float DeltaSeconds) override;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	EDADorm Dorm = EDADorm::Slifer;

	/** How far (cm) the student strolls from where it was placed. 0 = stands still. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float WanderRadius = 800.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float StrollSpeed = 140.f;

	/** Anime cast mesh / skeleton group (set by the editor build from layout.json + cast.json). Empty: the
	 *  avatar component's defaults. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString CastMesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString AnimGroup;

	/** Generic students wear their dorm's jacket colour; named characters keep their own look. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	bool bDormTint = true;

	/** Uniform size of the figure; 0 = a random student size. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float BodyScale = 0.f;

	/** Named characters (Jaden, Alexis, ...): HUD name and what they say. Empty: a generic student of the dorm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	TArray<FString> Lines;

	// IDAInteractableInterface
	virtual FString GetInteractPrompt() const override { return TEXT("Talk"); }
	virtual FString GetInteractName() const override;
	virtual FVector GetInteractLocation() const override { return GetActorLocation(); }
	virtual float GetInteractRadius() const override { return 260.f; }
	virtual void Interact(ADAStudentCharacter* By) override;

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UDAAvatarComponent> Avatar;

private:
	void PickNewTarget();
	bool IsSafeAhead(const FVector& Dir) const;

	FVector Home = FVector::ZeroVector;
	FVector Target = FVector::ZeroVector;
	float IdleTime = 0.f;
	float StuckTime = 0.f;
	float TalkTime = -100.f;
	int32 LineIndex = 0;
	FRandomStream Rng;
};
