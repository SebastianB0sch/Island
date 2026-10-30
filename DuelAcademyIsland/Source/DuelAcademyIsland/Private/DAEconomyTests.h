#pragma once

#include "CoreMinimal.h"

class UCardDatabaseSubsystem;
class UDAInventorySubsystem;
class UDADeckLogic;
class UDAShopSubsystem;

namespace DAEconomyTests
{
	/** Runs the -DAEconomySelfTest suite and returns the log report. */
	FString Run(
		UDAInventorySubsystem* Inventory,
		UDAShopSubsystem* Shop,
		UDADeckLogic* DeckLogic,
		UCardDatabaseSubsystem* Database);
}
