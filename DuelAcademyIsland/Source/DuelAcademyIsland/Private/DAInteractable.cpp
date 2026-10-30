// Duel Academy Island - signs, card shop and duel field triggers.

#include "DAInteractable.h"

#include "Components/BillboardComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DAHUD.h"
#include "DAIslandSubsystem.h"
#include "DAStudentCharacter.h"
#include "DACardDatabase.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ADAInteractable::ADAInteractable()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = false;

	Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	RootComponent = Root;

	Marker = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Marker"));
	Marker->SetupAttachment(Root);
	Marker->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Marker->SetCastShadow(false);
	Marker->SetRelativeLocation(FVector(0.0, 0.0, 260.0));
	Marker->SetRelativeRotation(FRotator(180.f, 0.f, 0.f));
	Marker->SetRelativeScale3D(FVector(0.35, 0.35, 0.5));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(TEXT("/Engine/BasicShapes/Cone.Cone"));
	if (ConeMesh.Succeeded())
	{
		Marker->SetStaticMesh(ConeMesh.Object);
	}

#if WITH_EDITORONLY_DATA
	EditorIcon = CreateEditorOnlyDefaultSubobject<UBillboardComponent>(TEXT("EditorIcon"));
	if (EditorIcon)
	{
		EditorIcon->SetupAttachment(Root);
		EditorIcon->bIsScreenSizeScaled = true;
	}
#endif
}

void ADAInteractable::BeginPlay()
{
	Super::BeginPlay();
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		Sub->RegisterInteractable(this);
	}

	// Practice fields use resident duelists as holographic opponents; the arena
	// keeps Jaden so the first duel matches the island's opening fiction.
	if (Kind == EDAInteractKind::DuelField && OpponentId == TEXT("jaden") && OpponentName == TEXT("Jaden Yuki"))
	{
		if (Title.Contains(TEXT("Practice Field")))
		{
			OpponentId = TEXT("syrus");
			OpponentName = TEXT("Syrus Truesdale");
			OpponentDeckId = TEXT("water");
		}
		else if (Title.Contains(TEXT("Outdoor Practice")))
		{
			OpponentId = TEXT("chazz");
			OpponentName = TEXT("Chazz Princeton");
			OpponentDeckId = TEXT("wind");
		}
		else if (Title.Contains(TEXT("Beach")))
		{
			OpponentId = TEXT("alexis");
			OpponentName = TEXT("Alexis Rhodes");
			OpponentDeckId = TEXT("water");
		}
	}

	const bool bMarker = bShowMarker && (Kind == EDAInteractKind::DuelField || Kind == EDAInteractKind::CardShop);
	Marker->SetVisibility(bMarker);
	if (bMarker)
	{
		if (UMaterialInterface* Holo = LoadObject<UMaterialInterface>(nullptr, DuelAcademy::HologramMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet))
		{
			UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(Holo, this);
			MID->SetVectorParameterValue(TEXT("Color"), Kind == EDAInteractKind::CardShop ? FLinearColor(1.f, 0.7f, 0.15f) : FLinearColor(0.25f, 0.85f, 1.f));
			Marker->SetMaterial(0, MID);
		}
	}
	SetActorTickEnabled(bMarker);
}

void ADAInteractable::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		Sub->UnregisterInteractable(this);
	}
	Super::EndPlay(EndPlayReason);
}

namespace
{
	bool IsAnyDuelOpen(const AActor* Context)
	{
		if (const UWorld* World = Context ? Context->GetWorld() : nullptr)
		{
			if (const APlayerController* PC = World->GetFirstPlayerController())
			{
				if (const ADAHUD* HUD = Cast<ADAHUD>(PC->GetHUD()))
				{
					return HUD->IsDuelOpen();
				}
			}
		}
		return false;
	}
}

FString ADAInteractable::GetInteractPrompt() const
{
	switch (Kind)
	{
	case EDAInteractKind::CardShop:  return TEXT("Buy a booster pack");
	case EDAInteractKind::DuelField: return IsAnyDuelOpen(this) ? TEXT("Duel in progress") : TEXT("Duel");
	case EDAInteractKind::Info:      return TEXT("Look");
	case EDAInteractKind::Sign:
	default:                         return TEXT("Read");
	}
}

FString ADAInteractable::GetInteractName() const
{
	return Title.IsEmpty() ? FString(TEXT("Sign")) : Title;
}

