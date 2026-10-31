// Duel Academy Island - 12-cycle exam lifecycle self-test.

#pragma once

#include "CoreMinimal.h"
#include "DAPuzzleSelfTest.h"

class UCardDatabaseSubsystem;

class DUELACADEMYISLAND_API FDAExamSelfTest
{
public:
	/**
	 * Runs months 1-12 through a transient UDAExamSubsystem: perfect written
	 * score, actual timed-puzzle solve, all practical objectives, a failing
	 * written mix, retry and next-cycle resets.  No UI or profile mutation.
	 */
	static FDASelfTestReport Run(UCardDatabaseSubsystem* Database);
};
