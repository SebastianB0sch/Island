// Duel Academy Island - the playable student.

#include "DAStudentCharacter.h"

#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "DAAvatarComponent.h"
#include "DACalendarSubsystem.h"
#include "DAHUD.h"
#include "DAInteractableInterface.h"
#include "DAIslandManager.h"
#include "DAIslandSubsystem.h"
#include "DALocationVolume.h"
#include "DAMotorcycleComponent.h"
#include "DAMovementAudioComponent.h"
#include "DAProfileSubsystem.h"
#include "Engine/GameInstance.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputAction.h"
#include "InputMappingContext.h"

namespace
{
	// On-foot movement profile; ApplyMovementProfile swaps these for the bike's and back.
	const float FootAcceleration = 1000.f;
	const float FootBrakingDeceleration = 1400.f;
	const float FootStepHeight = 45.f;
	const float FootWalkableSlope = 46.f;
	const float FootJumpZVelocity = 560.f;
	const float FootAirControl = 0.4f;
	const float BaseFieldOfView = 75.f;
	const FVector AvatarOnFoot(0.0, 0.0, -92.0);
}

ADAStudentCharacter::ADAStudentCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->InitCapsuleSize(38.f, 92.f);

	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;

	UCharacterMovementComponent* Move = GetCharacterMovement();
	Move->bOrientRotationToMovement = true;
	Move->RotationRate = FRotator(0.f, 420.f, 0.f);
	Move->MaxWalkSpeed = WalkSpeed;
	Move->MinAnalogWalkSpeed = 40.f;
	Move->MaxAcceleration = FootAcceleration;
	Move->JumpZVelocity = FootJumpZVelocity;
	Move->AirControl = FootAirControl;
	Move->BrakingDecelerationWalking = FootBrakingDeceleration;
	Move->BrakingDecelerationFalling = 600.f;
	Move->MaxStepHeight = FootStepHeight;
	Move->SetWalkableFloorAngle(FootWalkableSlope);
	Move->MaxFlySpeed = SwimSpeed;
	// Water drag: a swimmer glides to a stop over about half a second instead of halting.
	Move->BrakingDecelerationFlying = 350.f;
	Move->bMaintainHorizontalGroundVelocity = true;

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = TargetZoom;
	CameraBoom->SocketOffset = FVector(0.0, 0.0, 70.0);
	CameraBoom->bUsePawnControlRotation = true;
	CameraBoom->bEnableCameraLag = true;
	CameraBoom->CameraLagSpeed = 14.f;
	CameraBoom->ProbeSize = 14.f;

	FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
	FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	FollowCamera->bUsePawnControlRotation = false;
	FollowCamera->SetFieldOfView(BaseFieldOfView);

	Avatar = CreateDefaultSubobject<UDAAvatarComponent>(TEXT("Avatar"));
	Avatar->SetupAttachment(GetCapsuleComponent());
	Avatar->SetRelativeLocation(AvatarOnFoot);
	// The protagonist's own bespoke model (Tools/dai/anime/hero.py); its coat keeps the dorm tint. BeginPlay
	// switches to the heroine when the profile says so.
	Avatar->CastMesh = HeroCastMesh;
	Avatar->AnimGroup = HeroAnimGroup;
	Avatar->BodyScale = HeroScale;

	Bike = CreateDefaultSubobject<UDAMotorcycleComponent>(TEXT("Motorcycle"));
	Bike->SetupAttachment(GetCapsuleComponent());
	Bike->SetRelativeLocation(AvatarOnFoot);

	MovementAudio = CreateDefaultSubobject<UDAMovementAudioComponent>(TEXT("MovementAudio"));
	MovementAudio->SetupAttachment(GetCapsuleComponent());
	MovementAudio->SetRelativeLocation(AvatarOnFoot);

	// No skeletal mesh: the avatar component draws the student.
	GetMesh()->SetVisibility(false);
	GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

bool ADAStudentCharacter::IsHeroineGender(const FString& Gender)
{
	const FString G = Gender.TrimStartAndEnd().ToLower();
	return G == TEXT("female") || G == TEXT("f") || G == TEXT("woman") || G == TEXT("girl");
}

void ADAStudentCharacter::BeginPlay()
{
	// Pick the protagonist's model before the avatar component sets itself up (its BeginPlay runs inside
	// Super::BeginPlay). The avatar falls back to SK_Anime_StudentM1 when the mesh is not imported.
	if (Avatar)
	{
		const UGameInstance* GameInstance = GetWorld() ? GetWorld()->GetGameInstance() : nullptr;
		const UDAProfileSubsystem* Profile = GameInstance ? GameInstance->GetSubsystem<UDAProfileSubsystem>() : nullptr;
		const bool bHeroine = Profile && IsHeroineGender(Profile->GetGender());
		Avatar->CastMesh = bHeroine ? HeroineCastMesh : HeroCastMesh;
		Avatar->AnimGroup = bHeroine ? HeroineAnimGroup : HeroAnimGroup;
		Avatar->BodyScale = bHeroine ? HeroineScale : HeroScale;
		Avatar->FallbackCastMesh = bHeroine ? TEXT("SK_Anime_StudentF1") : TEXT("SK_Anime_StudentM1");
	}
	Super::BeginPlay();
	CreateInput();
	AddMappingContext();
	if (Bike)
	{
		Bike->SetPaint(DuelAcademy::DormColor(GetDorm()));
	}
	SafeLocation = GetActorLocation();
	// A save loaded inside a generated interior cell must not be "rescued" by
	// the fall-out-of-world safety on the first tick.
	bInInterior = GetActorLocation().Z < -20000.f;
}

void ADAStudentCharacter::PawnClientRestart()
{
	Super::PawnClientRestart();
	CreateInput();
	AddMappingContext();
	// A respawn/possession must not inherit a sprint held by the previous pawn,
	// and the interaction target belongs to the old view.
	bSprinting = false;
	FocusedInteractable.Reset();
	// W5: a mid-deck-select restart (possession change, slot reload) must not
	// walk out with the duel disk raised; CloseDuel clears it normally, but
	// restart happens outside that flow.
	bDuelPose = false;
	bManualDuelPose = false;
	// A new possession starts on foot.
	SetRiding(false, true);
}

// ------------------------------------------------------------------------ input setup

