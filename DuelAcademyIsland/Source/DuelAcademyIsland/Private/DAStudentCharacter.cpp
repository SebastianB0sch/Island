// Duel Academy Island - the playable student.

#include "DAStudentCharacter.h"

#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "DAAvatarComponent.h"
#include "DAHUD.h"
#include "DAInteractableInterface.h"
#include "DAIslandManager.h"
#include "DAIslandSubsystem.h"
#include "DALocationVolume.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputAction.h"
#include "InputMappingContext.h"

ADAStudentCharacter::ADAStudentCharacter()
{
	PrimaryActorTick.bCanEverTick = true;

	GetCapsuleComponent()->InitCapsuleSize(38.f, 92.f);

	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;

	UCharacterMovementComponent* Move = GetCharacterMovement();
	Move->bOrientRotationToMovement = true;
	Move->RotationRate = FRotator(0.f, 600.f, 0.f);
	Move->MaxWalkSpeed = WalkSpeed;
	Move->MinAnalogWalkSpeed = 40.f;
	Move->JumpZVelocity = 560.f;
	Move->AirControl = 0.4f;
	Move->BrakingDecelerationWalking = 2200.f;
	Move->BrakingDecelerationFalling = 600.f;
	Move->MaxStepHeight = 45.f;
	Move->SetWalkableFloorAngle(46.f);
	Move->MaxFlySpeed = SwimSpeed;
	Move->BrakingDecelerationFlying = 1400.f;
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
	FollowCamera->SetFieldOfView(75.f);

	Avatar = CreateDefaultSubobject<UDAAvatarComponent>(TEXT("Avatar"));
	Avatar->SetupAttachment(GetCapsuleComponent());
	Avatar->SetRelativeLocation(FVector(0.0, 0.0, -92.0));

	// No skeletal mesh: the avatar component draws the student.
	GetMesh()->SetVisibility(false);
	GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void ADAStudentCharacter::BeginPlay()
{
	Super::BeginPlay();
	CreateInput();
	AddMappingContext();
	SafeLocation = GetActorLocation();
}

void ADAStudentCharacter::PawnClientRestart()
{
	Super::PawnClientRestart();
	CreateInput();
	AddMappingContext();
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

	UInputAction* Up = MakeAction(TEXT("MenuUp"), VT::Boolean);
	Map(Up, EKeys::Up);
	Map(Up, EKeys::Gamepad_DPad_Up);
	UInputAction* Down = MakeAction(TEXT("MenuDown"), VT::Boolean);
	Map(Down, EKeys::Down);
	Map(Down, EKeys::Gamepad_DPad_Down);
	UInputAction* Select = MakeAction(TEXT("MenuSelect"), VT::Boolean);
	Map(Select, EKeys::Enter);
	Map(Select, EKeys::Gamepad_FaceButton_Right);
	Map(MakeAction(TEXT("Click"), VT::Boolean), EKeys::LeftMouseButton);

	Map(MakeAction(TEXT("Jacket"), VT::Boolean), EKeys::J);
	Map(MakeAction(TEXT("DuelDisk"), VT::Boolean), EKeys::F);
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
	EIC->BindAction(A(TEXT("MenuUp")), ETriggerEvent::Started, this, &ThisClass::OnMenuUp);
	EIC->BindAction(A(TEXT("MenuDown")), ETriggerEvent::Started, this, &ThisClass::OnMenuDown);
	EIC->BindAction(A(TEXT("MenuSelect")), ETriggerEvent::Started, this, &ThisClass::OnMenuSelect);
	EIC->BindAction(A(TEXT("Click")), ETriggerEvent::Started, this, &ThisClass::OnClick);
	EIC->BindAction(A(TEXT("Jacket")), ETriggerEvent::Started, this, &ThisClass::OnJacket);
	EIC->BindAction(A(TEXT("DuelDisk")), ETriggerEvent::Started, this, &ThisClass::OnDuelDisk);
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

// ------------------------------------------------------------------------ movement / camera

void ADAStudentCharacter::MoveInput(float Forward, float Right)
{
	if (!Controller)
	{
		return;
	}
	if (const ADAHUD* HUD = GetDAHUD())
	{
		if (HUD->IsMapOpen())
		{
			return;
		}
	}
	const FRotator YawRot(0.f, Controller->GetControlRotation().Yaw, 0.f);
	const FRotationMatrix M(YawRot);
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
	if (const ADAHUD* HUD = GetDAHUD())
	{
		if (HUD->IsMapOpen())
		{
			return;
		}
	}
	const FVector2D Axis = V.Get<FVector2D>();
	AddControllerYawInput(Axis.X);
	AddControllerPitchInput(-Axis.Y);
}

void ADAStudentCharacter::OnLookStick(const FInputActionValue& V)
{
	const FVector2D Axis = V.Get<FVector2D>();
	const float Dt = GetWorld() ? GetWorld()->GetDeltaSeconds() : 0.016f;
	AddControllerYawInput(Axis.X * 140.f * Dt);
	AddControllerPitchInput(-Axis.Y * 100.f * Dt);
}

void ADAStudentCharacter::OnZoom(const FInputActionValue& V)
{
	TargetZoom = FMath::Clamp(TargetZoom - V.Get<float>() * 70.f, MinZoom, MaxZoom);
}

void ADAStudentCharacter::OnJump(const FInputActionValue& V)
{
	if (!bSwimming)
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
	bSprinting = true;
}

void ADAStudentCharacter::OnSprintStop(const FInputActionValue& V)
{
	bSprinting = false;
}

// ------------------------------------------------------------------------ interaction / UI

void ADAStudentCharacter::OnInteract(const FInputActionValue& V)
{
	UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this);
	if (Sub && Sub->GetActiveMessage() && Sub->GetActiveMessageAge() > 0.3f && !FocusedInteractable.IsValid())
	{
		Sub->DismissMessage();
		return;
	}
	if (AActor* Target = FocusedInteractable.Get())
	{
		if (IDAInteractableInterface* I = Cast<IDAInteractableInterface>(Target))
		{
			if (I->CanInteract(this))
			{
				I->Interact(this);
			}
		}
	}
	else if (Sub && Sub->GetActiveMessage())
	{
		Sub->DismissMessage();
	}
}

void ADAStudentCharacter::OnMap(const FInputActionValue& V)
{
	if (ADAHUD* HUD = GetDAHUD())
	{
		HUD->ToggleMap();
	}
}

void ADAStudentCharacter::OnMenuUp(const FInputActionValue& V)
{
	if (ADAHUD* HUD = GetDAHUD())
	{
		HUD->MoveMapSelection(-1);
	}
}

void ADAStudentCharacter::OnMenuDown(const FInputActionValue& V)
{
	if (ADAHUD* HUD = GetDAHUD())
	{
		HUD->MoveMapSelection(1);
	}
}

void ADAStudentCharacter::OnMenuSelect(const FInputActionValue& V)
{
	if (ADAHUD* HUD = GetDAHUD())
	{
		if (HUD->IsMapOpen())
		{
			if (ADALocationVolume* Zone = HUD->GetSelectedZone())
			{
				HUD->ToggleMap();
				FastTravelTo(Zone);
			}
		}
	}
}

void ADAStudentCharacter::OnClick(const FInputActionValue& V)
{
	if (ADAHUD* HUD = GetDAHUD())
	{
		if (HUD->IsMapOpen())
		{
			if (ADALocationVolume* Zone = HUD->PickZoneUnderCursor())
			{
				HUD->ToggleMap();
				FastTravelTo(Zone);
			}
		}
	}
}

void ADAStudentCharacter::OnJacket(const FInputActionValue& V)
{
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
	bManualDuelPose = !bManualDuelPose;
}

void ADAStudentCharacter::OnHelp(const FInputActionValue& V)
{
	if (ADAHUD* HUD = GetDAHUD())
	{
		HUD->ToggleHelp();
	}
}

void ADAStudentCharacter::OnTimePause(const FInputActionValue& V)
{
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
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		if (ADAIslandManager* M = Sub->GetManager())
		{
			M->SetHour(M->Hour + 3.f);
		}
	}
}

