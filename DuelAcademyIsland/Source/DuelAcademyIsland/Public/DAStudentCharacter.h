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
class UDAMotorcycleComponent;
class UDAMovementAudioComponent;
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
 *   V / Y                  summon / stow the motorcycle (Shift / L3 = boost while riding)
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

	/** Raising the duel disk (a duel starting) also gets the student off the motorcycle. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetDuelPose(bool bOn);

	/**
	 * Mount (summoning the bike) or dismount (stowing it). Mounting is refused
	 * indoors, in deep water and while a modal screen owns the input; refusals
	 * show a short message unless bQuiet. Returns whether the student now rides.
	 */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy|Motorcycle")
	bool SetRiding(bool bRide, bool bQuiet = false);

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Motorcycle")
	bool IsRiding() const { return bRiding; }

	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void FastTravelTo(ADALocationVolume* Zone);

	/**
	 * Pinned cross-workstream contract (WS-05 consumes from portal code):
	 * strictly focus-clearing. A teleport makes the departure view's world
	 * focus meaningless, so drop it and let the next focus poll re-acquire from
	 * the arrival point. Never teleports, moves, or changes any mode.
	 */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void NotifyTeleportArrived();

	/** The interactable actor currently in focus (implements IDAInteractableInterface), or null. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	AActor* GetFocusedInteractable() const { return FocusedInteractable.Get(); }

	void AddCardToCollection(const FString& CardName) { CardCollection.Add(CardName); }
	int32 GetCollectionSize() const { return CardCollection.Num(); }

	bool IsSwimming() const { return bSwimming; }
	bool IsSprinting() const { return bSprinting; }

	/** True while the player is inside a generated interior cell (its Z is far below the island). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetInInterior(bool bNewInInterior);

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	bool IsInInterior() const { return bInInterior; }

	/**
	 * Pure gate for DAA02GateTests: the exact denominator the pawn's world
	 * input gate consults. The flags mirror ADAHUD's modal-ownership set
	 * (IsModalOpen + bHelpOpen). No world object is touched, so headless tests
	 * enumerate every modal combination. Nothing outside this class and the
	 * headless gate test may call it.
	 */
	static bool WorldInputAllowedFor(bool bDuelOpen, bool bMapOpen, bool bDialogueOpen, bool bPDAOpen,
		bool bTitleOpen, bool bGameplayUIOpen, bool bHelpOpen);

	/** Pure mount gate (headless-tested): the bike needs world input, open air and solid footing. */
	static bool CanMountFor(bool bWorldInputAllowed, bool bInInterior, bool bSwimming);

	/**
	 * Pure steering step (headless-tested): turn CurrentYaw towards DesiredYaw by at most
	 * TurnRate * DeltaSeconds degrees. Returns the new yaw, normalised to (-180, 180].
	 */
	static float StepBikeYaw(float CurrentYaw, float DesiredYaw, float TurnRate, float DeltaSeconds);

	/** Turn rate (deg/s) of the bike at a ground speed: nimble when slow, wide arcs at full speed. */
	static float BikeTurnRateFor(float Speed, float TopSpeed);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Movement")
	float WalkSpeed = 150.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Movement")
	float SprintSpeed = 420.f;

	/** Front-crawl speed (cm/s); Shift swims 1.45x faster. 1.5 m/s is a strong swimmer (the old
	 *  3.3 m/s was faster than the world record and left the stroke far behind the body). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Movement")
	float SwimSpeed = 150.f;

	/** Motorcycle cruising speed (cm/s; 1500 = 54 km/h). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float BikeSpeed = 1500.f;

	/** Motorcycle speed with Shift / L3 held (cm/s; 2200 = 79 km/h). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float BikeBoostSpeed = 2200.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float BikeAcceleration = 1300.f;

	/** Deceleration when steering hard against the direction of travel (cm/s^2). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float BikeBrakeDeceleration = 2600.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float BikeJumpZVelocity = 520.f;

	/** Steepest slope (degrees) the bike climbs; walking stops at 46. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float BikeWalkableSlope = 56.f;

	/** Kerbs, roots and rocks the bike rolls over (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Motorcycle")
	float BikeStepHeight = 60.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Camera")
	float MinZoom = 180.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Camera")
	float MaxZoom = 1400.f;

	/** Under a roof (walking into a building through its door) the camera pulls in to at most this boom
	 *  length (cm) and eases back out to the player's own zoom outdoors - no loading, no separate interior. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Camera")
	float IndoorZoom = 240.f;

	/** A ceiling closer than this above the head (cm) counts as indoors. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Camera")
	float IndoorCeilingCheck = 900.f;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Camera")
	bool IsIndoors() const { return bIndoors; }

	/** The protagonists' bespoke models (Tools/dai/anime/hero.py): the profile's gender picks one at BeginPlay.
	 *  Scales are cast.scale_of() of the two cast entries (172 cm / 163 cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Avatar")
	FString HeroCastMesh = TEXT("SK_Anime_Hero");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Avatar")
	FString HeroAnimGroup = TEXT("VroidC");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Avatar")
	float HeroScale = 0.987f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Avatar")
	FString HeroineCastMesh = TEXT("SK_Anime_Heroine");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Avatar")
	FString HeroineAnimGroup = TEXT("VroidA");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy|Avatar")
	float HeroineScale = 1.052f;

	/** True for the profile genders that select the heroine ("female", "f", "woman", "girl"; any case). */
	static bool IsHeroineGender(const FString& Gender);