void ADAStudentCharacter::CreateInput()
{
	if (MappingContext)
	{
		return;
	}
	MappingContext = NewObject<UInputMappingContext>(this, TEXT("IMC_DuelAcademy"));

	auto MakeAction = [this](const TCHAR* Name, EInputActionValueType Type) -> UInputAction*
	{
		UInputAction* A = NewObject<UInputAction>(this, FName(FString(TEXT("IA_")) + Name));
		A->ValueType = Type;
		Actions.Add(FName(Name), A);
		return A;
	};
	auto Map = [this](UInputAction* A, const FKey& Key)
	{
		MappingContext->MapKey(A, Key);
	};

	using VT = EInputActionValueType;
	UInputAction* Fwd = MakeAction(TEXT("MoveForward"), VT::Boolean);
	UInputAction* Back = MakeAction(TEXT("MoveBack"), VT::Boolean);
	UInputAction* Left = MakeAction(TEXT("MoveLeft"), VT::Boolean);
	UInputAction* Right = MakeAction(TEXT("MoveRight"), VT::Boolean);
	Map(Fwd, EKeys::W);
	Map(Fwd, EKeys::Z);      // AZERTY
	Map(Back, EKeys::S);
	Map(Left, EKeys::A);
	Map(Left, EKeys::Q);     // AZERTY
	Map(Right, EKeys::D);

	Map(MakeAction(TEXT("MoveStick"), VT::Axis2D), EKeys::Gamepad_Left2D);
	Map(MakeAction(TEXT("Look"), VT::Axis2D), EKeys::Mouse2D);
	Map(MakeAction(TEXT("LookStick"), VT::Axis2D), EKeys::Gamepad_Right2D);
	Map(MakeAction(TEXT("Zoom"), VT::Axis1D), EKeys::MouseWheelAxis);

	UInputAction* JumpAction = MakeAction(TEXT("Jump"), VT::Boolean);
	Map(JumpAction, EKeys::SpaceBar);
	Map(JumpAction, EKeys::Gamepad_FaceButton_Bottom);

	UInputAction* SprintAction = MakeAction(TEXT("Sprint"), VT::Boolean);
	Map(SprintAction, EKeys::LeftShift);
	Map(SprintAction, EKeys::Gamepad_LeftThumbstick);

	UInputAction* InteractAction = MakeAction(TEXT("Interact"), VT::Boolean);
	Map(InteractAction, EKeys::E);
	Map(InteractAction, EKeys::Gamepad_FaceButton_Left);

	UInputAction* MapAction = MakeAction(TEXT("Map"), VT::Boolean);
	Map(MapAction, EKeys::M);
	Map(MapAction, EKeys::Tab);
	Map(MapAction, EKeys::Gamepad_Special_Right);
	// Deliberately no Enhanced Input actions for Up/Down/Enter/click here: the
	// island map owns its menu navigation and click travel by polling keys in
	// ADAHUD::Tick (the bMapOpen && !bHelpOpen block at ADAHUD.cpp:1449), the
	// same pattern the duel UI uses, because GameAndUI input mode can swallow
	// those bindings. Do not re-introduce enhanced-menu handlers here - that
	// was the pre-three-pass double-owner bug.

	Map(MakeAction(TEXT("Jacket"), VT::Boolean), EKeys::J);
	Map(MakeAction(TEXT("DuelDisk"), VT::Boolean), EKeys::F);
	UInputAction* BikeAction = MakeAction(TEXT("Bike"), VT::Boolean);
	Map(BikeAction, EKeys::V);
	Map(BikeAction, EKeys::Gamepad_FaceButton_Top);
	UInputAction* HelpAction = MakeAction(TEXT("Help"), VT::Boolean);
	Map(HelpAction, EKeys::F1);
	Map(HelpAction, EKeys::H);
	Map(MakeAction(TEXT("TimePause"), VT::Boolean), EKeys::T);
	Map(MakeAction(TEXT("TimeFaster"), VT::Boolean), EKeys::RightBracket);
	Map(MakeAction(TEXT("TimeSlower"), VT::Boolean), EKeys::LeftBracket);
	Map(MakeAction(TEXT("TimeSkip"), VT::Boolean), EKeys::N);
}

void ADAStudentCharacter::AddMappingContext()
{
	APlayerController* PC = Cast<APlayerController>(GetController());
	if (!PC || !MappingContext)
	{
		return;
	}
	if (ULocalPlayer* LP = PC->GetLocalPlayer())
	{
		if (UEnhancedInputLocalPlayerSubsystem* Sub = LP->GetSubsystem<UEnhancedInputLocalPlayerSubsystem>())
		{
			Sub->RemoveMappingContext(MappingContext);
			Sub->AddMappingContext(MappingContext, 0);
		}
	}
}

void ADAStudentCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);
	CreateInput();

	UEnhancedInputComponent* EIC = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!EIC)
	{
		UE_LOG(LogTemp, Error, TEXT("DuelAcademy: Enhanced Input component missing - check Config/DefaultInput.ini"));
		return;
	}
	auto A = [this](const TCHAR* Name) -> UInputAction*
	{
		const TObjectPtr<UInputAction>* Found = Actions.Find(FName(Name));
		return Found ? Found->Get() : nullptr;
	};
	EIC->BindAction(A(TEXT("MoveForward")), ETriggerEvent::Triggered, this, &ThisClass::OnMoveForward);
	EIC->BindAction(A(TEXT("MoveBack")), ETriggerEvent::Triggered, this, &ThisClass::OnMoveBack);
	EIC->BindAction(A(TEXT("MoveLeft")), ETriggerEvent::Triggered, this, &ThisClass::OnMoveLeft);
	EIC->BindAction(A(TEXT("MoveRight")), ETriggerEvent::Triggered, this, &ThisClass::OnMoveRight);
	EIC->BindAction(A(TEXT("MoveStick")), ETriggerEvent::Triggered, this, &ThisClass::OnMoveStick);
	EIC->BindAction(A(TEXT("Look")), ETriggerEvent::Triggered, this, &ThisClass::OnLook);
	EIC->BindAction(A(TEXT("LookStick")), ETriggerEvent::Triggered, this, &ThisClass::OnLookStick);
	EIC->BindAction(A(TEXT("Zoom")), ETriggerEvent::Triggered, this, &ThisClass::OnZoom);
	EIC->BindAction(A(TEXT("Jump")), ETriggerEvent::Started, this, &ThisClass::OnJump);
	EIC->BindAction(A(TEXT("Jump")), ETriggerEvent::Completed, this, &ThisClass::OnJumpReleased);
	EIC->BindAction(A(TEXT("Sprint")), ETriggerEvent::Started, this, &ThisClass::OnSprintStart);
	EIC->BindAction(A(TEXT("Sprint")), ETriggerEvent::Completed, this, &ThisClass::OnSprintStop);
	EIC->BindAction(A(TEXT("Interact")), ETriggerEvent::Started, this, &ThisClass::OnInteract);
	EIC->BindAction(A(TEXT("Map")), ETriggerEvent::Started, this, &ThisClass::OnMap);
	// Map navigation and travel are polled by ADAHUD::Tick while the map is open: Enhanced Input can swallow
	// Enter / clicks in the map's GameAndUI input mode.
	EIC->BindAction(A(TEXT("Jacket")), ETriggerEvent::Started, this, &ThisClass::OnJacket);
	EIC->BindAction(A(TEXT("DuelDisk")), ETriggerEvent::Started, this, &ThisClass::OnDuelDisk);
	EIC->BindAction(A(TEXT("Bike")), ETriggerEvent::Started, this, &ThisClass::OnBike);
	EIC->BindAction(A(TEXT("Help")), ETriggerEvent::Started, this, &ThisClass::OnHelp);
	EIC->BindAction(A(TEXT("TimePause")), ETriggerEvent::Started, this, &ThisClass::OnTimePause);
	EIC->BindAction(A(TEXT("TimeFaster")), ETriggerEvent::Started, this, &ThisClass::OnTimeFaster);
	EIC->BindAction(A(TEXT("TimeSlower")), ETriggerEvent::Started, this, &ThisClass::OnTimeSlower);
	EIC->BindAction(A(TEXT("TimeSkip")), ETriggerEvent::Started, this, &ThisClass::OnTimeSkip);
}

ADAHUD* ADAStudentCharacter::GetDAHUD() const
{
	const APlayerController* PC = Cast<APlayerController>(GetController());
	return PC ? Cast<ADAHUD>(PC->GetHUD()) : nullptr;
}

bool ADAStudentCharacter::IsMovementBlocked() const
{
	const ADAHUD* HUD = GetDAHUD();
	return HUD && (HUD->IsDuelOpen() || HUD->IsMapOpen() || HUD->IsDialogueOpen() || HUD->IsPDAOpen() || HUD->IsTitleOpen() || HUD->IsGameplayUIOpen());
}

bool ADAStudentCharacter::WorldInputAllowedFor(bool bDuelOpen, bool bMapOpen, bool bDialogueOpen, bool bPDAOpen,
	bool bTitleOpen, bool bGameplayUIOpen, bool bHelpOpen)
{
	// U1: exactly ADAHUD's modal set. Help sits on top of the map and blocked
	// screens the same way, so one flat "any modal wins" test covers U2's
	// map/help leaks too. A missing HUD keeps the world playable.
	return !(bDuelOpen || bMapOpen || bDialogueOpen || bPDAOpen || bTitleOpen || bGameplayUIOpen || bHelpOpen);
}

bool ADAStudentCharacter::IsWorldInputAllowed() const
{
	const ADAHUD* HUD = GetDAHUD();
	if (!HUD)
	{
		return true;
	}
	return WorldInputAllowedFor(HUD->IsDuelOpen(), HUD->IsMapOpen(), HUD->IsDialogueOpen(), HUD->IsPDAOpen(),
		HUD->IsTitleOpen(), HUD->IsGameplayUIOpen(), HUD->IsHelpOpen());
}

// ------------------------------------------------------------------------ movement / camera

void ADAStudentCharacter::MoveInput(float Forward, float Right)
{
	if (!Controller || IsMovementBlocked())
	{
		return;
	}
	const FRotator YawRot(0.f, Controller->GetControlRotation().Yaw, 0.f);
	const FRotationMatrix M(YawRot);
	if (bRiding)
	{
		// The bike cannot strafe: gather the camera-relative wish and let
		// UpdateRiding steer the heading towards it.
		RideInput += M.GetUnitAxis(EAxis::X) * Forward + M.GetUnitAxis(EAxis::Y) * Right;
		return;
	}
	AddMovementInput(M.GetUnitAxis(EAxis::X), Forward);
	AddMovementInput(M.GetUnitAxis(EAxis::Y), Right);
}

void ADAStudentCharacter::OnMoveStick(const FInputActionValue& V)
{
	const FVector2D Axis = V.Get<FVector2D>();
	MoveInput(Axis.Y, Axis.X);
}

void ADAStudentCharacter::OnLook(const FInputActionValue& V)
{
	if (IsMovementBlocked())
	{
		return;
	}
	const FVector2D Axis = V.Get<FVector2D>();
	if (!Axis.IsNearlyZero())
	{
		LookIdleTime = 0.f;
	}
	AddControllerYawInput(Axis.X);
	AddControllerPitchInput(-Axis.Y);
}

void ADAStudentCharacter::OnLookStick(const FInputActionValue& V)
{
	if (IsMovementBlocked())
	{
		return;
	}
	const FVector2D Axis = V.Get<FVector2D>();
	if (!Axis.IsNearlyZero())
	{
		LookIdleTime = 0.f;
	}
	const float Dt = GetWorld() ? GetWorld()->GetDeltaSeconds() : 0.016f;
	AddControllerYawInput(Axis.X * 140.f * Dt);
	AddControllerPitchInput(-Axis.Y * 100.f * Dt);
}

void ADAStudentCharacter::OnZoom(const FInputActionValue& V)
{
	if (IsMovementBlocked())
	{
		return;
	}
	TargetZoom = FMath::Clamp(TargetZoom - V.Get<float>() * 70.f, MinZoom, MaxZoom);
}

void ADAStudentCharacter::OnJump(const FInputActionValue& V)
{
	if (!bSwimming && !IsMovementBlocked())
	{
		Jump();
	}
}

void ADAStudentCharacter::OnJumpReleased(const FInputActionValue& V)
{
	StopJumping();
}

