// Duel Academy Island - named location zone.

#include "DALocationVolume.h"

#include "Components/BoxComponent.h"
#include "Components/TextRenderComponent.h"
#include "DAIslandSubsystem.h"

namespace
{
	// A box extent is a half-size; negative or non-finite values poison both
	// containment and the smallest-volume tie-break.
	FVector SanitizeZoneExtent(const FVector& Extent)
	{
		return FVector(
			FMath::IsFinite(Extent.X) ? FMath::Abs(Extent.X) : 5000.0,
			FMath::IsFinite(Extent.Y) ? FMath::Abs(Extent.Y) : 5000.0,
			FMath::IsFinite(Extent.Z) ? FMath::Abs(Extent.Z) : 3000.0);
	}
}

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
	ZoneExtent = SanitizeZoneExtent(ZoneExtent);
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
	ZoneExtent = SanitizeZoneExtent(ZoneExtent);
	if (Box)
	{
		Box->SetBoxExtent(ZoneExtent, false);
	}
	if (!FMath::IsFinite(SpawnYaw))
	{
		SpawnYaw = 0.f;
	}
	if (!FMath::IsFinite(SpawnLocation.X) || !FMath::IsFinite(SpawnLocation.Y) || !FMath::IsFinite(SpawnLocation.Z))
	{
		UE_LOG(LogTemp, Warning, TEXT("DALocationVolume '%s' has a non-finite spawn location; using its centre."), *LocationId);
		SpawnLocation = GetActorLocation() + FVector(0.0, 0.0, 200.0);
	}
	else if (SpawnLocation.IsNearlyZero())
	{
		SpawnLocation = GetActorLocation() + FVector(0.0, 0.0, 200.0);
	}
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		Sub->RegisterZone(this);
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
	return FMath::Abs(Local.X) <= FMath::Abs(ZoneExtent.X)
		&& FMath::Abs(Local.Y) <= FMath::Abs(ZoneExtent.Y)
		&& FMath::Abs(Local.Z) <= FMath::Abs(ZoneExtent.Z);
}
