// Duel Academy Island - A02 Gate 3 scale tests (subsystem bootstrap).
#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DAA02GateTests.generated.h"

UCLASS()
class DUELACADEMYISLAND_API UDAA02GateTestSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

private:
	bool Tick(float DeltaSeconds);

	FTSTicker::FDelegateHandle TickerHandle;
	bool bRunFuzz = false;
	bool bRunTwelveMonth = false;
	int32 FuzzCount = 0;
	int32 FuzzSeed = 0;
};