void ADAStudentCharacter::OnSprintStart(const FInputActionValue& V)
{
	bSprinting = !IsMovementBlocked();
}

void ADAStudentCharacter::OnSprintStop(const FInputActionValue& V)
{
	bSprinting = false;
}

// ------------------------------------------------------------------------ interaction / UI

void ADAStudentCharacter::OnInteract(const FInputActionValue& V)
{
	if (!IsWorldInputAllowed())
	{
		return;
	}
	UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this);
	if (Sub && Sub->GetActiveMessage() && !FocusedInteractable.IsValid())
	{
		// Ignore the same key press that just opened a message. The old guard
		// fell through to an unconditional dismiss, so it never protected it.
		if (Sub->GetActiveMessageAge() > 0.3f)
		{
			Sub->DismissMessage();
		}
		return;
	}
	if (AActor* Target = FocusedInteractable.Get(); IsValid(Target))
	{
		if (IDAInteractableInterface* I = Cast<IDAInteractableInterface>(Target))
		{
			if (I->CanInteract(this))
			{
				// Reach out for doors, counters and machines; talking to people needs no gesture.
				if (Avatar && !Target->IsA<APawn>())
				{
					Avatar->PlayGesture(TEXT("Interact"));
				}
				I->Interact(this);
			}
		}
	}
}

void ADAStudentCharacter::OnMap(const FInputActionValue& V)
{
	// The map's own M/Tab toggle must stay reachable while the map is open, but
	// every other modal (help included) wins first; HUD::ToggleMap re-checks.
	ADAHUD* HUD = GetDAHUD();
	if (!HUD || HUD->IsDuelOpen() || HUD->IsHelpOpen() || HUD->IsDialogueOpen()
		|| HUD->IsPDAOpen() || HUD->IsTitleOpen() || HUD->IsGameplayUIOpen())
	{
		return;
	}
	HUD->ToggleMap();
}

void ADAStudentCharacter::OnJacket(const FInputActionValue& V)
{
	if (!IsWorldInputAllowed())
	{
		return;
	}
	const EDADorm Next = static_cast<EDADorm>((static_cast<uint8>(GetDorm()) + 1) % 4);
	SetDorm(Next);
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		FDAMessage Msg;
		Msg.Title = TEXT("Uniform changed");
		Msg.Body = FString::Printf(TEXT("You are now wearing the %s jacket."), *DuelAcademy::DormName(Next));
		Msg.Accent = DuelAcademy::DormColor(Next);
		Msg.Duration = 3.f;
		Sub->PushMessage(Msg);
		Sub->PlayUISound(TEXT("A_CardDraw"), 0.6f);
	}
}

void ADAStudentCharacter::OnDuelDisk(const FInputActionValue& V)
{
	// The disk stays down on the bike: both hands are on the bars.
	if (!IsWorldInputAllowed() || bRiding)
	{
		return;
	}
	bManualDuelPose = !bManualDuelPose;
}

void ADAStudentCharacter::OnBike(const FInputActionValue& V)
{
	(void)V;
	if (!IsWorldInputAllowed())
	{
		return;
	}
	SetRiding(!bRiding);
}

void ADAStudentCharacter::OnHelp(const FInputActionValue& V)
{
	// F1/H stays togglable while help itself is open (otherwise the overlay
	// could only be closed by Escape), so this handler keeps the movement
	// gate instead of IsWorldInputAllowed(): every real modal still blocks
	// the toggle, help merely does not block its own dismissal.
	(void)V;
	if (IsMovementBlocked())
	{
		return;
	}
	ADAHUD* HUD = GetDAHUD();
	if (HUD)
	{
		HUD->ToggleHelp();
	}
}

void ADAStudentCharacter::OnTimePause(const FInputActionValue& V)
{
	if (!IsWorldInputAllowed())
	{
		return;
	}
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		if (ADAIslandManager* M = Sub->GetManager())
		{
			M->ToggleTimePaused();
		}
	}
}

void ADAStudentCharacter::OnTimeFaster(const FInputActionValue& V)
{
	if (!IsWorldInputAllowed())
	{
		return;
	}
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		if (ADAIslandManager* M = Sub->GetManager())
		{
			M->AdjustTimeSpeed(4.f);
		}
	}
}

void ADAStudentCharacter::OnTimeSlower(const FInputActionValue& V)
{
	if (!IsWorldInputAllowed())
	{
		return;
	}
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		if (ADAIslandManager* M = Sub->GetManager())
		{
			M->AdjustTimeSpeed(0.25f);
		}
	}
}

void ADAStudentCharacter::OnTimeSkip(const FInputActionValue& V)
{
	if (!IsWorldInputAllowed())
	{
		return;
	}

	// Advance the campaign clock, not just the lighting. Periods roll
	// AM -> PM -> Night -> next day, which is what date/weekday gates read.
	UGameInstance* GameInstance = GetWorld() ? GetWorld()->GetGameInstance() : nullptr;
	UDACalendarSubsystem* Calendar = GameInstance ? GameInstance->GetSubsystem<UDACalendarSubsystem>() : nullptr;
	if (!Calendar)
	{
		return;
	}
	Calendar->AdvancePeriod();

	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		if (ADAIslandManager* M = Sub->GetManager())
		{
			M->SetCalendarTime(Calendar->GetAbsoluteDay(), static_cast<float>(Calendar->GetHour()));
		}
	}
}

void ADAStudentCharacter::SetDorm(EDADorm NewDorm)
{
	if (Avatar)
	{
		Avatar->SetDorm(NewDorm);
	}
	if (Bike)
	{
		Bike->SetPaint(DuelAcademy::DormColor(NewDorm));
	}
}

EDADorm ADAStudentCharacter::GetDorm() const
{
	return Avatar ? Avatar->GetDorm() : EDADorm::Slifer;
}

void ADAStudentCharacter::NotifyTeleportArrived()
{
	// Pinned cross-workstream contract #2 (WS-05 calls this from
	// DAInteriorPortal::ApplyArrival): strictly focus-clearing. The
	// dependency view belongs to the departure point, so drop it and reset
	// the focus poll timer so the next UI tick re-acquires at the arrival
	// point. Never teleports, never changes movement or input modes.
	FocusedInteractable.Reset();
	FocusTimer = 0.f;
}

