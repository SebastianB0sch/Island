// Duel Academy Island - profile self-test subsystem bootstrap.
#pragma once

#include "CoreMinimal.h"
#include "Containers/Ticker.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DAProfileSelfTestSubsystem.generated.h"

UCLASS()
class DUELACADEMYISLAND_API UDAProfileSelfTestSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

private:
	bool Tick(float DeltaSeconds);

	FTSTicker::FDelegateHandle TickerHandle;
};
