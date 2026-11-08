// Duel Academy Island - cosmetic anime puppet built from the licensed Fab Anime Character Pack.

#include "DAFabAnimePuppet.h"

#include "DAAvatarComponent.h"
#include "DAStudentNPC.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/Controller.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "TimerManager.h"

namespace
{
	const TCHAR* const BlueprintPath =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/bp_AnimeCharacter.bp_AnimeCharacter_C");

	const TCHAR* const HeadMale =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Male_Average/Head/Starter/skl_AnimeM_Head_0.skl_AnimeM_Head_0");
	const TCHAR* const HeadFemale =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Female_Average/Head/Starter/skl_AnimeF_Head_1.skl_AnimeF_Head_1");
	const TCHAR* const HairMale1 =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Male_Average/Hair/Starter1/sk_AnimeHair_M1.sk_AnimeHair_M1");
	const TCHAR* const HairMale2 =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Male_Average/Hair/Starter2/skl_AnimeHair_M2.skl_AnimeHair_M2");
	const TCHAR* const HairFemale1 =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Female_Average/Hair/Starter1/skl_AnimeHair_F1.skl_AnimeHair_F1");
	const TCHAR* const HairFemale2 =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Female_Average/Hair/Starter2/skl_AnimeHair_F2.skl_AnimeHair_F2");
	const TCHAR* const TopMaleTShirt =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Male_Average/Tops/Starter_TShirt/skl_AnimeM_Top_Tshirt.skl_AnimeM_Top_Tshirt");
	const TCHAR* const TopMaleTank =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Male_Average/Tops/Starter_Tank/skl_AnimeM_Top_tank.skl_AnimeM_Top_tank");
	const TCHAR* const TopMaleNak =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Male_Average/Tops/Starter_Nak/skl_AnimeM_Top_nak.skl_AnimeM_Top_nak");
	const TCHAR* const BottomMalePants =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Male_Average/Bottoms/Starter_pants/skl_AnimeM_Bottom_Pants.skl_AnimeM_Bottom_Pants");
	const TCHAR* const BottomMaleShorts =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Male_Average/Bottoms/Starter_Shorts/skl_AnimeM_Bottom_Shorts.skl_AnimeM_Bottom_Shorts");
	const TCHAR* const BottomMaleNak =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Male_Average/Bottoms/Starter_Nak/skl_AnimeM_bottom_nak.skl_AnimeM_bottom_nak");
	const TCHAR* const TopFemaleTank =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Female_Average/tops/Starter_Tank/skl_AnimeF_top_tank.skl_AnimeF_top_tank");
	const TCHAR* const TopFemaleTurtle =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Female_Average/tops/Starter_TurtleNeck/skl_AnimeF_top_TurtleNeck.skl_AnimeF_top_TurtleNeck");
	const TCHAR* const TopFemaleNak =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Female_Average/tops/Starter_Nak/skl_AnimeF_top_nak.skl_AnimeF_top_nak");
	const TCHAR* const BottomFemaleSkirt =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Female_Average/bottoms/Starter_Skirt/skl_AnimeF_bottom_skirt.skl_AnimeF_bottom_skirt");
	const TCHAR* const BottomFemaleShorts =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Female_Average/bottoms/Starter_Shorts/skl_AnimeF_bottom_shorts.skl_AnimeF_bottom_shorts");
	const TCHAR* const BottomFemaleNak =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Female_Average/bottoms/Starter_Nak/skl_AnimeF_bottom_nak.skl_AnimeF_bottom_nak");
	const TCHAR* const HeadMaleMaterial1 =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Male_Average/Head/Starter/mi_AnimeMale_Head1.mi_AnimeMale_Head1");
	const TCHAR* const HeadMaleMaterial2 =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Male_Average/Head/Starter/mi_AnimeMale_Head2.mi_AnimeMale_Head2");
	const TCHAR* const HeadFemaleMaterial1 =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Female_Average/Head/Starter/mi_AnimeF_Head1.mi_AnimeF_Head1");
	const TCHAR* const HeadFemaleMaterial2 =
		TEXT("/Game/AnimeCharacters/Blueprints/Characters/Female_Average/Head/Starter/mi_AnimeF_Head2.mi_AnimeF_Head2");
	const TCHAR* const HairBaseMaterial =
		TEXT("/Game/AnimeCharacters/Materials/Instances/Hairs/m_hair_Base.m_hair_Base");
	const TCHAR* const OutlineMaterial =
		TEXT("/Game/AnimeCharacters/Materials/Instances/Outlines/m_Outline_Inst3.m_Outline_Inst3");