void ADAStudentCharacter::FastTravelTo(ADALocationVolume* Zone)
{
	if (!Zone)
	{
		return;
	}
	if (APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (PC->PlayerCameraManager)
		{
			PC->PlayerCameraManager->StartCameraFade(1.f, 0.f, 1.0f, FLinearColor::Black, false, false);
		}
		PC->SetControlRotation(FRotator(-10.f, Zone->SpawnYaw, 0.f));
	}
	// Fast travel always lands on the island, never in a generated interior cell.
	// A rider arrives still mounted, upright and facing the spawn direction.
	bInInterior = false;
	RideInput = FVector::ZeroVector;
	BikeSteer = BikeLean = BikePitch = BikeYawRate = 0.f;
	bSprinting = false;
	FocusedInteractable.Reset();
	bSwimming = false;
	SwimAlpha = 0.f;
	if (Avatar)
	{
		Avatar->SwimAlpha = 0.f;
	}
	UCharacterMovementComponent* Move = GetCharacterMovement();
	if (Move && (Move->MovementMode == MOVE_Flying || Move->MovementMode == MOVE_Swimming))
	{
		// Do not inherit a stale swim/fly mode from the departure point; the
		// water query can re-enter swimming at the destination next tick.
		Move->SetMovementMode(MOVE_Falling);
	}
	SetActorLocationAndRotation(Zone->SpawnLocation, FRotator(0.f, Zone->SpawnYaw, 0.f), false, nullptr, ETeleportType::TeleportPhysics);
	if (Move)
	{
		Move->Velocity = FVector::ZeroVector;
	}
	// Re-anchor the fall-out-of-world rescue at the destination instead of the
	// place the player left from.
	SafeLocation = GetActorLocation();
	SafeTimer = 0.f;
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		Sub->PlayUISound(TEXT("A_CardDraw"), 0.7f);
	}
}

// ------------------------------------------------------------------------ tick

void ADAStudentCharacter::UpdateFocus()
{
	FocusedInteractable.Reset();
	UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this);
	if (!Sub)
	{
		return;
	}
	const FVector Me = GetActorLocation();
	// The character only faces its last movement direction; the camera (control
	// rotation) is what the player actually aims with when choosing an object.
	const FVector Fwd = Controller
		? FRotationMatrix(FRotator(0.f, Controller->GetControlRotation().Yaw, 0.f)).GetUnitAxis(EAxis::X)
		: GetActorForwardVector();
	float BestScore = TNumericLimits<float>::Max();
	for (const TWeakObjectPtr<AActor>& Weak : Sub->GetInteractables())
	{
		AActor* Actor = Weak.Get();
		if (!IsValid(Actor) || Actor == this || Actor->IsHidden())
		{
			continue;
		}
		const IDAInteractableInterface* I = Cast<IDAInteractableInterface>(Actor);
		if (!I || !I->CanInteract(this))
		{
			continue;
		}
		const FVector To = I->GetInteractLocation() - Me;
		const float Horizontal = FVector(To.X, To.Y, 0.0).Size();
		if (Horizontal > I->GetInteractRadius() || FMath::Abs(To.Z) > 400.f)
		{
			continue;
		}
		const float Facing = FVector::DotProduct(Fwd, FVector(To.X, To.Y, 0.0).GetSafeNormal());
		const float Score = Horizontal * (1.6f - 0.6f * Facing);
		if (Score < BestScore)
		{
			BestScore = Score;
			FocusedInteractable = Actor;
		}
	}
}

void ADAStudentCharacter::UpdateSwimming(float DeltaSeconds)
{
	UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this);
	UCharacterMovementComponent* Move = GetCharacterMovement();
	if (!Move)
	{
		return;
	}
	if (!Sub)
	{
		// Without the world subsystem there is no water query; never leave the
		// character stuck in flying mode or the avatar stuck in its swim pose.
		if (bSwimming)
		{
			bSwimming = false;
			Move->SetMovementMode(MOVE_Falling);
		}
		SwimAlpha = FMath::FInterpTo(SwimAlpha, 0.f, DeltaSeconds, 5.f);
		return;
	}

	// Interior cells sit below the island water plane; do not treat their Z as
	// open water or the character would enter flying/swimming mode indoors.
	if (bInInterior)
	{
		// No riding indoors: the bike is stowed at the door.
		SetRiding(false, true);
		bSwimming = false;
		SwimAlpha = FMath::FInterpTo(SwimAlpha, 0.f, DeltaSeconds, 5.f);
		return;
	}
	const FVector Loc = GetActorLocation();
	const float Half = GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	// The surface under the swimmer right now: the sea and the lake carry real waves (water.json), rivers and
	// ponds are flat and shallow.
	float WaterZ = Sub->GetWaterSurfaceZ(Loc);
	bool bWaves = false;
	bool bShallowBody = false;
	if (const ADAIslandManager* Manager = Sub->GetManager())
	{
		const FDAWaterInfo Water = Manager->QueryWater(Loc, true);
		WaterZ = Water.SurfaceZ;
		bWaves = Water.bWaves;
		bShallowBody = Water.Body == EDAWaterBody::River;
	}
	const float Depth = WaterZ - (Loc.Z - Half);

	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(DAStudentSwim), false, this);
	const bool bGround = GetWorld()->LineTraceSingleByChannel(Hit, Loc, Loc - FVector(0.0, 0.0, Half + 80.0), ECC_Visibility, Params);
	const float GroundDist = bGround ? static_cast<float>(Loc.Z - Hit.ImpactPoint.Z) : 1.0e6f;

	// Rivers are wading water: never deep enough to swim, whatever a carved pool or a cascade step measures.
	if (!bSwimming && !bShallowBody && Depth > 140.f && GroundDist > Half + 30.f)
	{
		bSwimming = true;
		Move->SetMovementMode(MOVE_Flying);
		Move->Velocity *= 0.35f;
	}
	else if (bSwimming && (bShallowBody || GroundDist < Half + 15.f || Depth < 60.f))
	{
		bSwimming = false;
		Move->SetMovementMode(bGround ? MOVE_Walking : MOVE_Falling);
	}

	if (bSwimming)
	{
		// Ride the swell: WaterZ already rises and falls with the waves, so only a small breathing bob is
		// added on top of it (the full 6 cm on still water, where nothing else moves the swimmer).
		const float Bob = (bWaves ? 2.f : 6.f) * FMath::Sin(GetWorld()->GetTimeSeconds() * 2.f);
		const float TargetZ = WaterZ - 48.f + Bob;
		Move->Velocity.Z = FMath::Clamp((TargetZ - Loc.Z) * 3.5f, -250.f, 250.f);
		Move->MaxFlySpeed = SwimSpeed * (bSprinting ? 1.45f : 1.f);
	}
	SwimAlpha = FMath::FInterpTo(SwimAlpha, bSwimming ? 1.f : 0.f, DeltaSeconds, 5.f);
}

void ADAStudentCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UCharacterMovementComponent* Move = GetCharacterMovement();
	if (!Move)
	{
		return;
	}
	// UI input modes can swallow the shift-release event while a map/duel is open.
	// Drop the flag so closing the UI cannot leave the character sprinting.
	if (bSprinting && (IsMovementBlocked() || !Controller))
	{
		bSprinting = false;
	}
	Move->MaxWalkSpeed = bRiding ? (bSprinting ? BikeBoostSpeed : BikeSpeed) : (bSprinting ? SprintSpeed : WalkSpeed);

	UpdateSwimming(DeltaSeconds);
	if (bRiding && bSwimming)
	{
		SetRiding(false, true);
		PushBikeMessage(TEXT("Too deep"), TEXT("The motorcycle can ford shallow water, not the open sea. You swim on."));
	}
	LookIdleTime += DeltaSeconds;
	if (bRiding)
	{
		UpdateRiding(DeltaSeconds);
	}
	RideInput = FVector::ZeroVector;
	if (Avatar)
	{
		Avatar->SwimAlpha = SwimAlpha;
		Avatar->DuelPoseAlpha = FMath::FInterpTo(Avatar->DuelPoseAlpha, (bDuelPose || bManualDuelPose) && !bSwimming && !bRiding ? 1.f : 0.f, DeltaSeconds, 6.f);
	}
	if (FollowCamera)
	{
		// A touch of extra field of view sells the speed on the bike.
		const float GroundSpeed = static_cast<float>(FVector(Move->Velocity.X, Move->Velocity.Y, 0.0).Size());
		const float SpeedFov = bRiding ? 13.f * FMath::Clamp((GroundSpeed - 300.f) / FMath::Max(BikeBoostSpeed - 300.f, 1.f), 0.f, 1.f) : 0.f;
		FollowCamera->SetFieldOfView(FMath::FInterpTo(FollowCamera->FieldOfView, BaseFieldOfView + SpeedFov, DeltaSeconds, 3.f));
	}

	FocusTimer -= DeltaSeconds;
	if (FocusTimer <= 0.f)
	{
		FocusTimer = 0.1f;
		if (IsMovementBlocked())
		{
			// Do not keep (or acquire) a world target behind a menu/dialogue; the
			// HUD draws its prompt without checking the UI state.
			FocusedInteractable.Reset();
		}
		else
		{
			UpdateFocus();
		}
	}

	// Indoors? Probe straight up a few times a second: a ceiling over the head (and over a second point a
	// little behind, so a porch roof or doorway lintel alone doesn't count) means we walked into a building.
	IndoorTimer -= DeltaSeconds;
	if (IndoorTimer <= 0.f && GetWorld())
	{
		IndoorTimer = 0.2f;
		FCollisionQueryParams Q(SCENE_QUERY_STAT(DAIndoorProbe), false, this);
		const FVector Head = GetActorLocation() + FVector(0.0, 0.0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
		const FVector Back = Head - GetControlRotation().Vector().GetSafeNormal2D() * 150.0;
		FHitResult H;
		const bool bA = GetWorld()->LineTraceSingleByChannel(H, Head, Head + FVector(0.0, 0.0, IndoorCeilingCheck), ECC_Camera, Q);
		const bool bB = bA && GetWorld()->LineTraceSingleByChannel(H, Back, Back + FVector(0.0, 0.0, IndoorCeilingCheck), ECC_Camera, Q);
		bIndoors = bA && bB;
	}

	// Camera zoom easing (pulled in indoors, the player's own zoom outside)
	if (CameraBoom)
	{
		const float Want = bIndoors ? FMath::Min(TargetZoom, IndoorZoom) : TargetZoom;
		CameraBoom->TargetArmLength = FMath::FInterpTo(CameraBoom->TargetArmLength, Want, DeltaSeconds, bIndoors ? 5.f : 3.f);
	}

	// Safety net: remember solid ground, rescue the player if they fall out of the world.
	SafeTimer -= DeltaSeconds;
	if (!bInInterior && SafeTimer <= 0.f && Move->IsMovingOnGround())
	{
		SafeTimer = 2.f;
		SafeLocation = GetActorLocation();
	}
	if (!bInInterior && GetActorLocation().Z < -8000.0)
	{
		// The rescue is a full reset: drop any swim/fly state along with the
		// velocity so the character does not hover or stay prone after arriving.
		bSwimming = false;
		SwimAlpha = 0.f;
		if (Avatar)
		{
			Avatar->SwimAlpha = 0.f;
		}
		if (Move->MovementMode == MOVE_Flying || Move->MovementMode == MOVE_Swimming)
		{
			Move->SetMovementMode(MOVE_Falling);
		}
		SetActorLocation(SafeLocation + FVector(0.0, 0.0, 200.0), false, nullptr, ETeleportType::TeleportPhysics);
		Move->Velocity = FVector::ZeroVector;
	}
}

// ------------------------------------------------------------------------ motorcycle

bool ADAStudentCharacter::CanMountFor(bool bWorldInputAllowed, bool bInInterior, bool bSwimming)
{
	return bWorldInputAllowed && !bInInterior && !bSwimming;
}

float ADAStudentCharacter::StepBikeYaw(float CurrentYaw, float DesiredYaw, float TurnRate, float DeltaSeconds)
{
	const float Delta = FMath::FindDeltaAngleDegrees(CurrentYaw, DesiredYaw);
	const float MaxStep = FMath::Max(TurnRate, 0.f) * FMath::Max(DeltaSeconds, 0.f);
	return static_cast<float>(FRotator::NormalizeAxis(CurrentYaw + FMath::Clamp(Delta, -MaxStep, MaxStep)));
}

