// Duel Academy Island - developer harness for the motorcycle's look and engine audio.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DABikeTestSubsystem.generated.h"

/**
 * `-DABikeTest` summons the student's motorcycle in the plaza, parks a
 * three-quarter camera around it and saves six screenshots (DABikeA..F).
 * It also logs the drivetrain state and whether the procedural engine synth
 * is playing, then exits. Development-only, like the other -DA* harnesses.
 */
UCLASS()
class DUELACADEMYISLAND_API UDABikeTestSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

private:
	bool Tick(float DeltaSeconds);
	void TakeShot(const TCHAR* FileName);
	void AimCamera(float Yaw, float Pitch, float BoomLength);

	bool bEnabled = false;
	int32 Step = 0;
	float StartTime = 0.f;
	FTSTicker::FDelegateHandle TickerHandle;
};
