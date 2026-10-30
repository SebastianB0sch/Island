#include "DACharacterPortraitSubsystem.h"

#include "DuelAcademyIsland.h"
#include "Engine/Texture2D.h"
#include "ImageUtils.h"
#include "Misc/Paths.h"

void UCharacterPortraitSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	PortraitDirectory = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Portraits"));
}

FString UCharacterPortraitSubsystem::PortraitPath(const FString& CharacterId, bool bFaceCrop) const
{
	const FString Suffix = bFaceCrop ? TEXT("_face") : TEXT("");
	return FPaths::Combine(PortraitDirectory, CharacterId + Suffix + TEXT(".png"));
}

FString UCharacterPortraitSubsystem::ExpressionPath(const FString& CharacterId, const FString& Expression) const
{
	return FPaths::Combine(PortraitDirectory, CharacterId + TEXT("_") + Expression + TEXT(".png"));
}

UTexture2D* UCharacterPortraitSubsystem::LoadTexture(const FString& Path)
{
	if (!FPaths::FileExists(Path))
	{
		UE_LOG(LogDuelAcademyIsland, Verbose, TEXT("Character portrait missing: %s"), *Path);
		return nullptr;
	}

	UTexture2D* Texture = FImageUtils::ImportFileAsTexture2D(Path);
	if (!Texture)
	{
		UE_LOG(LogDuelAcademyIsland, Warning, TEXT("Could not import character portrait: %s"), *Path);
		return nullptr;
	}

	Texture->SRGB = true;
	Texture->Filter = TF_Bilinear;
	Texture->NeverStream = true;
	Texture->LODGroup = TEXTUREGROUP_UI;
	Texture->UpdateResource();
	return Texture;
}

UTexture2D* UCharacterPortraitSubsystem::GetPortrait(const FString& CharacterId, bool bFaceCrop)
{
	if (CharacterId.IsEmpty())
	{
		return nullptr;
	}
	TMap<FString, TObjectPtr<UTexture2D>>& Cache = bFaceCrop ? FaceCache : PortraitCache;
	if (const TObjectPtr<UTexture2D>* Cached = Cache.Find(CharacterId))
	{
		return Cached->Get();
	}

	UTexture2D* Texture = LoadTexture(PortraitPath(CharacterId, bFaceCrop));
	// Fall back to the bust portrait when a dedicated face crop does not exist.
	if (!Texture && bFaceCrop)
	{
		Texture = LoadTexture(PortraitPath(CharacterId, false));
	}
	Cache.Add(CharacterId, Texture);
	return Texture;
}

UTexture2D* UCharacterPortraitSubsystem::GetExpression(const FString& CharacterId, const FString& Expression)
{
	if (CharacterId.IsEmpty() || Expression.IsEmpty())
	{
		return nullptr;
	}
	const FString Key = CharacterId + TEXT("#") + Expression;
	if (const TObjectPtr<UTexture2D>* Cached = ExpressionCache.Find(Key))
	{
		return Cached->Get();
	}

	UTexture2D* Texture = LoadTexture(ExpressionPath(CharacterId, Expression));
	// Fall back to the base render when a particular expression was not
	// supplied; the cut-in still works, it simply reuses the neutral art.
	if (!Texture)
	{
		Texture = GetPortrait(CharacterId, false);
	}
	ExpressionCache.Add(Key, Texture);
	return Texture;
}

bool UCharacterPortraitSubsystem::HasPortrait(const FString& CharacterId) const
{
	return FPaths::FileExists(PortraitPath(CharacterId, false))
		|| FPaths::FileExists(PortraitPath(CharacterId, true));
}

bool UCharacterPortraitSubsystem::HasExpression(const FString& CharacterId, const FString& Expression) const
{
	return FPaths::FileExists(ExpressionPath(CharacterId, Expression));
}