float ADAStudentCharacter::BikeTurnRateFor(float Speed, float TopSpeed)
{
	return FMath::Lerp(200.f, 95.f, FMath::Clamp(Speed / FMath::Max(TopSpeed, 1.f), 0.f, 1.f));
}

void ADAStudentCharacter::SetDuelPose(bool bOn)
{
	bDuelPose = bOn;
	if (bOn)
	{
		SetRiding(false, true);
	}
}

void ADAStudentCharacter::PushBikeMessage(const TCHAR* Title, const TCHAR* Body) const
{
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		FDAMessage Msg;
		Msg.Title = Title;
		Msg.Body = Body;
		Msg.Accent = DuelAcademy::DormColor(GetDorm());
		Msg.Duration = 2.5f;
		Sub->PushMessage(Msg);
	}
}

void ADAStudentCharacter::ApplyMovementProfile(bool bRide)
{
	UCharacterMovementComponent* Move = GetCharacterMovement();
	if (!Move)
	{
		return;
	}
	// The bike keeps its own heading (UpdateRiding steers it) and coasts instead of stopping dead.
	Move->bOrientRotationToMovement = !bRide;
	Move->MaxAcceleration = bRide ? BikeAcceleration : FootAcceleration;
	Move->BrakingDecelerationWalking = bRide ? 650.f : FootBrakingDeceleration;
	Move->bUseSeparateBrakingFriction = bRide;
	Move->BrakingFriction = bRide ? 0.35f : 0.f;
	Move->MaxStepHeight = bRide ? BikeStepHeight : FootStepHeight;
	Move->SetWalkableFloorAngle(bRide ? BikeWalkableSlope : FootWalkableSlope);
	Move->JumpZVelocity = bRide ? BikeJumpZVelocity : FootJumpZVelocity;
	Move->AirControl = bRide ? 0.1f : FootAirControl;
}

void ADAStudentCharacter::AttachAvatar(bool bToBike)
{
	if (!Avatar)
	{
		return;
	}
	USceneComponent* Mount = (bToBike && Bike) ? Bike->GetRiderMount() : nullptr;
	if (Mount)
	{
		// The rider rides on the bike's lean/pitch/suspension pivot.
		Avatar->AttachToComponent(Mount, FAttachmentTransformRules::KeepRelativeTransform);
		Avatar->SetRelativeLocationAndRotation(FVector::ZeroVector, FRotator(0.f, -90.f, 0.f));
		Avatar->RideHipHeight = Bike->GetRiderHipHeight();
		Avatar->RideAlpha = 1.f;
		FDARiderTargets RiderTargets;
		Bike->GetRiderTargets(RiderTargets);
		Avatar->SetRideTargets(RiderTargets);
	}
	else
	{
		Avatar->AttachToComponent(GetCapsuleComponent(), FAttachmentTransformRules::KeepRelativeTransform);
		Avatar->SetRelativeLocationAndRotation(AvatarOnFoot, FRotator(0.f, -90.f, 0.f));
		Avatar->RideAlpha = 0.f;
	}
}

bool ADAStudentCharacter::SetRiding(bool bRide, bool bQuiet)
{
	if (bRide == bRiding)
	{
		return bRiding;
	}
	UCharacterMovementComponent* Move = GetCharacterMovement();
	if (bRide)
	{
		if (!Bike || !Bike->GetRiderMount() || !Move)
		{
			return false;
		}
		if (!CanMountFor(IsWorldInputAllowed(), bInInterior, bSwimming))
		{
			if (!bQuiet && bInInterior)
			{
				PushBikeMessage(TEXT("No riding indoors"), TEXT("The motorcycle stays outside. Head out to ride."));
			}
			else if (!bQuiet && bSwimming)
			{
				PushBikeMessage(TEXT("Too deep"), TEXT("Get back to shore before you call the motorcycle."));
			}
			return false;
		}
		bRiding = true;
		bManualDuelPose = false;
		RideInput = FVector::ZeroVector;
		BikeSteer = BikeLean = BikePitch = BikeYawRate = 0.f;
		LookIdleTime = 0.f;
		PreRideZoom = TargetZoom;
		TargetZoom = FMath::Clamp(FMath::Max(TargetZoom, 700.f), MinZoom, MaxZoom);
		Bike->SetPaint(DuelAcademy::DormColor(GetDorm()));
		Bike->SetDeployed(true);
		AttachAvatar(true);
		ApplyMovementProfile(true);
	}
	else
	{
		bRiding = false;
		RideInput = FVector::ZeroVector;
		AttachAvatar(false);
		if (Bike)
		{
			Bike->SetDeployed(false);
		}
		ApplyMovementProfile(false);
		TargetZoom = FMath::Clamp(PreRideZoom, MinZoom, MaxZoom);
		if (Move)
		{
			// Hop off at a run, not at bike speed.
			const FVector Horizontal = FVector(Move->Velocity.X, Move->Velocity.Y, 0.0).GetClampedToMaxSize(SprintSpeed);
			Move->Velocity = FVector(Horizontal.X, Horizontal.Y, Move->Velocity.Z);
		}
	}
	if (!bQuiet)
	{
		if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
		{
			Sub->PlayUISound(bRide ? TEXT("A_DuelStart") : TEXT("A_CardDraw"), bRide ? 0.45f : 0.6f);
		}
	}
	return bRiding;
}