	const FDAFabAnimeLook Looks[] = {
		// Male looks
		{ TEXT("fab_male_a"), false, HeadMale, HairMale1, TopMaleTShirt, BottomMalePants,
			HeadMaleMaterial1, FLinearColor(0.18f, 0.09f, 0.04f) },
		{ TEXT("fab_male_b"), false, HeadMale, HairMale2, TopMaleTank, BottomMaleShorts,
			HeadMaleMaterial2, FLinearColor(0.02f, 0.02f, 0.025f) },
		{ TEXT("fab_male_c"), false, HeadMale, HairMale1, TopMaleTank, BottomMalePants,
			HeadMaleMaterial2, FLinearColor(0.55f, 0.38f, 0.10f) },
		{ TEXT("fab_male_d"), false, HeadMale, HairMale2, TopMaleTShirt, BottomMaleShorts,
			HeadMaleMaterial1, FLinearColor(0.04f, 0.09f, 0.30f) },
		// Female looks
		{ TEXT("fab_female_a"), true, HeadFemale, HairFemale1, TopFemaleTank, BottomFemaleSkirt,
			HeadFemaleMaterial1, FLinearColor(0.45f, 0.20f, 0.10f) },
		{ TEXT("fab_female_b"), true, HeadFemale, HairFemale2, TopFemaleTurtle, BottomFemaleSkirt,
			HeadFemaleMaterial2, FLinearColor(0.03f, 0.025f, 0.03f) },
		{ TEXT("fab_female_c"), true, HeadFemale, HairFemale2, TopFemaleTank, BottomFemaleShorts,
			HeadFemaleMaterial1, FLinearColor(0.80f, 0.60f, 0.25f) },
		{ TEXT("fab_female_d"), true, HeadFemale, HairFemale1, TopFemaleTurtle, BottomFemaleShorts,
			HeadFemaleMaterial2, FLinearColor(0.70f, 0.25f, 0.45f) },
	};

	const FDAFabAnimeLook* FindLook(const FString& LookId)
	{
		for (const FDAFabAnimeLook& Look : Looks)
		{
			if (LookId.Equals(Look.Id, ESearchCase::IgnoreCase))
			{
				return &Look;
			}
		}
		return nullptr;
	}

	USkeletalMeshComponent* FindSkeletal(AActor* Actor, const TCHAR* Name)
	{
		if (!Actor)
		{
			return nullptr;
		}
		TArray<USkeletalMeshComponent*> Components;
		Actor->GetComponents<USkeletalMeshComponent>(Components);
		for (USkeletalMeshComponent* Component : Components)
		{
			if (Component && Component->GetFName() == FName(Name))
			{
				return Component;
			}
		}
		return nullptr;
	}

	/** The pack creates one inverted-hull outline component under each visible body part.
	 *  Its object names are generated (SkeletalMeshComponent_0..3), so pair it by parent
	 *  instead of relying on a pack-version-specific index. */
	USkeletalMeshComponent* FindOutline(AActor* Actor, USkeletalMeshComponent* Main)
	{
		if (!Actor || !Main)
		{
			return nullptr;
		}
		TArray<USkeletalMeshComponent*> Components;
		Actor->GetComponents<USkeletalMeshComponent>(Components);
		// The pack's shading component may already have established the follower link.
		// Only generated outline components count: a visible part (Hair/Top/Bottom) can
		// itself be leader-posed to the body, and must not be mistaken for an outline.
		for (USkeletalMeshComponent* Component : Components)
		{
			const FString Name = Component ? Component->GetFName().ToString() : FString();
			if (Component && Component != Main && Component->LeaderPoseComponent.Get() == Main
				&& Name.StartsWith(TEXT("SkeletalMeshComponent_")))
			{
				return Component;
			}
		}
		for (USkeletalMeshComponent* Component : Components)
		{
			if (!Component || Component == Main || Component->GetAttachParent() != Main)
			{
				continue;
			}
			if (Component->GetFName().ToString().StartsWith(TEXT("SkeletalMeshComponent_")))
			{
				return Component;
			}
		}
		// Older pack builds may not use the generated prefix.  Require an explicit
		// outline name or a non-visible child; never pair a known body part.
		for (USkeletalMeshComponent* Component : Components)
		{
			if (!Component || Component == Main || Component->GetAttachParent() != Main)
			{
				continue;
			}
			const FString Name = Component->GetFName().ToString();
			if (!Name.Contains(TEXT("Hair")) && !Name.Contains(TEXT("Top"))
				&& !Name.Contains(TEXT("Bottom")) && Name.Contains(TEXT("Outline")))
			{
				return Component;
			}
		}
		return nullptr;
	}

