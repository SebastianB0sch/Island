// Duel Academy Island - player response window self-test (see the .cpp).

#pragma once

#include "CoreMinimal.h"

class UCardDatabaseSubsystem;

namespace DADuelResponseSelfTest
{
	/** Runs the scripted response-window / player-target duels; Check(bPassed, Name) records each result. */
	DUELACADEMYISLAND_API void Run(UCardDatabaseSubsystem* Database, TFunctionRef<void(bool, const FString&)> Check);
}