void ADAStudentCharacter::UpdateRiding(float DeltaSeconds)
{
	UCharacterMovementComponent* Move = GetCharacterMovement();
	if (!Move || !Bike || DeltaSeconds <= 0.f)
	{
		return;
	}
	FVector Wish(RideInput.X, RideInput.Y, 0.0);
	if (IsMovementBlocked())
	{
		Wish = FVector::ZeroVector;
	}
	const float Throttle = FMath::Min(static_cast<float>(Wish.Size()), 1.f);
	const FVector HVel(Move->Velocity.X, Move->Velocity.Y, 0.0);
	const float Speed = static_cast<float>(HVel.Size());
	const bool bGround = Move->IsMovingOnGround();
	const float OldYaw = static_cast<float>(GetActorRotation().Yaw);

	// Steering: the stick / WASD names a camera-relative direction and the bike
	// carves towards it at a speed-dependent turn rate. Asking for the opposite
	// direction at speed brakes first, then turns round.
	float Yaw = OldYaw;
	float SteerTarget = 0.f;
	bool bBraking = false;
	if (Throttle > 0.1f)
	{
		const float DesiredYaw = static_cast<float>(Wish.Rotation().Yaw);
		const float Delta = FMath::FindDeltaAngleDegrees(OldYaw, DesiredYaw);
		const float Along = static_cast<float>(FVector::DotProduct(HVel, FRotator(0.f, OldYaw, 0.f).Vector()));
		bBraking = FMath::Abs(Delta) > 115.f && Along > 450.f;
		const float Rate = BikeTurnRateFor(Speed, BikeSpeed) * (bGround ? 1.f : 0.3f);
		Yaw = StepBikeYaw(OldYaw, DesiredYaw, Rate, DeltaSeconds);
		SteerTarget = FMath::Clamp(Delta / 35.f, -1.f, 1.f);
		if (!bBraking)
		{
			AddMovementInput(FRotator(0.f, Yaw, 0.f).Vector(), Throttle);
		}
	}
	const FVector Heading = FRotator(0.f, Yaw, 0.f).Vector();
	if (bGround)
	{
		FVector NewH = HVel;
		if (bBraking)
		{
			NewH = NewH.GetClampedToMaxSize(FMath::Max(0.f, Speed - BikeBrakeDeceleration * DeltaSeconds));
		}
		// Tyre grip: the bike rolls where it points; sideways slip bleeds off quickly.
		const double Along = FVector::DotProduct(NewH, Heading);
		NewH = FMath::VInterpTo(NewH, Heading * Along, DeltaSeconds, 9.f);
		Move->Velocity.X = NewH.X;
		Move->Velocity.Y = NewH.Y;
	}
	SetActorRotation(FRotator(0.f, Yaw, 0.f));

	// Lean into turns from the lateral acceleration (v * yaw rate), upright in the air.
	BikeYawRate = FMath::FInterpTo(BikeYawRate, FMath::FindDeltaAngleDegrees(OldYaw, Yaw) / DeltaSeconds, DeltaSeconds, 10.f);
	const float ForwardSpeed = static_cast<float>(FVector::DotProduct(FVector(Move->Velocity.X, Move->Velocity.Y, 0.0), Heading));
	const float Lateral = ForwardSpeed * FMath::DegreesToRadians(BikeYawRate);
	const float LeanTarget = bGround ? FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan2(Lateral, 980.f)), -40.f, 40.f) : 0.f;
	BikeLean = FMath::FInterpTo(BikeLean, LeanTarget, DeltaSeconds, 6.f);

	// Pitch with the ground under the wheels, or with the flight path while airborne.
	float PitchTarget = 0.f;
	if (bGround && Move->CurrentFloor.IsWalkableFloor())
	{
		const FVector N = Move->CurrentFloor.HitResult.ImpactNormal;
		PitchTarget = FMath::RadiansToDegrees(FMath::Atan2(static_cast<float>(-FVector::DotProduct(N, Heading)), static_cast<float>(N.Z)));
	}
	else if (!bGround)
	{
		PitchTarget = 0.5f * FMath::RadiansToDegrees(FMath::Atan2(static_cast<float>(Move->Velocity.Z), FMath::Max(Speed, 300.f)));
	}
	BikePitch = FMath::FInterpTo(BikePitch, FMath::Clamp(PitchTarget, -35.f, 35.f), DeltaSeconds, bGround ? 10.f : 3.f);
	const float SteerScale = FMath::Lerp(1.f, 0.3f, FMath::Clamp(Speed / FMath::Max(BikeSpeed, 1.f), 0.f, 1.f));
	BikeSteer = FMath::FInterpTo(BikeSteer, SteerTarget * SteerScale, DeltaSeconds, 8.f);

	FDABikePose Pose;
	Pose.ForwardSpeed = ForwardSpeed;
	Pose.Steer = BikeSteer;
	Pose.Lean = BikeLean;
	Pose.Pitch = BikePitch;
	Pose.Throttle = Throttle;
	Pose.bBraking = bBraking;
	Pose.bBoosting = bSprinting && Throttle > 0.1f;
	Pose.bAirborne = !bGround;
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		if (const ADAIslandManager* M = Sub->GetManager())
		{
			Pose.NightAlpha = M->IsNight() ? 1.f : 0.f;
		}
	}
	Bike->UpdateRide(DeltaSeconds, Pose);
	if (Avatar)
	{
		// Where the seat, grips and pegs are this frame and how to sit: the avatar IKs the rider onto them.
		FDARiderTargets RiderTargets;
		Bike->GetRiderTargets(RiderTargets);
		Avatar->SetRideTargets(RiderTargets);
	}

	// Chase camera: after a moment without look input, swing in behind the bike.
	if (Controller && LookIdleTime > 1.5f && Speed > 400.f && !IsMovementBlocked())
	{
		const FRotator Ctrl = Controller->GetControlRotation();
		const float Follow = FMath::Min(1.f, 1.2f * DeltaSeconds);
		const float NewYaw = static_cast<float>(Ctrl.Yaw) + FMath::FindDeltaAngleDegrees(static_cast<float>(Ctrl.Yaw), Yaw) * Follow;
		Controller->SetControlRotation(FRotator(Ctrl.Pitch, NewYaw, Ctrl.Roll));
	}
}

void ADAStudentCharacter::SetInInterior(bool bNewInInterior)
{
	const bool bWasInInterior = bInInterior;
	bInInterior = bNewInInterior;
	if (bWasInInterior && !bInInterior)
	{
		// Leaving a cell re-anchors the fall rescue at the arrival point.
		SafeLocation = GetActorLocation();
		SafeTimer = 0.f;
	}
	if (bInInterior)
	{
		bSwimming = false;
		// Interior cells sit below the water plane; snap the prone swim pose off
		// instead of letting it fade out inside the cell.
		SwimAlpha = 0.f;
		if (Avatar)
		{
			Avatar->SwimAlpha = 0.f;
		}
		if (UCharacterMovementComponent* Move = GetCharacterMovement())
		{
			if (Move->MovementMode == MOVE_Flying || Move->MovementMode == MOVE_Swimming)
			{
				Move->SetMovementMode(MOVE_Walking);
			}
			Move->Velocity = FVector::ZeroVector;
		}
	}
}