	USkeletalMesh* LoadMesh(const TCHAR* Path)
	{
		return Path ? LoadObject<USkeletalMesh>(nullptr, Path, nullptr, LOAD_NoWarn | LOAD_Quiet) : nullptr;
	}

	UMaterialInterface* LoadMaterial(const TCHAR* Path)
	{
		return Path ? LoadObject<UMaterialInterface>(nullptr, Path, nullptr, LOAD_NoWarn | LOAD_Quiet) : nullptr;
	}

	void TintClothing(USkeletalMeshComponent* Component, const FLinearColor& Color)
	{
		if (!Component)
		{
			return;
		}
		const TArray<FName> Slots = Component->GetMaterialSlotNames();
		for (int32 Index = 0; Index < Slots.Num(); ++Index)
		{
			const FString Slot = Slots[Index].ToString();
			if (!Slot.Contains(TEXT("Cloth"), ESearchCase::IgnoreCase)
				&& !Slot.Contains(TEXT("Clothing"), ESearchCase::IgnoreCase)
				&& !Slot.Contains(TEXT("CelColor"), ESearchCase::IgnoreCase))
			{
				continue;
			}
			UMaterialInterface* Base = Component->GetMaterial(Index);
			if (!Base)
			{
				continue;
			}
			UMaterialInstanceDynamic* MID = Cast<UMaterialInstanceDynamic>(Base);
			if (!MID)
			{
				MID = UMaterialInstanceDynamic::Create(Base, Component);
				if (MID)
				{
					Component->SetMaterial(Index, MID);
				}
			}
			if (MID)
			{
				MID->SetVectorParameterValue(TEXT("Color 1"), Color);
				MID->SetVectorParameterValue(TEXT("Color 2"), Color * 0.97f);
				MID->SetVectorParameterValue(TEXT("Color 3"), Color * 0.93f);
				MID->SetVectorParameterValue(TEXT("OutlineColor"), Color * 0.22f);
				MID->SetScalarParameterValue(TEXT("ShadowDepth"), 0.0f);
			}
		}
	}
}

UDAFabAnimeComponent::UDAFabAnimeComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = false;
	bAutoActivate = false;
}

void UDAFabAnimeComponent::BeginPlay()
{
	Super::BeginPlay();
	SetComponentTickEnabled(Puppet.IsValid());
}

void UDAFabAnimeComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	DeactivateLook();
	Super::EndPlay(EndPlayReason);
}

