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

	/** Spots (world, capsule centre) the student may stroll to, precomputed by the build so every walk is a
	 *  clear straight line on one floor (no furniture or walls in the way). The student only walks
	 *  home -> spot -> home. Empty with bWanderPointsOnly: stands still. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	TArray<FVector> WanderPoints;

	/** Wander only along WanderPoints (set by the build). Off: random strolls within WanderRadius. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	bool bWanderPointsOnly = false;

	/** Strolling speed (cm/s). 1.4 m/s is an unhurried adult walk; the avatar's cadence and
	 *  step length follow whatever speed this is, so the feet never skate. */
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

	/** Stable hair colour from the build roster (generic students). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FLinearColor HairColor = FLinearColor(0.12f, 0.035f, 0.01f);

	/** Use HairColor instead of the random hair palette (set for roster NPCs). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	bool bOverrideHairColor = false;

	/** Named characters (Jaden, Alexis, ...): HUD name and what they say. Empty: a generic student of the dorm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString DisplayName;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	TArray<FString> Lines;

	/** Named cast members can be challenged to a duel after the first conversation. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	bool bDuelist = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	FString DuelOpponentId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Duel")
	FString DuelDeckId = TEXT("jaden");

	// IDAInteractableInterface
	virtual FString GetInteractPrompt() const override { return bDuelist && bHasTalked ? TEXT("Duel") : TEXT("Talk"); }
	virtual FString GetInteractName() const override;
	virtual FVector GetInteractLocation() const override { return GetActorLocation(); }
	virtual float GetInteractRadius() const override { return 260.f; }
	virtual bool CanInteract(const ADAStudentCharacter* By) const override;
	virtual void Interact(ADAStudentCharacter* By) override;

	/** Re-anchor the wander area after the director moves this NPC (schedule/teleport). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetWanderHome(const FVector& NewHome);

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
	float GreetTime = -100.f;
	int32 LineIndex = 0;
	bool bHasTalked = false;
	FRandomStream Rng;
};
