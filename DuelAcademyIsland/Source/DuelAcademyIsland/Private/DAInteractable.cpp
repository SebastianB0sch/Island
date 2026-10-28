// Duel Academy Island - signs, card shop, holographic duel fields.

#include "DAInteractable.h"

#include "Components/BillboardComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DACardDatabase.h"
#include "DAIslandSubsystem.h"
#include "DAStudentCharacter.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ADAInteractable::ADAInteractable()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

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
	SetActorTickEnabled(bMarker || Kind == EDAInteractKind::DuelField);
}

void ADAInteractable::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		Sub->UnregisterInteractable(this);
	}
	Super::EndPlay(EndPlayReason);
}

FString ADAInteractable::GetInteractPrompt() const
{
	switch (Kind)
	{
	case EDAInteractKind::CardShop:  return TEXT("Buy a booster pack");
	case EDAInteractKind::DuelField: return IsDuelRunning() ? TEXT("Duel in progress") : TEXT("Start a holographic duel");
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
	return !(Kind == EDAInteractKind::DuelField && IsDuelRunning());
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

UStaticMeshComponent* ADAInteractable::AddHoloMesh(const TCHAR* EngineShape, UMaterialInterface* Material)
{
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, EngineShape, nullptr, LOAD_NoWarn | LOAD_Quiet);
	UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(this, NAME_None, RF_Transient);
	C->SetupAttachment(Root);
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	C->SetCastShadow(false);
	if (Mesh)
	{
		C->SetStaticMesh(Mesh);
	}
	if (Material)
	{
		C->SetMaterial(0, Material);
	}
	C->SetRelativeScale3D(FVector(0.01));
	C->RegisterComponent();
	return C;
}

void ADAInteractable::StartDuel(ADAStudentCharacter* By)
{
	if (IsDuelRunning())
	{
		return;
	}
	Duelist = By;
	DuelTime = 0.f;
	DuelStep = 0;
	LifePointsA = 4000;
	LifePointsB = 4000;

	UMaterialInterface* Holo = LoadObject<UMaterialInterface>(nullptr, DuelAcademy::HologramMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);
	UMaterialInterface* CardBack = LoadObject<UMaterialInterface>(nullptr, DuelAcademy::CardBackMaterial, nullptr, LOAD_NoWarn | LOAD_Quiet);
	HoloMID = Holo ? UMaterialInstanceDynamic::Create(Holo, this) : nullptr;
	if (HoloMID)
	{
		HoloMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.3f, 0.9f, 1.f));
	}
	UMaterialInstanceDynamic* RedMID = Holo ? UMaterialInstanceDynamic::Create(Holo, this) : nullptr;
	if (RedMID)
	{
		RedMID->SetVectorParameterValue(TEXT("Color"), FLinearColor(1.f, 0.25f, 0.15f));
	}

	HoloPieces.Reset();
	int32 Group = 0;
	auto Add = [this, &Group](const TCHAR* Shape, UMaterialInterface* Mat, const FVector& Loc, const FVector& Scale, const FRotator& Rot, float Delay, float Spin, float Bob)
	{
		FDAHoloPiece P;
		P.Group = Group;
		P.Mesh = AddHoloMesh(Shape, Mat);
		P.BaseLocation = Loc;
		P.BaseScale = Scale;
		P.BaseRotation = Rot;
		P.Delay = Delay;
		P.Spin = Spin;
		P.Bob = Bob;
		HoloPieces.Add(P);
	};

	static const TCHAR* Plane = TEXT("/Engine/BasicShapes/Plane.Plane");
	static const TCHAR* Cube = TEXT("/Engine/BasicShapes/Cube.Cube");
	static const TCHAR* Sphere = TEXT("/Engine/BasicShapes/Sphere.Sphere");
	static const TCHAR* Cone = TEXT("/Engine/BasicShapes/Cone.Cone");
	static const TCHAR* Cylinder = TEXT("/Engine/BasicShapes/Cylinder.Cylinder");

	// Face-down set cards for both duelists (lying on the field), then the summoned monsters' cards (standing).
	for (int32 Side = -1; Side <= 1; Side += 2)
	{
		for (int32 i = 0; i < 3; ++i)
		{
			Add(Plane, CardBack, FVector(Side * 650.0, (i - 1) * 260.0, 5.0), FVector(1.6, 2.3, 1.0), FRotator(0.f, 90.f, 0.f), 0.3f + i * 0.25f, 0.f, 0.f);
		}
		// Standing card behind each monster, facing across the field (roll makes it upright, yaw turns it).
		Add(Plane, CardBack, FVector(Side * 420.0, 0.0, 190.0), FVector(2.4, 3.4, 1.0), FRotator(0.f, Side > 0 ? -90.f : 90.f, 90.f), 1.4f, 0.f, 6.f);
	}

	// Monster A (the player's): a sky dragon made of glowing primitives.
	Group = 1;
	const FVector A(-300.0, 0.0, 330.0);
	Add(Sphere, HoloMID, A, FVector(2.2, 1.4, 1.4), FRotator::ZeroRotator, 2.0f, 0.f, 18.f);                               // body
	Add(Cone, HoloMID, A + FVector(170.0, 0.0, 50.0), FVector(0.9, 0.9, 1.4), FRotator(-90.f, 0.f, 0.f), 2.2f, 0.f, 18.f);  // head
	Add(Cube, HoloMID, A + FVector(0.0, 160.0, 40.0), FVector(1.4, 2.6, 0.06), FRotator(0.f, 0.f, 25.f), 2.4f, 0.f, 18.f);  // wing
	Add(Cube, HoloMID, A + FVector(0.0, -160.0, 40.0), FVector(1.4, 2.6, 0.06), FRotator(0.f, 0.f, -25.f), 2.4f, 0.f, 18.f); // wing
	Add(Cone, HoloMID, A + FVector(-200.0, 0.0, -20.0), FVector(0.5, 0.5, 1.8), FRotator(90.f, 0.f, 0.f), 2.6f, 0.f, 18.f); // tail

	// Monster B (the hologram rival): an armoured guardian.
	Group = 2;
	const FVector B(300.0, 0.0, 120.0);
	Add(Cylinder, RedMID, B, FVector(1.1, 1.1, 2.2), FRotator::ZeroRotator, 3.0f, 0.f, 6.f);                                  // body
	Add(Sphere, RedMID, B + FVector(0.0, 0.0, 160.0), FVector(0.8, 0.8, 0.8), FRotator::ZeroRotator, 3.2f, 0.f, 6.f);         // head
	Add(Cube, RedMID, B + FVector(-120.0, 70.0, 60.0), FVector(2.6, 0.12, 0.25), FRotator(0.f, 0.f, 0.f), 3.4f, 0.f, 6.f);     // sword
	Add(Cube, RedMID, B + FVector(-60.0, -90.0, 40.0), FVector(0.1, 1.2, 1.6), FRotator::ZeroRotator, 3.4f, 0.f, 6.f);        // shield

	HoloLight = NewObject<UPointLightComponent>(this, NAME_None, RF_Transient);
	HoloLight->SetupAttachment(Root);
	HoloLight->SetRelativeLocation(FVector(0.0, 0.0, 400.0));
	HoloLight->SetLightColor(FLinearColor(0.3f, 0.85f, 1.f));
	HoloLight->SetIntensity(0.f);
	HoloLight->SetAttenuationRadius(2500.f);
	HoloLight->SetCastShadows(false);
	HoloLight->SetIntensityUnits(ELightUnits::Unitless);
	HoloLight->RegisterComponent();

	if (By)
	{
		By->SetDuelPose(true);
	}
	if (UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this))
	{
		FDAMessage Msg;
		Msg.Title = TEXT("DUEL!");
		Msg.Body = FString::Printf(TEXT("%s - holographic duel started!\nYou: 4000 LP     Rival: 4000 LP"), *GetInteractName());
		Msg.Accent = FLinearColor(0.3f, 0.85f, 1.f);
		Msg.Duration = 4.f;
		Sub->PushMessage(Msg);
		Sub->PlayUISound(TEXT("A_DuelStart"), 1.f);
	}
	SetActorTickEnabled(true);
}