bool UDAFabAnimeComponent::ActivateLook(const FString& LookId)
{
	if (LookId.IsEmpty())
	{
		return false;
	}
	if (Puppet.IsValid() && ActiveLook.Equals(LookId, ESearchCase::IgnoreCase))
	{
		return true;
	}

	const FDAFabAnimeLook* Look = FindLook(LookId);
	if (!Look)
	{
		UE_LOG(LogTemp, Warning, TEXT("DAFabAnime: unknown look '%s'"), *LookId);
		return false;
	}

	DeactivateLook();

	AActor* Owner = GetOwner();
	UWorld* World = GetWorld();
	if (!Owner || !World)
	{
		return false;
	}

	UClass* PuppetClass = LoadClass<AActor>(nullptr, BlueprintPath, nullptr, LOAD_NoWarn | LOAD_Quiet);
	if (!PuppetClass)
	{
		// The licensed Fab pack is optional; the NPC keeps its native GX cast avatar.
		return false;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Params.Owner = Owner;
	Params.OverrideLevel = Owner->GetLevel();
	AActor* NewPuppet = World->SpawnActor<AActor>(PuppetClass, Owner->GetActorLocation(),
		Owner->GetActorRotation(), Params);
	if (!NewPuppet)
	{
		return false;
	}

	NewPuppet->SetActorEnableCollision(false);
	if (APawn* Pawn = Cast<APawn>(NewPuppet))
	{
		Pawn->AutoPossessAI = EAutoPossessAI::Disabled;
		if (AController* Controller = Pawn->GetController())
		{
			Controller->UnPossess();
		}
	}

	NewPuppet->AttachToActor(Owner, FAttachmentTransformRules::KeepWorldTransform);

	if (ACharacter* PuppetCharacter = Cast<ACharacter>(NewPuppet))
	{
		if (UCharacterMovementComponent* Movement = PuppetCharacter->GetCharacterMovement())
		{
			// The pack's ABP derives "In Air" from IsFalling (false in MOVE_None as
			// well as MOVE_Walking); MOVE_Walking additionally keeps IsMovingOnGround
			// true for ABP variants that read it.  The component is not ticked, so it
			// never integrates our synthetic velocity or moves the attached puppet.
			Movement->SetMovementMode(MOVE_Walking);
			Movement->SetComponentTickEnabled(false);
		}
	}

	if (!ApplyLook(NewPuppet, *Look))
	{
		NewPuppet->Destroy();
		return false;
	}

	Puppet = NewPuppet;
	ActiveLook = LookId;
	HideNativeAvatar(true);
	SetComponentTickEnabled(true);
	bRefreshLookOnTick = true;
	UE_LOG(LogTemp, Log, TEXT("DAFabAnime: %s -> %s"), *Owner->GetName(), *LookId);

	// The pack's shading component creates its outline MIDs during BeginPlay;
	// re-apply once so our mesh/material swap wins regardless of spawn order.
	World->GetTimerManager().SetTimer(RefreshTimer, this, &UDAFabAnimeComponent::RefreshLook, 0.3f, false);
	return true;
}

void UDAFabAnimeComponent::DeactivateLook()
{
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(RefreshTimer);
	}
	if (AActor* OldPuppet = Puppet.Get())
	{
		OldPuppet->Destroy();
	}
	Puppet.Reset();
	ActiveLook.Empty();
	bRefreshLookOnTick = false;
	HideNativeAvatar(false);
	SetComponentTickEnabled(false);
}

void UDAFabAnimeComponent::RefreshPuppetLook()
{
	RefreshLook();
}

bool UDAFabAnimeComponent::IsPuppetMovementTickEnabled() const
{
	if (const AActor* ActivePuppet = Puppet.Get())
	{
		if (const ACharacter* Character = Cast<ACharacter>(ActivePuppet))
		{
			if (const UCharacterMovementComponent* Movement = Character->GetCharacterMovement())
			{
				return Movement->IsComponentTickEnabled();
			}
		}
	}
	return false;
}

void UDAFabAnimeComponent::RefreshLook()
{
	if (!Puppet.IsValid())
	{
		return;
	}
	if (const FDAFabAnimeLook* Look = FindLook(ActiveLook))
	{
		ApplyLook(Puppet.Get(), *Look);
	}
}

