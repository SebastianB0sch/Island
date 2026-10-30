// Duel Academy Island - the playable student.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "InputActionValue.h"
#include "DATypes.h"
#include "DAStudentCharacter.generated.h"

class USpringArmComponent;
class UCameraComponent;
class UDAAvatarComponent;
class UInputAction;
class UInputMappingContext;
class ADALocationVolume;
class ADAHUD;

/**
 * Third-person student. All input actions and the mapping context are created
 * in code, so the project needs no input assets:
 *
 *   WASD / left stick      move            Shift / L3      sprint
 *   Mouse / right stick    look            Space / A       jump
 *   Mouse wheel            zoom            E / X           interact
 *   M / Tab / Start        island map + fast travel (Up/Down/Enter or click)
 *   J                      switch dorm jacket   F   raise duel disk
 *   T  pause time   [ ]  time speed   N  skip 3 hours   F1 / H  help
 */
UCLASS(Blueprintable)
class DUELACADEMYISLAND_API ADAStudentCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ADAStudentCharacter();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
	virtual void PawnClientRestart() override;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetDorm(EDADorm NewDorm);

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	EDADorm GetDorm() const;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetDuelPose(bool bOn) { bDuelPose = bOn; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void FastTravelTo(ADALocationVolume* Zone);

	/** The interactable actor currently in focus (implements IDAInteractableInterface), or null. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	AActor* GetFocusedInteractable() const { return FocusedInteractable.Get(); }

	void AddCardToCollection(const FString& CardName) { CardCollection.Add(CardName); }
	int32 GetCollectionSize() const { return CardCollection.Num(); }

	bool IsSwimming() const { return bSwimming; }
	bool IsSprinting() const { return bSprinting; }

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Movement")
	float WalkSpeed = 450.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Movement")
	float SprintSpeed = 950.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Movement")
	float SwimSpeed = 330.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Camera")
	float MinZoom = 180.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Camera")
	float MaxZoom = 1400.f;

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UCameraComponent> FollowCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UDAAvatarComponent> Avatar;

private:
	void CreateInput();
	void AddMappingContext();
	ADAHUD* GetDAHUD() const;
	bool IsDuelOpen() const;
	bool IsMovementBlocked() const;
	void UpdateFocus();
	void UpdateSwimming(float DeltaSeconds);

	// Input handlers
	void OnMoveForward(const FInputActionValue& V) { MoveInput(1.f, 0.f); }
	void OnMoveBack(const FInputActionValue& V) { MoveInput(-1.f, 0.f); }
	void OnMoveLeft(const FInputActionValue& V) { MoveInput(0.f, -1.f); }
	void OnMoveRight(const FInputActionValue& V) { MoveInput(0.f, 1.f); }
	void OnMoveStick(const FInputActionValue& V);
	void OnLook(const FInputActionValue& V);
	void OnLookStick(const FInputActionValue& V);
	void OnZoom(const FInputActionValue& V);
	void OnJump(const FInputActionValue& V);
	void OnJumpReleased(const FInputActionValue& V);
	void OnSprintStart(const FInputActionValue& V);
	void OnSprintStop(const FInputActionValue& V);
	void OnInteract(const FInputActionValue& V);
	void OnMap(const FInputActionValue& V);
	void OnMenuUp(const FInputActionValue& V);
	void OnMenuDown(const FInputActionValue& V);
	void OnMenuSelect(const FInputActionValue& V);
	void OnClick(const FInputActionValue& V);
	void OnJacket(const FInputActionValue& V);
	void OnDuelDisk(const FInputActionValue& V);
	void OnHelp(const FInputActionValue& V);
	void OnTimePause(const FInputActionValue& V);
	void OnTimeFaster(const FInputActionValue& V);
	void OnTimeSlower(const FInputActionValue& V);
	void OnTimeSkip(const FInputActionValue& V);
	void MoveInput(float Forward, float Right);

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> MappingContext;

	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<UInputAction>> Actions;

	TWeakObjectPtr<AActor> FocusedInteractable;
	TSet<FString> CardCollection;
	bool bSprinting = false;
	bool bSwimming = false;
	bool bDuelPose = false;
	bool bManualDuelPose = false;
	float TargetZoom = 520.f;
	float SwimAlpha = 0.f;
	float FocusTimer = 0.f;
	FVector SafeLocation = FVector::ZeroVector;
	float SafeTimer = 0.f;
};