void ADAInteractable::EndDuel()
{
	for (FDAHoloPiece& P : HoloPieces)
	{
		if (P.Mesh)
		{
			P.Mesh->DestroyComponent();
		}
	}
	HoloPieces.Reset();
	if (HoloLight)
	{
		HoloLight->DestroyComponent();
		HoloLight = nullptr;
	}
	if (ADAStudentCharacter* C = Duelist.Get())
	{
		C->SetDuelPose(false);
	}
	Duelist.Reset();
	DuelTime = -1.f;
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
	if (!IsDuelRunning())
	{
		return;
	}

	DuelTime += DeltaSeconds;
	UDAIslandSubsystem* Sub = UDAIslandSubsystem::Get(this);
	const float FadeOutStart = 17.f;
	const float Fade = DuelTime < FadeOutStart ? 1.f : FMath::Clamp(1.f - (DuelTime - FadeOutStart) / 1.5f, 0.f, 1.f);

	// Attack choreography offsets
	FVector AttackA = FVector::ZeroVector;
	FVector AttackB = FVector::ZeroVector;
	auto Lunge = [](float T, float Start) -> float
	{
		const float X = (T - Start) / 1.2f;
		return (X > 0.f && X < 1.f) ? FMath::Sin(X * PI) : 0.f;
	};
	AttackA.X = 420.0 * Lunge(DuelTime, 6.f) + 520.0 * Lunge(DuelTime, 13.f);
	AttackB.X = -380.0 * Lunge(DuelTime, 9.5f);

	for (int32 i = 0; i < HoloPieces.Num(); ++i)
	{
		FDAHoloPiece& P = HoloPieces[i];
		if (!P.Mesh)
		{
			continue;
		}
		const float Appear = FMath::Clamp((DuelTime - P.Delay) / 0.6f, 0.f, 1.f);
		const float Ease = Appear * Appear * (3.f - 2.f * Appear);
		const bool bMonsterA = P.Group == 1;
		const bool bMonsterB = P.Group == 2;
		float Defeat = 1.f;
		if (bMonsterB && DuelTime > 14.f)
		{
			Defeat = FMath::Clamp(1.f - (DuelTime - 14.f) / 0.8f, 0.f, 1.f);
		}
		FVector Loc = P.BaseLocation + FVector(0.0, 0.0, P.Bob * FMath::Sin(DuelTime * 2.2f + i));
		if (bMonsterA)
		{
			Loc += AttackA;
		}
		if (bMonsterB)
		{
			Loc += AttackB;
		}
		P.Mesh->SetRelativeLocation(Loc);
		P.Mesh->SetRelativeRotation(P.BaseRotation);
		P.Mesh->SetRelativeScale3D(P.BaseScale * FMath::Max(Ease * Fade * Defeat, 0.001f));
	}
	if (HoloLight)
	{
		HoloLight->SetIntensity(30000.f * Fade * FMath::Clamp(DuelTime, 0.f, 1.f));
	}

	// Scripted duel log
	auto Step = [&](int32 Index, float At, const FString& StepTitle, const FString& StepBody, const TCHAR* Sound)
	{
		if (DuelStep == Index && DuelTime >= At)
		{
			++DuelStep;
			if (Sub)
			{
				FDAMessage Msg;
				Msg.Title = StepTitle;
				Msg.Body = StepBody;
				Msg.Accent = FLinearColor(0.3f, 0.85f, 1.f);
				Msg.Duration = 3.4f;
				Sub->PushMessage(Msg);
				if (Sound)
				{
					Sub->PlayUISound(Sound, 0.8f);
				}
			}
		}
	};
	Step(0, 2.0f, TEXT("Your turn"), TEXT("You summon CRIMSON SKY SERPENT (ATK 3000) in attack position!"), TEXT("A_CardDraw"));
	Step(1, 3.2f, TEXT("Rival's field"), TEXT("Your rival summons AZURE PALACE KNIGHT (ATK 2000)."), TEXT("A_CardDraw"));
	if (DuelStep == 2 && DuelTime >= 6.6f)
	{
		LifePointsB -= 1000;
	}
	Step(2, 6.6f, TEXT("Attack!"), TEXT("Crimson Sky Serpent attacks! Rival takes 1000 damage.\nYou: 4000 LP     Rival: 3000 LP"), TEXT("A_DuelStart"));
	if (DuelStep == 3 && DuelTime >= 10.1f)
	{
		LifePointsA -= 600;
	}
	Step(3, 10.1f, TEXT("Trap card!"), TEXT("Rival activates MIRROR OF THE LAKE - the knight strikes back for 600!\nYou: 3400 LP     Rival: 3000 LP"), TEXT("A_CardDraw"));
	if (DuelStep == 4 && DuelTime >= 13.6f)
	{
		LifePointsB = 0;
	}
	Step(4, 13.6f, TEXT("Final attack!"), TEXT("Burst Stream of... Crimson! The knight is destroyed.\nYou: 3400 LP     Rival: 0 LP"), TEXT("A_DuelStart"));
	Step(5, 15.2f, TEXT("YOU WIN!"), TEXT("That's game! Duel Academy's holographic system thanks you for dueling."), TEXT("A_Discover"));

	if (DuelTime > FadeOutStart + 1.6f)
	{
		EndDuel();
	}
}