bool UDAFabAnimeComponent::ApplyLook(AActor* InPuppet, const FDAFabAnimeLook& Look)
{
	USkeletalMeshComponent* Head = FindSkeletal(InPuppet, TEXT("CharacterMesh0"));
	USkeletalMeshComponent* Hair = FindSkeletal(InPuppet, TEXT("Hair"));
	USkeletalMeshComponent* Top = FindSkeletal(InPuppet, TEXT("Top"));
	USkeletalMeshComponent* Bottom = FindSkeletal(InPuppet, TEXT("Bottom"));
	if (!Head || !Hair || !Top || !Bottom)
	{
		UE_LOG(LogTemp, Warning,
			TEXT("DAFabAnime: bp_AnimeCharacter is missing one of CharacterMesh0/Hair/Top/Bottom"));
		return false;
	}

	USkeletalMesh* HeadMesh = LoadMesh(Look.HeadMesh);
	USkeletalMesh* HairMesh = LoadMesh(Look.HairMesh);
	USkeletalMesh* TopMesh = LoadMesh(Look.TopMesh);
	USkeletalMesh* BottomMesh = LoadMesh(Look.BottomMesh);
	if (!HeadMesh || !HairMesh || !TopMesh || !BottomMesh)
	{
		UE_LOG(LogTemp, Warning, TEXT("DAFabAnime: look '%s' is missing a mesh"), Look.Id);
		return false;
	}

	Head->SetSkeletalMeshAsset(HeadMesh);
	Hair->SetSkeletalMeshAsset(HairMesh);
	Top->SetSkeletalMeshAsset(TopMesh);
	Bottom->SetSkeletalMeshAsset(BottomMesh);

	// Match the owner's native avatar height.  The pack's UE4-Mannequin bodies are
	// authored at about 200 cm (male) / 187 cm (female), while the GX cast is built
	// at real heights (153-186 cm plus the NPCs' deterministic +/-5 % variation).
	// Scale the body-part components rather than the actor: their relative Z stays at
	// the host's floor (-avatar offset) and Hair / outline children inherit the same
	// scale, so the puppet never floats or sinks.
	const AActor* Owner = GetOwner();
	const UDAAvatarComponent* Avatar = Owner
		? Owner->FindComponentByClass<UDAAvatarComponent>() : nullptr;
	const float TargetHeight = Avatar ? Avatar->GetStandingHeight() : 170.f;
	float MeshZ = Avatar ? Avatar->GetRelativeLocation().Z : -90.f;
	if (FMath::IsNearlyZero(MeshZ))
	{
		if (const UCapsuleComponent* HostCapsule = Owner
			? Owner->FindComponentByClass<UCapsuleComponent>() : nullptr)
		{
			MeshZ = -HostCapsule->GetScaledCapsuleHalfHeight();
		}
	}

	// Measure the assembled bind-pose height from every visible part, including the
	// hair (the female styles can rise well above the skull).  Reset the parts to
	// scale 1 first so the measurement is idempotent when RefreshLook() runs again.
	const bool bHairChild = Hair->IsAttachedTo(Head);
	const FVector UnitScale(1.f);
	Head->SetRelativeScale3D(UnitScale);
	Top->SetRelativeScale3D(UnitScale);
	Bottom->SetRelativeScale3D(UnitScale);
	if (!bHairChild)
	{
		Hair->SetRelativeScale3D(UnitScale);
	}
	TArray<USkeletalMeshComponent*> PositionedParts = { Head, Top, Bottom };
	if (!bHairChild)
	{
		PositionedParts.Add(Hair);
	}
	for (USkeletalMeshComponent* Part : PositionedParts)
	{
		FVector Location = Part->GetRelativeLocation();
		if (!FMath::IsNearlyEqual(Location.Z, MeshZ, 0.1f))
		{
			Location.Z = MeshZ;
			Part->SetRelativeLocation(Location);
		}
	}

	const FTransform ActorTransform = InPuppet->GetActorTransform();
	float BaseHeight = 0.f;
	for (USkeletalMeshComponent* Part : { Head, Hair, Top, Bottom })
	{
		const USkeletalMesh* Mesh = Part ? Part->GetSkeletalMeshAsset() : nullptr;
		if (!Mesh)
		{
			continue;
		}
		const FBoxSphereBounds WorldBounds =
			Mesh->GetImportedBounds().TransformBy(Part->GetComponentTransform());
		const float WorldTop = WorldBounds.Origin.Z + WorldBounds.BoxExtent.Z;
		const float ActorTop = ActorTransform.InverseTransformPosition(FVector(0.f, 0.f, WorldTop)).Z;
		BaseHeight = FMath::Max(BaseHeight, ActorTop - MeshZ);
	}
	const float HeightScale = (BaseHeight > 1.f && TargetHeight > 1.f)
		? FMath::Clamp(TargetHeight / BaseHeight, 0.5f, 1.5f)
		: 1.f;
	const FVector PartScale(HeightScale);
	Head->SetRelativeScale3D(PartScale);
	Top->SetRelativeScale3D(PartScale);
	Bottom->SetRelativeScale3D(PartScale);
	if (!bHairChild)
	{
		Hair->SetRelativeScale3D(PartScale);
	}

	// Keep the pack's outline components in sync with the swapped meshes.  They are
	// generated children of each visible part (SkeletalMeshComponent_0..3) and must
	// follow that part's animated pose, so pair by parent and use it as leader pose.
	UMaterialInterface* OutlineBase = LoadMaterial(OutlineMaterial);
	TSet<USkeletalMeshComponent*> PairedOutlines;
	auto ApplyOutline = [OutlineBase, InPuppet, &PairedOutlines](USkeletalMeshComponent* Main, USkeletalMesh* Mesh)
	{
		USkeletalMeshComponent* Outline = FindOutline(InPuppet, Main);
		if (!Outline || !Mesh)
		{
			return;
		}
		PairedOutlines.Add(Outline);
		Outline->SetSkeletalMeshAsset(Mesh);
		Outline->SetLeaderPoseComponent(Main, true);
		if (OutlineBase)
		{
			if (UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(OutlineBase, Outline))
			{
				MID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.02f, 0.02f, 0.025f, 1.0f));
				MID->SetScalarParameterValue(TEXT("Thickness"), 0.075f);
				MID->SetScalarParameterValue(TEXT("Min"), 1.0f);
				MID->SetScalarParameterValue(TEXT("Max"), 2.5f);
				for (int32 Index = 0; Index < Outline->GetNumMaterials(); ++Index)
				{
					Outline->SetMaterial(Index, MID);
				}
			}
		}
		Outline->SetVisibility(true, true);
	};
	ApplyOutline(Head, HeadMesh);
	ApplyOutline(Top, TopMesh);
	ApplyOutline(Bottom, BottomMesh);
	ApplyOutline(Hair, HairMesh);

	// Top and Bottom are separate garment meshes driven by the pack's abp_Subsegment
	// (a copy-pose graph that reads CharacterMesh0 through the pack's animation
	// interface).  Leave their own AnimBlueprint in charge; forcing a leader pose here
	// makes this pack clear their skeletal mesh assets.

	// A failed pairing must never leave the pack's default male outline shells visible.
	TArray<USkeletalMeshComponent*> AllComponents;
	InPuppet->GetComponents<USkeletalMeshComponent>(AllComponents);
	for (USkeletalMeshComponent* Component : AllComponents)
	{
		if (Component && !PairedOutlines.Contains(Component)
			&& Component->GetFName().ToString().StartsWith(TEXT("SkeletalMeshComponent_")))
		{
			Component->SetVisibility(false, true);
		}
	}

	UE_LOG(LogTemp, Log, TEXT("DAFabAnime: %s scale %.3f (target %.1f cm / base %.1f cm)"),
		Look.Id, HeightScale, TargetHeight, BaseHeight);

	// Face material (two built-in faces per gender).
	if (UMaterialInterface* HeadMaterial = LoadMaterial(Look.HeadMaterial))
	{
		const TArray<FName> Slots = Head->GetMaterialSlotNames();
		for (int32 Index = 0; Index < Slots.Num(); ++Index)
		{
			const FString Slot = Slots[Index].ToString();
			if (Slot.Contains(TEXT("Head"), ESearchCase::IgnoreCase)
				|| Slot.Contains(TEXT("Skin"), ESearchCase::IgnoreCase))
			{
				Head->SetMaterial(Index, HeadMaterial);
			}
		}
	}

	// Hair tint keeps the pack's layered hair shader and physics.
	if (UMaterialInterface* HairBase = LoadMaterial(HairBaseMaterial))
	{
		if (UMaterialInstanceDynamic* HairMID = UMaterialInstanceDynamic::Create(HairBase, Hair))
		{
			HairMID->SetVectorParameterValue(TEXT("Hair Color"), Look.HairColor);
			HairMID->SetVectorParameterValue(TEXT("GradientColor"), Look.HairColor * 0.72f);
			HairMID->SetVectorParameterValue(TEXT("HairShadowColor"), Look.HairColor * 0.60f);
			HairMID->SetVectorParameterValue(TEXT("OutlineColor"), Look.HairColor * 0.20f);
			HairMID->SetVectorParameterValue(TEXT("RimlightColor"), FLinearColor::White);
			HairMID->SetScalarParameterValue(TEXT("Gradient Intensity"), 1.0f);
			HairMID->SetScalarParameterValue(TEXT("ShadowDepth"), 0.0f);
			for (int32 Index = 0; Index < Hair->GetNumMaterials(); ++Index)
			{
				Hair->SetMaterial(Index, HairMID);
			}
		}
	}

	// Casual clothes take the NPC's dorm colour so the pack looks at home on the island.
	FLinearColor Cloth = FLinearColor(0.20f, 0.20f, 0.22f, 1.0f);
	if (const ADAStudentNPC* Npc = Cast<ADAStudentNPC>(GetOwner()))
	{
		Cloth = DuelAcademy::DormColor(Npc->Dorm);
	}
	TintClothing(Top, Cloth);
	TintClothing(Bottom, Cloth);

	Head->SetVisibility(true, true);
	Hair->SetVisibility(true, true);
	Top->SetVisibility(true, true);
	Bottom->SetVisibility(true, true);
	return true;
}

