// Duel Academy Island - procedural student avatar (static mesh parts + code animation).

#pragma once

#include "CoreMinimal.h"
#include "Components/SceneComponent.h"
#include "DATypes.h"
#include "DAAvatarComponent.generated.h"

class UStaticMeshComponent;
class UStaticMesh;
class UMaterialInstanceDynamic;
class USkeletalMeshComponent;
class UAnimSequence;

/**
 * Student avatar, best available first:
 *  1. the anime cast (Tools/dai/anime, imported by the editor build script): SK_Anime_<Name> with the
 *     A_Anime_<Group>_<State> takes of its skeleton group and the group's duel disk;
 *  2. the curated CC0 student (SK_Student + A_Student_* sequences);
 *  3. the procedural SM_Avatar_* part meshes animated in code - no assets required.
 * Skeletal avatars are driven from the owner's velocity. The anime cast uses the native
 * DAAvatarAnimInstance (phase-synced idle/walk/run blend + crossfaded actions); SK_Student uses
 * single-node playback.
 *
 * Attach it at the bottom of the capsule; it faces the owner's +X.
 */
UCLASS(ClassGroup = (DuelAcademy), meta = (BlueprintSpawnableComponent))
class DUELACADEMYISLAND_API UDAAvatarComponent : public USceneComponent
{
	GENERATED_BODY()

public:
	UDAAvatarComponent();

	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetDorm(EDADorm NewDorm);

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	EDADorm GetDorm() const { return Dorm; }

	/** 0 = not swimming, 1 = fully swimming (blends the body horizontal). */
	UPROPERTY(Transient, BlueprintReadWrite, Category = "Duel Academy")
	float SwimAlpha = 0.f;

	/** 0..1 dueling pose (duel disk arm raised). */
	UPROPERTY(Transient, BlueprintReadWrite, Category = "Duel Academy")
	float DuelPoseAlpha = 0.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	EDADorm Dorm = EDADorm::Slifer;

	/** Scale of the whole figure (NPC variety). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float BodyScale = 1.f;

	/** Speed (cm/s) at which the walk cycle reaches a full stride. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float StrideSpeed = 600.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	bool bShowDuelDisk = true;

	/** Hair colour variation for NPCs. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FLinearColor HairColor = FLinearColor(0.12f, 0.035f, 0.01f);

	/** Use a skeletal character (anime cast / SK_Student) when one has been imported. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	bool bPreferSkeletal = true;

	/** Anime cast mesh in /Game/DuelAcademy/Characters (SK_Anime_<Name>, see SourceAssets/Data/cast.json). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString CastMesh = TEXT("SK_Anime_StudentM1");

	/** Skeleton group of CastMesh: its takes are A_Anime_<AnimGroup>_<State>, its disk SK_Anime_<AnimGroup>_DuelDisk. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	FString AnimGroup = TEXT("VroidC");

	/** Recolour the cast mesh's "JacketTint" slots by dorm and "HairTint" slots with HairColor (generic
	 *  students); named characters keep their own colours. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	bool bDormTint = true;

	/** Ground speed (cm/s) at which the walk / run takes play at rate 1 (no foot sliding). The defaults fit the
	 *  anime cast's authored takes (1.50 m/s walk, 4.20 m/s run); the SK_Student fallback switches to the
	 *  speeds its import normalises its clips to (RateScale, measured per rig by Tools/dai/character.py). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float WalkAnimSpeed = 150.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float RunAnimSpeed = 420.f;

	/** Above this ground speed (cm/s) the single-node SK_Student fallback runs instead of walking; 0 =
	 *  halfway between WalkAnimSpeed and RunAnimSpeed plus 60. The anime cast blends Walk and Run by
	 *  speed and ignores this. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float RunThreshold = 0.f;

	/** Material slot name fragments recoloured with the dorm colour on the skeletal student. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	TArray<FString> JacketSlotKeywords = { TEXT("jacket"), TEXT("blazer"), TEXT("coat"), TEXT("shirt"), TEXT("uniform"), TEXT("top") };

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	bool IsSkeletal() const { return SkelComp != nullptr; }

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	bool IsAnimeCast() const { return bAnimeCast; }

private:
	bool SetupSkeletal();
	bool SetupCast();
	void FinishSkeletal(class USkeletalMesh* Mesh);
	void TickSkeletal(float DeltaTime, float GroundSpeed, bool bInAir);
	void TickNative(float DeltaTime, float GroundSpeed, bool bInAir, float VerticalSpeed);
	void TickSingleNode(float DeltaTime, float GroundSpeed, bool bInAir);
	UAnimSequence* FindAnim(FName State) const;
	UStaticMeshComponent* MakePart(const TCHAR* MeshName, USceneComponent* Parent, const FVector& Offset);
	void ApplyColours();

	UPROPERTY(Transient)
	TObjectPtr<USceneComponent> Pelvis;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Torso;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Head;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> ArmL;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> ArmR;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> LegL;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> LegR;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMeshComponent> Disk;

	UPROPERTY(Transient)
	TArray<TObjectPtr<UMaterialInstanceDynamic>> JacketMaterials;

	UPROPERTY(Transient)
	TObjectPtr<USkeletalMeshComponent> SkelComp;

	UPROPERTY(Transient)
	TObjectPtr<USkeletalMeshComponent> DiskComp;

	UPROPERTY(Transient)
	TMap<FName, TObjectPtr<UAnimSequence>> Anims;

	bool bAnimeCast = false;

	FName CurrentAnim = NAME_None;
	FName CurrentAction = NAME_None;
	float LandTimer = 0.f;
	bool bWasInAir = false;

	float Phase = 0.f;
	float SmoothedSpeed = 0.f;
	float AirAlpha = 0.f;
	float Time = 0.f;
	float BreathPhase = 0.f;
};
