// Duel Academy Island - cosmetic anime puppet built from the licensed Fab Anime Character Pack.

#include "DAFabAnimePuppet.h"

#include "DAAvatarComponent.h"
#include "DAStudentNPC.h"
#include "Components/SkeletalMeshComponent.h"
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
	SetComponentTickEnabled(false);
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

	DeactivateLook();

	const FDAFabAnimeLook* Look = FindLook(LookId);
	if (!Look)
	{
		UE_LOG(LogTemp, Warning, TEXT("DAFabAnime: unknown look '%s'"), *LookId);
		return false;
	}

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
	if (ACharacter* PuppetCharacter = Cast<ACharacter>(NewPuppet))
	{
		if (UCharacterMovementComponent* Movement = PuppetCharacter->GetCharacterMovement())
		{
			Movement->DisableMovement();
			Movement->SetComponentTickEnabled(false);
		}
	}

	NewPuppet->AttachToActor(Owner, FAttachmentTransformRules::KeepWorldTransform);

	if (!ApplyLook(NewPuppet, *Look))
	{
		NewPuppet->Destroy();
		return false;
	}

	Puppet = NewPuppet;
	ActiveLook = LookId;
	HideNativeAvatar(true);
	SetComponentTickEnabled(true);
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
	HideNativeAvatar(false);
	SetComponentTickEnabled(false);
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

	// Keep the pack's outline components in sync with the swapped meshes.  The
	// mesh swap resets material overrides, so re-apply the outline material too.
	UMaterialInterface* OutlineBase = LoadMaterial(OutlineMaterial);
	auto ApplyOutline = [OutlineBase](USkeletalMeshComponent* Component, USkeletalMesh* Mesh)
	{
		if (!Component || !Mesh)
		{
			return;
		}
		Component->SetSkeletalMeshAsset(Mesh);
		if (OutlineBase)
		{
			if (UMaterialInstanceDynamic* MID = UMaterialInstanceDynamic::Create(OutlineBase, Component))
			{
				MID->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.02f, 0.02f, 0.025f, 1.0f));
				MID->SetScalarParameterValue(TEXT("Thickness"), 0.075f);
				MID->SetScalarParameterValue(TEXT("Min"), 1.0f);
				MID->SetScalarParameterValue(TEXT("Max"), 2.5f);
				for (int32 Index = 0; Index < Component->GetNumMaterials(); ++Index)
				{
					Component->SetMaterial(Index, MID);
				}
			}
		}
		Component->SetVisibility(true, true);
	};
	ApplyOutline(FindSkeletal(InPuppet, TEXT("SkeletalMeshComponent_4")), HeadMesh);
	ApplyOutline(FindSkeletal(InPuppet, TEXT("SkeletalMeshComponent_5")), TopMesh);
	ApplyOutline(FindSkeletal(InPuppet, TEXT("SkeletalMeshComponent_6")), BottomMesh);
	ApplyOutline(FindSkeletal(InPuppet, TEXT("SkeletalMeshComponent_7")), HairMesh);

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
	if (UDAAvatarComponent* Avatar = Owner->FindComponentByClass<UDAAvatarComponent>())
	{
		Avatar->SetVisibility(!bHide, true);
		Avatar->SetComponentTickEnabled(!bHide);
	}
	if (ACharacter* Host = Cast<ACharacter>(Owner))
	{
		if (USkeletalMeshComponent* Mesh = Host->GetMesh())
		{
			Mesh->SetVisibility(!bHide, true);
		}
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

	// The puppet is attached and does not move itself; feed it the host velocity so
	// the pack's locomotion blueprint blends idle / walk / run with the real stride.
	if (ACharacter* PuppetCharacter = Cast<ACharacter>(ActivePuppet))
	{
		if (UCharacterMovementComponent* Movement = PuppetCharacter->GetCharacterMovement())
		{
			Movement->Velocity = Owner->GetVelocity();
		}
	}
}