void UDAFabAnimeComponent::HideNativeAvatar(bool bHide)
{
	AActor* Owner = GetOwner();
	if (!Owner)
	{
		return;
	}
	UDAAvatarComponent* Avatar = Owner->FindComponentByClass<UDAAvatarComponent>();
	ACharacter* Host = Cast<ACharacter>(Owner);
	USkeletalMeshComponent* HostMesh = Host ? Host->GetMesh() : nullptr;

	if (bHide)
	{
		if (bNativeHidden)
		{
			return;
		}
		bWasAvatarVisible = Avatar ? Avatar->IsVisible() : true;
		bWasAvatarTickEnabled = Avatar ? Avatar->IsComponentTickEnabled() : true;
		bWasHostMeshVisible = HostMesh ? HostMesh->IsVisible() : false;
		if (Avatar)
		{
			Avatar->SetVisibility(false, true);
			Avatar->SetComponentTickEnabled(false);
			Avatar->SetSkeletalTickEnabled(false);
		}
		if (HostMesh)
		{
			HostMesh->SetVisibility(false, true);
		}
		bNativeHidden = true;
	}
	else
	{
		if (!bNativeHidden)
		{
			return;
		}
		if (Avatar)
		{
			Avatar->SetVisibility(bWasAvatarVisible, true);
			Avatar->SetComponentTickEnabled(bWasAvatarTickEnabled);
			Avatar->SetSkeletalTickEnabled(true);
		}
		if (HostMesh)
		{
			// ADAStudentNPC hides its inherited ACharacter mesh in the constructor; do
			// not re-show it on deactivation just because we once hid it.
			HostMesh->SetVisibility(bWasHostMeshVisible, true);
		}
		bNativeHidden = false;
	}
}

void UDAFabAnimeComponent::TickComponent(float DeltaTime, ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	AActor* Owner = GetOwner();
	AActor* ActivePuppet = Puppet.Get();
	if (!Owner || !ActivePuppet)
	{
		return;
	}

	// The pack creates/refreshes some of its components during BeginPlay; re-apply once
	// on the first tick so the swapped meshes are present before the first visible frame.
	if (bRefreshLookOnTick)
	{
		bRefreshLookOnTick = false;
		RefreshLook();
	}

	// The puppet is attached and does not move itself; feed it the host velocity so
	// the pack's locomotion blueprint blends idle / walk / run with the real stride.
	if (ACharacter* PuppetCharacter = Cast<ACharacter>(ActivePuppet))
	{
		if (UCharacterMovementComponent* Movement = PuppetCharacter->GetCharacterMovement())
		{
			FVector HostVelocity = Owner->GetVelocity();
			// The puppet is in a grounded locomotion state; a jumping/falling host's Z
			// velocity must not turn into a "walking in air" speed spike in the ABP.
			HostVelocity.Z = 0.f;
			Movement->Velocity = HostVelocity;
			Movement->UpdateComponentVelocity();
		}
	}
}
