#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DACharacterPortraitSubsystem.generated.h"

class UTexture2D;

/**
 * Runtime loader for the character portraits shown in dialogue, duel
 * scoreboards and the result screen. The PNGs live under Content/Data so they
 * can be replaced without reimporting assets.
 */
UCLASS()
class DUELACADEMYISLAND_API UCharacterPortraitSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	/** Bust/face portrait for scoreboards and dialogue, keyed by character id. */
	UTexture2D* GetPortrait(const FString& CharacterId, bool bFaceCrop = true);

	/** Expression frame for key-event cut-ins (neutral, happy, angry, ...). */
	UTexture2D* GetExpression(const FString& CharacterId, const FString& Expression);

	bool HasPortrait(const FString& CharacterId) const;
	bool HasExpression(const FString& CharacterId, const FString& Expression) const;
	FString GetPortraitDirectory() const { return PortraitDirectory; }

private:
	UTexture2D* LoadTexture(const FString& Path);
	FString PortraitPath(const FString& CharacterId, bool bFaceCrop) const;
	FString ExpressionPath(const FString& CharacterId, const FString& Expression) const;

	UPROPERTY(Transient)
	TMap<FString, TObjectPtr<UTexture2D>> PortraitCache;

	UPROPERTY(Transient)
	TMap<FString, TObjectPtr<UTexture2D>> FaceCache;

	UPROPERTY(Transient)
	TMap<FString, TObjectPtr<UTexture2D>> ExpressionCache;

	FString PortraitDirectory;
};
