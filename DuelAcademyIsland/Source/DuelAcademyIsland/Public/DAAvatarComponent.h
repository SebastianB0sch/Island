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
struct FDARiderIKTargets;

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

	/** 0 = on foot, 1 = seated on the motorcycle (the owner attaches the avatar to the bike's rider mount). */
	UPROPERTY(Transient, BlueprintReadWrite, Category = "Duel Academy")
	float RideAlpha = 0.f;

	/** While riding: height (cm above the avatar's origin) at which the hips sit on the seat. Used by the
	 *  avatars without the rider IK (SK_Student's Sit take, the procedural parts). */
	UPROPERTY(Transient, BlueprintReadWrite, Category = "Duel Academy")
	float RideHipHeight = 108.f;

	/** While riding: this frame's seat, grips, pegs and riding style from the motorcycle (UDAMotorcycleComponent::
	 *  GetRiderTargets), in the attach parent's (rider mount's) space. The anime cast IKs onto them
	 *  (UDAAvatarAnimInstance::SetRider); the procedural parts aim their limbs at the grips and pegs. */
	void SetRideTargets(const FDARiderTargets& InTargets) { RideTargets = InTargets; }

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	EDADorm Dorm = EDADorm::Slifer;

	/** Scale of the whole figure (NPC variety). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float BodyScale = 1.f;

	/** Procedural fallback only: speed (cm/s) of its reference walk (1.0 s cycle, 0.75 m steps at
	 *  BodyScale 1). Its cadence and stride are solved from the ground speed with the same human
	 *  cadence model as the anime cast, so the feet travel exactly as fast as the body. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float StrideSpeed = 150.f;

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

	/** Ground speed (cm/s) at which the walk / run takes play at rate 1 (no foot sliding). The defaults fit
	 *  the procedural gait takes (1.50 m/s walk, 4.20 m/s run). When the local Fab locomotion retarget is
	 *  installed, SetupCast detects the longer 1.17 s / 0.63 s clips and uses their measured planted-foot
	 *  reference speeds (about 1.33-1.58 m/s walk and 5.55-6.59 m/s sprint, per skeleton group). The
	 *  SK_Student fallback switches to the speeds its import normalises its clips to (RateScale, measured
	 *  per rig by Tools/dai/character.py). */
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

	/** Visible standing height of the active avatar in cm (imported bind-pose bounds including hair,
	 *  multiplied by the avatar's actual scale).  Returns a nominal 170 cm * BodyScale for the
	 *  procedural fallback, so optional puppets can always match the owner's size. */
	UFUNCTION(BlueprintPure, Category = "Duel Academy")
	float GetStandingHeight() const;

	/** Enable/disable the skeletal mesh's animation tick (the Fab puppet hides it while active). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetSkeletalTickEnabled(bool bEnabled);

	/** Anime cast only: mouth visemes while talking (UDAAvatarAnimInstance face layer). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetTalking(bool bTalking);

	/** Anime cast only: turn the head towards a world location (false eases back). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetLookAt(const FVector& WorldLocation, bool bEnable);

	/** Anime cast only: Joy / Angry / Sorrow / Surprised / Fun, 0..1 (NAME_None clears). */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	void SetEmotion(FName Emotion, float Weight);

	/** Current locomotion contact phase, 0..1 (0 and 0.5 are the two foot plants). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Animation")
	float GetLocomotionPhase() const;

	/** Locomotion cycles per second currently shown (two foot contacts per cycle). */
	UFUNCTION(BlueprintPure, Category = "Duel Academy|Animation")
	float GetLocomotionCadence() const;

	/** Play a one-shot gesture take (Wave, Yes, No, Clap, Interact...) while standing. It is
	 *  skipped while walking, airborne, swimming or dueling, and fades out as soon as the
	 *  character starts moving, so it can never freeze the legs over the ground. Returns false
	 *  when the take is missing or the character is busy. */
	UFUNCTION(BlueprintCallable, Category = "Duel Academy")
	bool PlayGesture(FName State);

	/** Swim speed (cm/s) at which A_Anime_<Group>_Swim plays at rate 1: one stroke cycle
	 *  (1.6 s) moves the body about 2 m, a relaxed front crawl. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Duel Academy")
	float SwimAnimSpeed = 125.f;

private:
	/** SetTalking: plays the Talk gesture take while standing. */
	bool bSpeaking = false;

	bool SetupSkeletal();
	bool SetupCast();
	void FinishSkeletal(class USkeletalMesh* Mesh);
	void TickSkeletal(float DeltaTime, float GroundSpeed, bool bInAir);
	void TickNative(float DeltaTime, float GroundSpeed, bool bInAir, float VerticalSpeed);
	void TickSingleNode(float DeltaTime, float GroundSpeed, bool bInAir);
	UAnimSequence* FindAnim(FName State) const;
	/** Pelvis height of the current skeletal pose in component space (cm), or a pose-based guess. */
	float MeasurePelvisHeight();
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

	void UpdateBodyLean(float DeltaTime, float GroundSpeed);

	/** Whether the skeletal mesh has the bones the rider IK needs (checked once per mesh). */
	bool HasRiderRig();
	/** The bike's targets converted to the mesh's component space for the rider IK. */
	bool MakeRiderIK(FDARiderIKTargets& Out) const;
	/** Procedural parts: point the arms at the grips and the legs at the pegs. */
	void AimRiderLimbs();

	FDARiderTargets RideTargets;
	/** 0..1 blend onto the bike (a quick hop on after mounting). */
	float RideBlend = 0.f;
	/** The rider IK drives the anime cast this frame (no Sit take, no lift). */
	bool bRiderIK = false;
	int8 RiderRigState = -1;   // -1 unknown, 0 no, 1 yes

	FName CurrentAnim = NAME_None;
	FName CurrentAction = NAME_None;
	float LandTimer = 0.f;
	float LandWeight = 0.f;
	float LastAirVerticalSpeed = 0.f;
	float AirTime = 0.f;
	float JumpRate = 1.f;
	bool bWasInAir = false;
	bool bJumped = false;

	/** Swimming: 0 = treading water upright, 1 = horizontal crawl (follows the swim speed). */
	float SwimMoveAlpha = 0.f;
	bool bSwimStroke = false;

	FName PendingGesture = NAME_None;
	FName ActiveGesture = NAME_None;
	float GestureTime = 0.f;

	/** Whole-body lean (deg) into turns and against acceleration, about the feet. */
	float LeanSide = 0.f;
	float LeanForward = 0.f;
	float LastYaw = 0.f;
	float LastGroundSpeed = 0.f;
	bool bHasLastYaw = false;

	float Phase = 0.f;
	/** Cadence solved by the procedural gait (cycles per second). */
	float GaitCadence = 0.f;
	float RideLift = 0.f;
	FName PelvisBone = NAME_None;
	bool bPelvisSearched = false;
	float SmoothedSpeed = 0.f;
	float StepAmplitude = 0.f;
	float SwimCycle = 0.f;
	float AirAlpha = 0.f;
	float Time = 0.f;
	float BreathPhase = 0.f;
};
