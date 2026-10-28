// Duel Academy Island - anything the player can press Interact on.

#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "DAInteractableInterface.generated.h"

class ADAStudentCharacter;

UINTERFACE(MinimalAPI, meta = (CannotImplementInterfaceInBlueprint))
class UDAInteractableInterface : public UInterface
{
	GENERATED_BODY()
};

class DUELACADEMYISLAND_API IDAInteractableInterface
{
	GENERATED_BODY()

public:
	/** Verb shown in the prompt, e.g. "Read", "Talk", "Start duel". */
	virtual FString GetInteractPrompt() const = 0;

	/** Short name shown next to the prompt. */
	virtual FString GetInteractName() const = 0;

	/** Where the interaction "lives" (for distance checks). */
	virtual FVector GetInteractLocation() const = 0;

	/** Maximum interaction distance in cm. */
	virtual float GetInteractRadius() const { return 300.f; }

	virtual bool CanInteract(const ADAStudentCharacter* By) const { return true; }

	virtual void Interact(ADAStudentCharacter* By) = 0;
};
