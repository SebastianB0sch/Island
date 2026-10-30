#include "DACardArtSubsystem.h"

#include "DuelAcademyIsland.h"
#include "Engine/Texture2D.h"
#include "ImageUtils.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

void UCardArtSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	ArtDirectory = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/CardArt"));
}

FString UCardArtSubsystem::CardArtPath(int32 CardId) const
{
	return FPaths::Combine(ArtDirectory, FString::Printf(TEXT("%d.jpg"), CardId));
}

UTexture2D* UCardArtSubsystem::LoadTexture(const FString& Path)
{
	if (!FPaths::FileExists(Path))
	{
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Card art missing: %s"), *Path);
		return nullptr;
	}

	UTexture2D* Texture = FImageUtils::ImportFileAsTexture2D(Path);
	if (!Texture)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Could not import card art: %s"), *Path);
		return nullptr;
	}

	Texture->SRGB = true;
	Texture->Filter = TF_Bilinear;
	Texture->NeverStream = true;
	Texture->LODGroup = TEXTUREGROUP_UI;
	Texture->UpdateResource();
	return Texture;
}

UTexture2D* UCardArtSubsystem::GetCardArt(int32 CardId)
{
	if (CardId <= 0)
	{
		return nullptr;
	}
	if (const TObjectPtr<UTexture2D>* Cached = ArtCache.Find(CardId))
	{
		return Cached->Get();
	}

	UTexture2D* Texture = LoadTexture(CardArtPath(CardId));
	ArtCache.Add(CardId, Texture);
	return Texture;
}

UTexture2D* UCardArtSubsystem::GetCardBack()
{
	if (CardBack || bBackLoadAttempted)
	{
		return CardBack;
	}
	bBackLoadAttempted = true;
	CardBack = LoadTexture(FPaths::Combine(ArtDirectory, TEXT("back.jpg")));
	return CardBack;
}

bool UCardArtSubsystem::HasCardArt(int32 CardId) const
{
	if (ArtCache.Contains(CardId))
	{
		return ArtCache.FindRef(CardId) != nullptr;
	}
	return FPaths::FileExists(CardArtPath(CardId));
}