protected:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UCameraComponent> FollowCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UDAAvatarComponent> Avatar;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy")
	TObjectPtr<UDAMotorcycleComponent> Bike;

	/** Procedural footsteps, body/cloth, wind and water (silent while riding). */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Duel Academy|Audio")
	TObjectPtr<UDAMovementAudioComponent> MovementAudio;

private:
	void CreateInput();
	void AddMappingContext();
	ADAHUD* GetDAHUD() const;
	bool IsMovementBlocked() const;
	void UpdateFocus();
	void UpdateSwimming(float DeltaSeconds);
	void UpdateRiding(float DeltaSeconds);
	void ApplyMovementProfile(bool bRide);
	void AttachAvatar(bool bToBike);
	void PushBikeMessage(const TCHAR* Title, const TCHAR* Body) const;

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
	void OnJacket(const FInputActionValue& V);
	void OnDuelDisk(const FInputActionValue& V);
	void OnBike(const FInputActionValue& V);
	void OnHelp(const FInputActionValue& V);
	void OnTimePause(const FInputActionValue& V);
	void OnTimeFaster(const FInputActionValue& V);
	void OnTimeSlower(const FInputActionValue& V);
	void OnTimeSkip(const FInputActionValue& V);
	void MoveInput(float Forward, float Right);

	/**
	 * True when no HUD modal owns the screen. World hotkeys (F/J/T/N/[/]/E and
	 * the map toggle's own opens) route through this one gate so nothing leaks
	 * under the map, help, or gameplay Canvas modals. Movement and camera keep
	 * IsMovementBlocked() (help is deliberately not movement-blocking).
	 */
	bool IsWorldInputAllowed() const;

	UPROPERTY(Transient)
	TObjectPtr<UInputMappingContext> MappingContext;

	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<UInputAction>> Actions;

	TWeakObjectPtr<AActor> FocusedInteractable;
	TSet<FString> CardCollection;
	bool bSprinting = false;
	bool bSwimming = false;
	bool bInInterior = false;
	bool bDuelPose = false;
	bool bManualDuelPose = false;
	bool bRiding = false;
	/** Camera-relative steering wish gathered from this frame's move input, consumed by UpdateRiding. */
	FVector RideInput = FVector::ZeroVector;
	float BikeSteer = 0.f;
	float BikeLean = 0.f;
	float BikePitch = 0.f;
	float BikeYawRate = 0.f;
	float PreRideZoom = 520.f;
	float LookIdleTime = 0.f;
	float TargetZoom = 520.f;
	bool bIndoors = false;
	float IndoorTimer = 0.f;
	float SwimAlpha = 0.f;
	float FocusTimer = 0.f;
	FVector SafeLocation = FVector::ZeroVector;
	float SafeTimer = 0.f;
};