void ADAStudentCharacter::SetDorm(EDADorm NewDorm)
{
	if (Avatar)
	{
		Avatar->SetDorm(NewDorm);
	}
}

EDADorm ADAStudentCharacter::GetDorm() const
{
	return Avatar ? Avatar->GetDorm() : EDADorm::Slifer;
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
	if (bSwimming)
	{
		bSwimming = false;
		GetCharacterMovement()->SetMovementMode(MOVE_Falling);
	}
	SetActorLocationAndRotation(Zone->SpawnLocation, FRotator(0.f, Zone->SpawnYaw, 0.f), false, nullptr, ETeleportType::TeleportPhysics);
	GetCharacterMovement()->Velocity = FVector::ZeroVector;
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
	const FVector Fwd = GetActorForwardVector();
	float BestScore = TNumericLimits<float>::Max();
	for (const TWeakObjectPtr<AActor>& Weak : Sub->GetInteractables())
	{
		AActor* Actor = Weak.Get();
		if (!Actor || Actor == this)
		{
			continue;
		}
		const IDAInteractableInterface* I = Cast<IDAInteractableInterface>(Actor);
		if (!I)
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
	if (!Sub || !Move)
	{
		return;
	}
	const FVector Loc = GetActorLocation();
	const float Half = GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	const float WaterZ = Sub->GetWaterSurfaceZ(Loc);
	const float Depth = WaterZ - (Loc.Z - Half);

	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(DAStudentSwim), false, this);
	const bool bGround = GetWorld()->LineTraceSingleByChannel(Hit, Loc, Loc - FVector(0.0, 0.0, Half + 80.0), ECC_Visibility, Params);
	const float GroundDist = bGround ? static_cast<float>(Loc.Z - Hit.ImpactPoint.Z) : 1.0e6f;

	if (!bSwimming && Depth > 140.f && GroundDist > Half + 30.f)
	{
		bSwimming = true;
		Move->SetMovementMode(MOVE_Flying);
		Move->Velocity *= 0.35f;
	}
	else if (bSwimming && (GroundDist < Half + 15.f || Depth < 60.f))
	{
		bSwimming = false;
		Move->SetMovementMode(bGround ? MOVE_Walking : MOVE_Falling);
	}

	if (bSwimming)
	{
		const float TargetZ = WaterZ - 48.f + 6.f * FMath::Sin(GetWorld()->GetTimeSeconds() * 2.f);
		Move->Velocity.Z = FMath::Clamp((TargetZ - Loc.Z) * 3.5f, -250.f, 250.f);
		Move->MaxFlySpeed = SwimSpeed * (bSprinting ? 1.45f : 1.f);
	}
	SwimAlpha = FMath::FInterpTo(SwimAlpha, bSwimming ? 1.f : 0.f, DeltaSeconds, 5.f);
}

void ADAStudentCharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UCharacterMovementComponent* Move = GetCharacterMovement();
	Move->MaxWalkSpeed = bSprinting ? SprintSpeed : WalkSpeed;

	UpdateSwimming(DeltaSeconds);
	if (Avatar)
	{
		Avatar->SwimAlpha = SwimAlpha;
		Avatar->DuelPoseAlpha = FMath::FInterpTo(Avatar->DuelPoseAlpha, (bDuelPose || bManualDuelPose) && !bSwimming ? 1.f : 0.f, DeltaSeconds, 6.f);
	}

	FocusTimer -= DeltaSeconds;
	if (FocusTimer <= 0.f)
	{
		FocusTimer = 0.1f;
		UpdateFocus();
	}

	// Camera zoom easing
	if (CameraBoom)
	{
		CameraBoom->TargetArmLength = FMath::FInterpTo(CameraBoom->TargetArmLength, TargetZoom, DeltaSeconds, 6.f);
	}

	// Safety net: remember solid ground, rescue the player if they fall out of the world.
	SafeTimer -= DeltaSeconds;
	if (SafeTimer <= 0.f && Move->IsMovingOnGround())
	{
		SafeTimer = 2.f;
		SafeLocation = GetActorLocation();
	}
	if (GetActorLocation().Z < -8000.0)
	{
		SetActorLocation(SafeLocation + FVector(0.0, 0.0, 200.0), false, nullptr, ETeleportType::TeleportPhysics);
		Move->Velocity = FVector::ZeroVector;
	}
}
