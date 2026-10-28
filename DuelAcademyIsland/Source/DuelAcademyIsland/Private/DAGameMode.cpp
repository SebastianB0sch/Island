// Duel Academy Island - game mode.

#include "DAGameMode.h"

#include "DAHUD.h"
#include "DAStudentCharacter.h"
#include "GameFramework/PlayerController.h"

ADAGameMode::ADAGameMode()
{
	DefaultPawnClass = ADAStudentCharacter::StaticClass();
	HUDClass = ADAHUD::StaticClass();
	PlayerControllerClass = APlayerController::StaticClass();
}
