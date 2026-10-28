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
 * Student avatar. If the curated CC0 character (SK_Student + A_Student_* animation
 * sequences, imported by the editor build script) is present, it is used with real
 * skeletal animation driven from the owner's velocity. Otherwise the avatar is built
 * from the procedural SM_Avatar_* part meshes and animated in code
 * (walk/run/idle/jump/swim) - no animation assets required.
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

	/** Use the skeletal student (SK_Student) when it has been imported. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	bool bPreferSkeletal = true;

	/** Ground speed (cm/s) the Walk / Run clips cover at play rate 1. The editor import normalises every clip to
	 *  these via its RateScale (measured per rig by Tools/dai/character.py), so feet don't skate. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float WalkAnimSpeed = 300.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float RunAnimSpeed = 600.f;

	/** Above this ground speed (cm/s) the skeletal student runs instead of walking. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float RunThreshold = 560.f;

	/** Material slot name fragments recoloured with the dorm colour on the skeletal student. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	TArray<FString> JacketSlotKeywords = { TEXT("jacket"), TEXT("blazer"), TEXT("coat"), TEXT("shirt"), TEXT("uniform"), TEXT("top") };

	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	bool IsSkeletal() const { return SkelComp != nullptr; }

private:
	bool SetupSkeletal();
	void TickSkeletal(float DeltaTime, float GroundSpeed, bool bInAir);
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
	TMap<FName, TObjectPtr<UAnimSequence>> Anims;

	FName CurrentAnim = NAME_None;

	float Phase = 0.f;
	float SmoothedSpeed = 0.f;
	float AirAlpha = 0.f;
	float Time = 0.f;
	float BreathPhase = 0.f;
};