bool ADAInteractable::CanInteract(const ADAStudentCharacter* By) const
{
	return !(Kind == EDAInteractKind::DuelField && IsAnyDuelOpen(this));
}

void ADAInteractable::Interact(ADAStudentCharacter* By)
{
	UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this);
	switch (Kind)
	{
	case EDAInteractKind::CardShop:
		OpenBoosterPack(By);
		break;
	case EDAInteractKind::DuelField:
		StartDuel(By);
		break;
	case EDAInteractKind::Sign:
	case EDAInteractKind::Info:
	default:
		if (Sub)
		{
			FDAMessage Msg;
			Msg.Title = GetInteractName();
			Msg.Body = Text;
			Msg.Duration = 10.f;
			Sub->PushMessage(Msg);
			Sub->PlayUISound(TEXT("A_UIClick"), 0.5f);
		}
		break;
	}
}

// ------------------------------------------------------------------------ card shop

void ADAInteractable::OpenBoosterPack(ADAStudentCharacter* By)
{
	UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this);
	if (!Sub)
	{
		return;
	}
	++PacksOpened;
	FRandomStream Rng(FMath::Rand());
	const TArray<DuelAcademy::FCardDef>& All = DuelAcademy::Cards();
	FString Body = FString::Printf(TEXT("Booster pack #%d - you pulled:\n"), PacksOpened);
	bool bUltra = false;
	for (int32 i = 0; i < 5; ++i)
	{
		const int32 Index = DuelAcademy::PullCardIndex(Rng);
		const DuelAcademy::FCardDef& C = All[Index];
		if (C.Atk > 0 || C.Def > 0)
		{
			Body += FString::Printf(TEXT("  [%s]  %s  (%s, ATK %d / DEF %d)\n"), DuelAcademy::RarityName(C.Rarity), C.Name, C.Type, C.Atk, C.Def);
		}
		else
		{
			Body += FString::Printf(TEXT("  [%s]  %s  (%s)\n"), DuelAcademy::RarityName(C.Rarity), C.Name, C.Type);
		}
		bUltra |= C.Rarity == DuelAcademy::ERarity::UltraRare;
		if (By)
		{
			By->AddCardToCollection(C.Name);
		}
	}
	if (By)
	{
		Body += FString::Printf(TEXT("\nCollection: %d / %d different cards"), By->GetCollectionSize(), All.Num());
	}
	FDAMessage Msg;
	Msg.Title = bUltra ? TEXT("Card Shop - ULTRA RARE PULL!") : TEXT("Card Shop");
	Msg.Body = Body;
	Msg.Accent = bUltra ? FLinearColor(1.f, 0.85f, 0.2f) : FLinearColor(0.95f, 0.55f, 0.15f);
	Msg.Duration = 12.f;
	Sub->PushMessage(Msg);
	Sub->PlayUISound(TEXT("A_CardDraw"), 0.9f);
	if (bUltra)
	{
		Sub->PlayUISound(TEXT("A_Discover"), 0.9f);
	}
}

// ------------------------------------------------------------------------ duel field

void ADAInteractable::StartDuel(ADAStudentCharacter* By)
{
	if (!By || IsAnyDuelOpen(this))
	{
		return;
	}
	APlayerController* PC = Cast<APlayerController>(By->GetController());
	ADAHUD* HUD = PC ? Cast<ADAHUD>(PC->GetHUD()) : nullptr;
	if (!HUD)
	{
		return;
	}

	By->SetDuelPose(true);
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		FDAMessage Msg;
		Msg.Title = TEXT("DUEL!");
		Msg.Body = FString::Printf(TEXT("%s - choose a starter deck to face %s."), *GetInteractName(), *OpponentName);
		Msg.Accent = FLinearColor(0.3f, 0.85f, 1.f);
		Msg.Duration = 3.f;
		Sub->PushMessage(Msg);
		Sub->PlayUISound(TEXT("A_DuelStart"), 1.f);
	}
	HUD->OpenDuelDeckSelect(OpponentId, OpponentName, OpponentDeckId);
}

void ADAInteractable::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	MarkerTime += DeltaSeconds;
	if (Marker && Marker->IsVisible())
	{
		Marker->SetRelativeLocation(FVector(0.0, 0.0, 260.0 + 25.0 * FMath::Sin(MarkerTime * 2.0f)));
		Marker->SetRelativeRotation(FRotator(180.f, MarkerTime * 90.f, 0.f));
	}
}
