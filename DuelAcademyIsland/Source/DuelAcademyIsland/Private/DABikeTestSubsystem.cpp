// Duel Academy Island - developer harness for the motorcycle's look and engine audio.

#include "DABikeTestSubsystem.h"

#include "DAEngineSynthComponent.h"
#include "DAHUD.h"
#include "DAMotorcycleComponent.h"
#include "DAMovementAudioComponent.h"
#include "DAStudentCharacter.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

void UDABikeTestSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	if (FParse::Param(FCommandLine::Get(), TEXT("DABikeAudioTest")))
	{
		FString Summary;
		const FString WavPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("BikeAudioTest.wav"));
		const bool bPassed = UDAEngineSynthComponent::RenderOfflineTest(WavPath, Summary);
		UE_LOG(LogTemp, Log, TEXT("DABikeAudioTest: %s | %s"), bPassed ? TEXT("PASS") : TEXT("FAIL"), *Summary);
		FPlatformMisc::RequestExitWithStatus(false, bPassed ? 0 : 1, TEXT("DABikeAudioTest"));
		return;
	}

	if (FParse::Param(FCommandLine::Get(), TEXT("DAMovementAudioTest")))
	{
		FString Summary;
		const FString WavPath = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("MovementAudioTest.wav"));
		const bool bPassed = UDAMovementAudioComponent::RenderOfflineTest(WavPath, Summary);
		UE_LOG(LogTemp, Log, TEXT("DAMovementAudioTest: %s | %s"), bPassed ? TEXT("PASS") : TEXT("FAIL"), *Summary);
		FPlatformMisc::RequestExitWithStatus(false, bPassed ? 0 : 1, TEXT("DAMovementAudioTest"));
		return;
	}

	bEnabled = FParse::Param(FCommandLine::Get(), TEXT("DABikeTest"));
	if (bEnabled)
	{
		TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateUObject(this, &UDABikeTestSubsystem::Tick), 0.2f);
	}
}

void UDABikeTestSubsystem::Deinitialize()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}
	Super::Deinitialize();
}

void UDABikeTestSubsystem::TakeShot(const TCHAR* FileName)
{
	FScreenshotRequest::RequestScreenshot(FileName, false, false);
}

void UDABikeTestSubsystem::AimCamera(float Yaw, float Pitch, float BoomLength)
{
	UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
	APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
	ADAStudentCharacter* Char = PC ? Cast<ADAStudentCharacter>(PC->GetPawn()) : nullptr;
	if (!PC || !Char)
	{
		return;
	}
	PC->SetControlRotation(FRotator(Pitch, Yaw, 0.0f));
	if (USpringArmComponent* Boom = Char->FindComponentByClass<USpringArmComponent>())
	{
		Boom->TargetArmLength = BoomLength;
		Boom->SocketOffset = FVector(0.0, 0.0, 55.0);
		Boom->bDoCollisionTest = false;
	}
}

bool UDABikeTestSubsystem::Tick(float DeltaSeconds)
{
	(void)DeltaSeconds;

	UWorld* World = GetGameInstance() ? GetGameInstance()->GetWorld() : nullptr;
	APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
	ADAHUD* HUD = PC ? Cast<ADAHUD>(PC->GetHUD()) : nullptr;
	ADAStudentCharacter* Char = PC ? Cast<ADAStudentCharacter>(PC->GetPawn()) : nullptr;
	if (!World || !PC || !HUD || !Char)
	{
		return true;
	}

	if (Step == 0)
	{
		HUD->CloseTitle();
		Char->SetActorLocation(FVector(0.0f, 4000.0f, 3700.0f), false, nullptr, ETeleportType::TeleportPhysics);
		Char->SetActorRotation(FRotator::ZeroRotator);
		Char->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
		Char->GetCharacterMovement()->Velocity = FVector::ZeroVector;
		Char->SetRiding(true, true);
		StartTime = World->GetTimeSeconds();
		Step = 1;
		UE_LOG(LogTemp, Log, TEXT("DABikeTest: summoned the motorcycle."));
		return true;
	}

	const float Elapsed = World->GetTimeSeconds() - StartTime;
	if (Step == 1 && Elapsed > 1.0f)
	{
		AimCamera(90.0f, -8.0f, 520.0f);
		TakeShot(TEXT("DABikeA.png"));
		Step = 2;
	}
	else if (Step == 2 && Elapsed > 2.0f)
	{
		AimCamera(150.0f, -10.0f, 460.0f);
		TakeShot(TEXT("DABikeB.png"));
		Step = 3;
	}
	else if (Step == 3 && Elapsed > 3.0f)
	{
		AimCamera(20.0f, -10.0f, 520.0f);
		TakeShot(TEXT("DABikeC.png"));
		Step = 4;
	}
	else if (Step == 4 && Elapsed > 4.0f)
	{
		AimCamera(90.0f, -5.0f, 300.0f);
		TakeShot(TEXT("DABikeD.png"));
		Step = 5;
	}
	else if (Step == 5 && Elapsed > 5.0f)
	{
		AimCamera(-90.0f, -8.0f, 520.0f);
		TakeShot(TEXT("DABikeE.png"));
		Step = 6;
	}
	else if (Step == 6 && Elapsed > 6.0f)
	{
		AimCamera(150.0f, -4.0f, 260.0f);
		TakeShot(TEXT("DABikeF.png"));
		Step = 7;
	}
	else if (Step == 7 && Elapsed > 7.0f)
	{
		// Remount after the stop fade: this re-creates the synth generator and
		// checks that a stale stop event can never keep the engine dead.
		Char->SetRiding(false, true);
		StartTime = World->GetTimeSeconds();
		Step = 8;
	}
	else if (Step == 8 && Elapsed > 0.8f)
	{
		Char->SetRiding(true, true);
		StartTime = World->GetTimeSeconds();
		Step = 9;
	}
	else if (Step == 9 && Elapsed > 1.2f)
	{
		UDAMotorcycleComponent* Bike = Char->FindComponentByClass<UDAMotorcycleComponent>();
		UDAEngineSynthComponent* Audio = Char->FindComponentByClass<UDAEngineSynthComponent>();
		const bool bOk = Bike && Bike->IsDeployed() && Bike->GetEngineRPM() > 0.f && Audio && Audio->IsPlaying();
		UE_LOG(LogTemp, Log, TEXT("DABikeTest: %s rpm=%.0f gear=%d deployed=%d audioPlaying=%d (remount)"),
			bOk ? TEXT("PASS") : TEXT("FAIL"),
			Bike ? Bike->GetEngineRPM() : -1.0f,
			Bike ? Bike->GetGear() : -1,
			Bike ? Bike->IsDeployed() : 0,
			Audio ? Audio->IsPlaying() : 0);
		FPlatformMisc::RequestExitWithStatus(false, bOk ? 0 : 1, TEXT("DABikeTest"));
		Step = 10;
	}
	return true;
}
