// Duel Academy Island - interior portal / door trigger.
//
// A portal is deliberately self-contained: it is placed by the editor build
// script (or by hand for debugging), holds the destination in data, fades the
// camera with the engine's built-in camera fade, and teleports the player. It
// does not depend on a UI, a loading screen or a Blueprint.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DAInteractableInterface.h"
#include "DAInteriorPortal.generated.h"

class UBoxComponent;
class UBillboardComponent;
class ADAInteriorPortal;
class ADAStudentCharacter;

/** Optional flag query so the story/profile layer can answer door locks without the portal depending on it. */
DECLARE_DELEGATE_RetVal_OneParam(bool, FDAPortalFlagQuery, const FString&);

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FDAPortalUsedSignature, ADAInteriorPortal*, Portal, AActor*, User);

/** Small serializable slice owned by the portal; A02 can embed it in the save payload. */
USTRUCT(BlueprintType)
struct FDAPortalSaveState
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, Category = "Duel Academy|Portal")
	FString PortalId;

	UPROPERTY(BlueprintReadWrite, Category = "Duel Academy|Portal")
	bool bLocked = false;

	UPROPERTY(BlueprintReadWrite, Category = "Duel Academy|Portal")
	bool bUsed = false;
};

/**
 * A door / trigger that moves the player to an interior cell (or back outside).
 *
 *  - Place it at a door, set PortalId (unique), InteriorId, TargetLocation,
 *    TargetYaw and TargetPortalId (the paired portal, used for return state).
 *  - bAutoTrigger lets the player walk in; bInteractable also exposes the
 *    standard "E / Interact" prompt through IDAInteractableInterface.
 *  - The fade is APlayerCameraManager::StartCameraFade, so no UMG asset is
 *    needed. The teleport happens when the fade-out reaches black.
 */
UCLASS(Blueprintable)
class DUELACADEMYISLAND_API ADAInteriorPortal : public AActor, public IDAInteractableInterface
{
	GENERATED_BODY()

public:
	ADAInteriorPortal();

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void OnConstruction(const FTransform& Transform) override;

	// ---------------------------------------------------------------- identity / destination
	/** Unique id; referenced by portals.json, anchors.json and SaveGame. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	FString PortalId = TEXT("portal");

	/** Interior cell id (interiors.json). Empty for an exterior-to-exterior shortcut. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	FString InteriorId;

	/** The paired portal that occupies the other side of this door. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	FString TargetPortalId;

	/** Fallback arrival point when TargetPortalId is not found. World space, cm. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	FVector TargetLocation = FVector::ZeroVector;

	/** Fallback arrival yaw, degrees. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	float TargetYaw = 0.f;

	/** If true and the linked portal exists, arrive in front of the linked portal using ArrivalOffset. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	bool bSnapToLinkedPortal = false;

	/** Arrival distance in front of the linked portal (cm) when bSnapToLinkedPortal is true. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	float ArrivalOffset = 140.f;

	// ---------------------------------------------------------------- trigger / fade
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	FVector TriggerExtent = FVector(110.f, 110.f, 120.f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	bool bAutoTrigger = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	bool bInteractable = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	float InteractionRadius = 280.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	FString DisplayName = TEXT("Door");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	FString Prompt = TEXT("Enter");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	float CooldownSeconds = 1.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	float FadeOutSeconds = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	float FadeInSeconds = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	FLinearColor FadeColor = FLinearColor(0.f, 0.f, 0.f, 1.f);

	// ---------------------------------------------------------------- lock condition
	/** Direct runtime lock (story event, dorm restriction, exam in progress, ...). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal|Lock")
	bool bLocked = false;

	/** Optional profile/story flag that must be true. Empty = no flag check. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal|Lock")
	FString RequiredFlag;

	/** If the flag query is not bound yet, should a RequiredFlag keep the door shut? */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal|Lock")
	bool bFailClosedWhenFlagQueryMissing = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal|Lock")
	FString LockReason = TEXT("This door is locked.");

	/** Return-portal marker used by save/UI (the destination side of a pair). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Portal")
	bool bReturnPortal = false;

	/** True after the first successful use; story/UI may use it for "first visit" beats. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Portal")
	bool bUsed = false;

	// ---------------------------------------------------------------- events / API
	UPROPERTY(BlueprintAssignable, Category = "Duel Academy|Portal")
	FDAPortalUsedSignature OnPortalUsed;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Portal")
	bool TryUse(AActor* User);

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Portal")
	void SetLocked(bool bNewLocked, const FString& InReason = FString());

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Portal")
	void SetRequiredFlag(const FString& Flag) { RequiredFlag = Flag; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Portal")
	bool IsPortalLocked() const { return bLocked; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Portal")
	bool IsOnCooldown() const;

	/** Put the portal (usually the destination side) on cooldown for Seconds. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Portal")
	void ArmCooldown(float Seconds);

	/** Ignore overlap triggers from User until they leave this trigger (prevents ping-pong). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Portal")
	void SuppressFor(AActor* User);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Portal")
	ADAInteriorPortal* FindLinkedPortal() const;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Portal")
	FDAPortalSaveState GetSaveState() const;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Portal")
	void ApplySaveState(const FDAPortalSaveState& State);

	/** Override this in a Blueprint or a C++ subclass for event-specific rules. */
	UFUNCTION(BlueprintNativeEvent, BlueprintCallable, Category = "Duel Academy|Portal|Lock")
	bool CanUsePortal(AActor* User) const;
	virtual bool CanUsePortal_Implementation(AActor* User) const;

	/** Optional hook for A02. Bind once from the game mode/profile subsystem. */
	static FDAPortalFlagQuery FlagQuery;

	// IDAInteractableInterface
	virtual FString GetInteractPrompt() const override;
	virtual FString GetInteractName() const override;
	virtual FVector GetInteractLocation() const override { return GetActorLocation(); }
	virtual float GetInteractRadius() const override { return InteractionRadius; }
	virtual bool CanInteract(const ADAStudentCharacter* By) const override;
	virtual void Interact(ADAStudentCharacter* By) override;

protected:
	UFUNCTION()
	void HandleBeginOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
		int32 OtherBodyIndex, bool bFromSweep, const FHitResult& SweepResult);

	UFUNCTION()
	void HandleEndOverlap(UPrimitiveComponent* OverlappedComponent, AActor* OtherActor, UPrimitiveComponent* OtherComp,
		int32 OtherBodyIndex);

	void BeginTeleport(AActor* User);
	void FinishTeleport();
	void ApplyArrival(AActor* User);
	void ClearSuppression();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Portal")
	TObjectPtr<UBoxComponent> Trigger;

#if WITH_EDITORONLY_DATA
	UPROPERTY(VisibleAnywhere, Category = "Duel Academy|Portal")
	TObjectPtr<UBillboardComponent> EditorIcon;
#endif

private:
	TWeakObjectPtr<AActor> PendingUser;
	TWeakObjectPtr<AActor> SuppressedUser;
	FVector PendingLocation = FVector::ZeroVector;
	float PendingYaw = 0.f;
	FTimerHandle TeleportTimer;
	FTimerHandle SuppressTimer;
	double CooldownUntil = 0.0;
	bool bTeleportPending = false;
};
