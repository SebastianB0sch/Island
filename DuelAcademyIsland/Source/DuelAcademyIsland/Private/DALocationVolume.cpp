// Duel Academy Island - named location zone.

#include "DALocationVolume.h"

#include "Components/BoxComponent.h"
#include "Components/TextRenderComponent.h"
#include "DAIslandSubsystem.h"

ADALocationVolume::ADALocationVolume()
{
	PrimaryActorTick.bCanEverTick = false;

	Box = CreateDefaultSubobject<UBoxComponent>(TEXT("Zone"));
	RootComponent = Box;
	Box->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Box->SetGenerateOverlapEvents(false);
	Box->SetCanEverAffectNavigation(false);
	Box->ShapeColor = FColor(255, 200, 40);
	Box->SetLineThickness(20.f);
	Box->SetHiddenInGame(true);

#if WITH_EDITORONLY_DATA
	EditorLabel = CreateEditorOnlyDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
	if (EditorLabel)
	{
		EditorLabel->SetupAttachment(Box);
		EditorLabel->SetHorizontalAlignment(EHTA_Center);
		EditorLabel->SetWorldSize(600.f);
		EditorLabel->SetHiddenInGame(true);
		EditorLabel->SetRelativeLocation(FVector(0.0, 0.0, 800.0));
		EditorLabel->bIsEditorOnly = true;
	}
#endif
}

void ADALocationVolume::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	Box->SetBoxExtent(ZoneExtent, false);
#if WITH_EDITORONLY_DATA
	if (EditorLabel)
	{
		EditorLabel->SetText(FText::FromString(DisplayName));
		EditorLabel->SetTextRenderColor(ThemeColor.ToFColor(true));
	}
#endif
}

void ADALocationVolume::BeginPlay()
{
	Super::BeginPlay();
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		Sub->RegisterZone(this);
	}
	if (SpawnLocation.IsNearlyZero())
	{
		SpawnLocation = GetActorLocation() + FVector(0.0, 0.0, 200.0);
	}
}

void ADALocationVolume::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		Sub->UnregisterZone(this);
	}
	Super::EndPlay(EndPlayReason);
}

bool ADALocationVolume::ContainsPoint(const FVector& WorldPoint) const
{
	const FVector Local = GetActorTransform().InverseTransformPositionNoScale(WorldPoint);
	return FMath::Abs(Local.X) <= ZoneExtent.X && FMath::Abs(Local.Y) <= ZoneExtent.Y && FMath::Abs(Local.Z) <= ZoneExtent.Z;
}
