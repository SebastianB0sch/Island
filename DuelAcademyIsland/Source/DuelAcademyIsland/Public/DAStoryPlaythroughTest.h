// Duel Academy Island - in-engine story playthrough harness.
//
// -DAStoryPlaythroughTest boots the normal game instance, waits for the story
// data, then runs UDAStorySubsystem::RunStoryPlaythroughTest(). The harness
// starts from a fresh profile, plays the opening, advances A02's calendar for
// 365 days, and starts/drives every E02-E33 event through the real scene queue.
// da.StoryPlaythroughTest runs the same suite on demand.

#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DAStoryPlaythroughTest.generated.h"

UCLASS()
class DUELACADEMYISLAND_API UDAStoryPlaythroughTestSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

private:
	bool Tick(float DeltaTime);

	FTSTicker::FDelegateHandle TickerHandle;
	bool bFinished = false;
	float WaitSeconds = 0.f;
};
