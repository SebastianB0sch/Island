// Duel Academy Island - schedule-driven NPC spawn point implementation.

#include "DANpcSpawnPoint.h"

#include "Components/SceneComponent.h"
#include "DANpcDirector.h"
#include "DAStudentNPC.h"
#include "Engine/World.h"

#if WITH_EDITORONLY_DATA
#include "Components/BillboardComponent.h"
#include "Components/TextRenderComponent.h"
#endif

ADANpcSpawnPoint::ADANpcSpawnPoint()
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
		EditorLabel->SetWorldSize(38.f);
		EditorLabel->SetTextRenderColor(FColor(255, 190, 80));
		EditorLabel->SetRelativeLocation(FVector(0.f, 0.f, 110.f));
		EditorLabel->bIsEditorOnly = true;
	}
#endif
}

void ADANpcSpawnPoint::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);

#if WITH_EDITORONLY_DATA
	RefreshEditorLabel();
#endif
}

#if WITH_EDITORONLY_DATA
void ADANpcSpawnPoint::RefreshEditorLabel()
{
	if (EditorLabel)
	{
		EditorLabel->SetText(FText::FromString(FString::Printf(TEXT("%s [%s]"), *SpawnPointId, *SpawnRole)));
	}
}
#endif

bool ADANpcSpawnPoint::MatchesSchedule(const FString& InScheduleId, const FString& InWeekday,
	const FString& InPeriod, const FString& InActiveEvent) const
{
	if (!bEnabled)
	{
		return false;
	}

	// Event overrides win: a point pinned to an event only exists during that event.
	if (!EventOverride.IsEmpty())
	{
		return EventOverride.Equals(InActiveEvent, ESearchCase::IgnoreCase);
	}

	if (bEventOnly && InActiveEvent.IsEmpty())
	{
		return false;
	}

	TArray<FString> Query;
	if (!InScheduleId.IsEmpty())
	{
		Query.Add(InScheduleId);
	}
	if (!InWeekday.IsEmpty())
	{
		Query.Add(InWeekday);
	}
	if (!InPeriod.IsEmpty())
	{
		Query.Add(InPeriod);
	}

	if (Query.Num() == 0)
	{
		return true;
	}

	for (const FString& Tag : ScheduleTags)
	{
		for (const FString& Value : Query)
		{
			if (Tag.Equals(Value, ESearchCase::IgnoreCase))
			{
				return true;
			}
		}
	}

	if (!ScheduleId.IsEmpty())
	{
		for (const FString& Value : Query)
		{
			if (ScheduleId.Equals(Value, ESearchCase::IgnoreCase))
			{
				return true;
			}
		}
		return false;
	}

	// A point with no explicit id and no tags is a generic "always here" mark.
	return ScheduleTags.Num() == 0;
}

AActor* ADANpcSpawnPoint::SpawnNpc(ADANpcDirector* Director)
{
	if (SpawnedNpc.IsValid() || !GetWorld())
	{
		return SpawnedNpc.Get();
	}

	UClass* ClassToSpawn = NpcClass ? NpcClass.Get() : nullptr;
	if (!ClassToSpawn && Director)
	{
		ClassToSpawn = Director->GetDefaultNpcClass();
	}
	if (!ClassToSpawn)
	{
		return nullptr;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;
	Params.Owner = Director;

	AActor* Npc = GetWorld()->SpawnActor<AActor>(ClassToSpawn, GetSpawnLocation(), GetSpawnRotation(), Params);
	if (!Npc)
	{
		return nullptr;
	}

	if (ADAStudentNPC* Student = Cast<ADAStudentNPC>(Npc))
	{
		Student->Dorm = Dorm;
		Student->WanderRadius = WanderRadius;
		if (!DisplayName.IsEmpty())
		{
			Student->DisplayName = DisplayName;
		}
	}

	SpawnedNpc = Npc;
	OnNpcSpawned.Broadcast(this, Npc);
	OnNpcSpawnedNative(Npc);
	return Npc;
}

void ADANpcSpawnPoint::DespawnNpc()
{
	AActor* Npc = SpawnedNpc.Get();
	if (!Npc)
	{
		return;
	}

	SpawnedNpc.Reset();
	OnNpcDespawned.Broadcast(this, Npc);
	OnNpcDespawnedNative(Npc);
	Npc->Destroy();
}

void ADANpcSpawnPoint::OnNpcSpawnedNative_Implementation(AActor* Npc)
{
}

void ADANpcSpawnPoint::OnNpcDespawnedNative_Implementation(AActor* Npc)
{
}
