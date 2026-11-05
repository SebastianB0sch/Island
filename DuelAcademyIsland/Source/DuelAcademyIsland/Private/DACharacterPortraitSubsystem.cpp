#include "DACharacterPortraitSubsystem.h"

#include "DuelAcademyIsland.h"
#include "Engine/Texture2D.h"
#include "ImageUtils.h"
#include "Misc/Paths.h"

namespace
{
	/**
	 * Content ids are slugs.  Reject separators and parent-directory components
	 * so a malformed story id cannot escape Content/Data/Portraits.
	 */
	bool IsSafeAssetSegment(const FString& Value)
	{
		if (Value.IsEmpty() || Value.Len() > 128)
		{
			return false;
		}
		for (const TCHAR Character : Value)
		{
			if (!FChar::IsAlnum(Character) && Character != TEXT('_') && Character != TEXT('-'))
			{
				return false;
			}
		}
		return true;
	}

	FString NormalizeAssetSegment(const FString& Value)
	{
		return Value.TrimStartAndEnd().ToLower();
	}
}

void UCharacterPortraitSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	PortraitCache.Reset();
	FaceCache.Reset();
	ExpressionCache.Reset();
	PortraitDirectory = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data/Portraits"));
}

FString UCharacterPortraitSubsystem::PortraitPath(const FString& CharacterId, bool bFaceCrop) const
{
	const FString Id = NormalizeAssetSegment(CharacterId);
	if (!IsSafeAssetSegment(Id))
	{
		return FString();
	}
	const FString Suffix = bFaceCrop ? TEXT("_face") : TEXT("");
	return FPaths::Combine(PortraitDirectory, Id + Suffix + TEXT(".png"));
}

FString UCharacterPortraitSubsystem::ExpressionPath(const FString& CharacterId, const FString& Expression) const
{
	const FString Id = NormalizeAssetSegment(CharacterId);
	const FString ExpressionId = NormalizeAssetSegment(Expression);
	if (!IsSafeAssetSegment(Id) || !IsSafeAssetSegment(ExpressionId))
	{
		return FString();
	}
	return FPaths::Combine(PortraitDirectory, Id + TEXT("_") + ExpressionId + TEXT(".png"));
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
	const FString Key = NormalizeAssetSegment(CharacterId);
	if (!IsSafeAssetSegment(Key))
	{
		return nullptr;
	}
	TMap<FString, TObjectPtr<UTexture2D>>& Cache = bFaceCrop ? FaceCache : PortraitCache;
	if (const TObjectPtr<UTexture2D>* Cached = Cache.Find(Key))
	{
		return Cached->Get();
	}

	UTexture2D* Texture = LoadTexture(PortraitPath(Key, bFaceCrop));
	// Fall back to the bust portrait when a dedicated face crop does not exist.
	if (!Texture && bFaceCrop)
	{
		Texture = LoadTexture(PortraitPath(Key, false));
	}
	Cache.Add(Key, Texture);
	return Texture;
}

UTexture2D* UCharacterPortraitSubsystem::GetExpression(const FString& CharacterId, const FString& Expression)
{
	const FString Id = NormalizeAssetSegment(CharacterId);
	const FString ExpressionId = NormalizeAssetSegment(Expression);
	if (!IsSafeAssetSegment(Id) || !IsSafeAssetSegment(ExpressionId))
	{
		return nullptr;
	}
	const FString Key = Id + TEXT("#") + ExpressionId;
	if (const TObjectPtr<UTexture2D>* Cached = ExpressionCache.Find(Key))
	{
		return Cached->Get();
	}

	UTexture2D* Texture = LoadTexture(ExpressionPath(Id, ExpressionId));
	// Fall back to the base render when a particular expression was not
	// supplied; the cut-in still works, it simply reuses the neutral art.
	if (!Texture)
	{
		Texture = GetPortrait(Id, false);
	}
	ExpressionCache.Add(Key, Texture);
	return Texture;
}

bool UCharacterPortraitSubsystem::HasPortrait(const FString& CharacterId) const
{
	const FString Path = PortraitPath(CharacterId, false);
	const FString FacePath = PortraitPath(CharacterId, true);
	return (!Path.IsEmpty() && FPaths::FileExists(Path))
		|| (!FacePath.IsEmpty() && FPaths::FileExists(FacePath));
}

bool UCharacterPortraitSubsystem::HasExpression(const FString& CharacterId, const FString& Expression) const
{
	const FString Path = ExpressionPath(CharacterId, Expression);
	return !Path.IsEmpty() && FPaths::FileExists(Path);
}
