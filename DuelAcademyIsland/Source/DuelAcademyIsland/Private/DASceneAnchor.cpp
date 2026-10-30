// Duel Academy Island - named scene anchor implementation.

#include "DASceneAnchor.h"

#include "Components/SceneComponent.h"

#if WITH_EDITORONLY_DATA
#include "Components/BillboardComponent.h"
#include "Components/TextRenderComponent.h"
#endif

ADASceneAnchor::ADASceneAnchor()
{
	PrimaryActorTick.bCanEverTick = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

#if WITH_EDITORONLY_DATA
	EditorIcon = CreateEditorOnlyDefaultSubobject<UBillboardComponent>(TEXT("EditorIcon"));
	if (EditorIcon)
	{
		EditorIcon->SetupAttachment(Root);
		EditorIcon->bIsScreenSizeScaled = true;
	}

	EditorLabel = CreateEditorOnlyDefaultSubobject<UTextRenderComponent>(TEXT("EditorLabel"));
	if (EditorLabel)
	{
		EditorLabel->SetupAttachment(Root);
		EditorLabel->SetHorizontalAlignment(EHTA_Center);
		EditorLabel->SetWorldSize(45.f);
		EditorLabel->SetTextRenderColor(FColor(120, 220, 255));
		EditorLabel->SetRelativeLocation(FVector(0.f, 0.f, 90.f));
		EditorLabel->bIsEditorOnly = true;
	}
#endif
}

void ADASceneAnchor::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

#if WITH_EDITORONLY_DATA
	if (EditorLabel)
	{
		EditorLabel->SetText(FText::FromString(AnchorId));
		EditorLabel->SetWorldSize(FMath::Clamp(FOV, 20.f, 90.f) * 0.8f);
	}
#endif
}

FVector ADASceneAnchor::GetLookAtLocation() const
{
	return bUseLookAt ? LookAtTarget : GetActorLocation() + GetActorForwardVector() * 100.f;
}

FTransform ADASceneAnchor::GetViewTransform() const
{
	const FRotator ViewRotation = bUseLookAt
		? (LookAtTarget - GetActorLocation()).Rotation()
		: GetActorRotation();
	return FTransform(ViewRotation, GetActorLocation());
}

bool ADASceneAnchor::HasTag(const FString& Tag) const
{
	for (const FString& Existing : AnchorTags)
	{
		if (Existing.Equals(Tag, ESearchCase::IgnoreCase))
		{
			return true;
		}
	}
	return false;
}
