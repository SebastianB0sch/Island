#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "DACardArtSubsystem.generated.h"

class UTexture2D;

/**
 * Loads the card scans that ship alongside the JSON card database.  The files
 * live outside /Game on purpose: they are ordinary JPGs under Content/Data so
 * the art can be refreshed with Tools/fetch_card_art.py without reimporting
 * assets.  Textures are created on first use and cached for the session.
 *
 * A missing or invalid scan is cached as null so draw code does not repeat the
 * file lookup every frame; restart the session after adding art.  Card ids are
 * integers, so the path has no user-controlled directory components.
 */
UCLASS()
class DUELACADEMYISLAND_API UCardArtSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;

	/** Full card scan for a GBA card id, or null when the file is missing. */
	UTexture2D* GetCardArt(int32 CardId);

	/** Generic face-down card back. */
	UTexture2D* GetCardBack();

	bool HasCardArt(int32 CardId) const;
	FString GetArtDirectory() const { return ArtDirectory; }

private:
	UTexture2D* LoadTexture(const FString& Path);
	FString CardArtPath(int32 CardId) const;

	UPROPERTY(Transient)
	TMap<int32, TObjectPtr<UTexture2D>> ArtCache;

	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> CardBack = nullptr;

	FString ArtDirectory;
	bool bBackLoadAttempted = false;
};
