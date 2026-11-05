// Duel Academy Island - procedural student avatar.

#include "DAAvatarComponent.h"

#include "Animation/AnimSequence.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DAAvatarAnimInstance.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace
{
	// Joint layout of the SM_Avatar_* parts (cm, avatar space: +Y forward before the -90 yaw).
	const FVector HipHeight(0.0, 0.0, 93.0);
	const FVector HeadJoint(0.0, 0.0, 56.0);
	const FVector ArmLJoint(-21.0, 0.0, 48.0);
	const FVector ArmRJoint(21.0, 0.0, 48.0);
	const FVector LegLJoint(-9.0, 0.0, 0.0);
	const FVector LegRJoint(9.0, 0.0, 0.0);
	const FVector DiskOnArm(-4.0, 0.0, -40.0);
}

UDAAvatarComponent::UDAAvatarComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.bStartWithTickEnabled = true;
	// The part meshes are authored facing UE +Y (Blender -Y); turn them to face the owner's +X.
	SetRelativeRotation(FRotator(0.f, -90.f, 0.f));
}

UStaticMeshComponent* UDAAvatarComponent::MakePart(const TCHAR* MeshName, USceneComponent* Parent, const FVector& Offset)
{
	const FString Path = FString::Printf(TEXT("%s%s.%s"), DuelAcademy::AvatarFolder, MeshName, MeshName);
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *Path, nullptr, LOAD_NoWarn | LOAD_Quiet);

	UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(GetOwner(), NAME_None, RF_Transient);
	C->SetupAttachment(Parent);
	C->SetRelativeLocation(Offset);
	C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	C->SetGenerateOverlapEvents(false);
	C->SetCanEverAffectNavigation(false);
	C->bCastDynamicShadow = true;
	C->CastShadow = true;
	if (Mesh)
	{
		C->SetStaticMesh(Mesh);
	}
	C->RegisterComponent();
	return C;
}

namespace
{
	const TCHAR* CharacterFolder = TEXT("/Game/DuelAcademy/Characters/");

	template <typename T>
	T* LoadCharacterAsset(const FString& Name)
	{
		return LoadObject<T>(nullptr, *FString::Printf(TEXT("%s%s.%s"), CharacterFolder, *Name, *Name), nullptr, LOAD_NoWarn | LOAD_Quiet);
	}
}

void UDAAvatarComponent::FinishSkeletal(USkeletalMesh* Mesh)
{
	SkelComp = NewObject<USkeletalMeshComponent>(GetOwner(), NAME_None, RF_Transient);
	SkelComp->SetupAttachment(this);
	SkelComp->SetSkeletalMeshAsset(Mesh);
	SkelComp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	SkelComp->SetGenerateOverlapEvents(false);
	SkelComp->SetCanEverAffectNavigation(false);
	SkelComp->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	SkelComp->RegisterComponent();
	// the duel disk is skinned into the mesh (slots MT_Student_Duel*); hide it for students without one
	if (!bShowDuelDisk)
	{
		const TArray<FName> Slots = SkelComp->GetMaterialSlotNames();
		for (int32 i = 0; i < Slots.Num(); ++i)
		{
			if (Slots[i].ToString().Contains(TEXT("Duel")))
			{
				SkelComp->ShowMaterialSection(i, INDEX_NONE, false, 0);
			}
		}
	}
	SetRelativeScale3D(FVector(BodyScale));
}

bool UDAAvatarComponent::SetupCast()
{
	if (CastMesh.IsEmpty() || AnimGroup.IsEmpty())
	{
		return false;
	}
	USkeletalMesh* Mesh = LoadCharacterAsset<USkeletalMesh>(CastMesh);
	if (!Mesh)
	{
		return false;
	}
	for (const TCHAR* State : { TEXT("Idle"), TEXT("Walk"), TEXT("Run"), TEXT("Jump"), TEXT("Fall"), TEXT("Land"), TEXT("Swim"),
		TEXT("Tread"), TEXT("Wave"), TEXT("Duel"), TEXT("Sit"), TEXT("Yes"), TEXT("No"), TEXT("Clap"), TEXT("Interact") })
	{
		if (UAnimSequence* Seq = LoadCharacterAsset<UAnimSequence>(FString::Printf(TEXT("A_Anime_%s_%s"), *AnimGroup, State)))
		{
			Anims.Add(FName(State), Seq);
		}
	}
	if (!Anims.Contains(TEXT("Idle")))
	{
		Anims.Reset();
		return false;
	}
	FinishSkeletal(Mesh);
	bAnimeCast = true;
	// Native phase-synced locomotion graph (Idle/Walk/Run + crossfaded actions) on the cast skeleton.
	SkelComp->SetAnimationMode(EAnimationMode::AnimationBlueprint);
	SkelComp->SetAnimInstanceClass(UDAAvatarAnimInstance::StaticClass());
	if (!SkelComp->GetAnimInstance())
	{
		SkelComp->InitializeAnimScriptInstance(true);
	}
	if (UDAAvatarAnimInstance* Inst = Cast<UDAAvatarAnimInstance>(SkelComp->GetAnimInstance()))
	{
		Inst->Configure(Anims, WalkAnimSpeed * BodyScale, RunAnimSpeed * BodyScale);
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("DAAvatar: %s has no native anim instance; falling back to single-node playback"), *GetName());
	}
	if (bShowDuelDisk)
	{
		if (USkeletalMesh* DiskMesh = LoadCharacterAsset<USkeletalMesh>(FString::Printf(TEXT("SK_Anime_%s_DuelDisk"), *AnimGroup)))
		{
			// same skeleton: the disk follows the body's pose
			DiskComp = NewObject<USkeletalMeshComponent>(GetOwner(), NAME_None, RF_Transient);
			DiskComp->SetupAttachment(SkelComp);
			DiskComp->SetSkeletalMeshAsset(DiskMesh);
			DiskComp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			DiskComp->SetCanEverAffectNavigation(false);
			DiskComp->RegisterComponent();
			DiskComp->SetLeaderPoseComponent(SkelComp);
		}
	}
	return true;
}

bool UDAAvatarComponent::SetupSkeletal()
{
	if (SetupCast())
	{
		return true;
	}
	USkeletalMesh* Mesh = LoadCharacterAsset<USkeletalMesh>(TEXT("SK_Student"));
	if (!Mesh)
	{
		return false;
	}
	for (const TCHAR* State : { TEXT("Idle"), TEXT("Walk"), TEXT("Run"), TEXT("Jump"), TEXT("Swim"), TEXT("Wave") })
	{
		if (UAnimSequence* Seq = LoadCharacterAsset<UAnimSequence>(FString::Printf(TEXT("A_Student_%s"), State)))
		{
			Anims.Add(FName(State), Seq);
		}
	}
	if (!Anims.Contains(TEXT("Idle")))
	{
		return false;   // a mesh without animations would T-pose; keep the procedural avatar
	}
	FinishSkeletal(Mesh);
	// the editor import scales SK_Student's walk / run clips to these speeds (importer.py REF_SPEED)
	WalkAnimSpeed = 300.f;
	RunAnimSpeed = 600.f;
	if (RunThreshold <= 0.f)
	{
		RunThreshold = 300.f;   // the player walks at 150, sprints at 420
	}
	return true;
}

UAnimSequence* UDAAvatarComponent::FindAnim(FName State) const
{
	const TObjectPtr<UAnimSequence>* Found = Anims.Find(State);
	return Found ? Found->Get() : nullptr;
}

namespace
{
	/** Gravity (cm/s^2, positive) acting on the owner; 980 when it has no movement component. */
	float OwnerGravity(const AActor* Owner)
	{
		if (const ACharacter* Char = Cast<ACharacter>(Owner))
		{
			if (const UCharacterMovementComponent* Move = Char->GetCharacterMovement())
			{
				return FMath::Max(1.f, -Move->GetGravityZ());
			}
		}
		return 980.f;
	}

	// Air / landing heuristics (cm/s).
	constexpr float JumpTakeoffSpeed = 120.f;   // leaving the ground faster than this upwards = a jump
	constexpr float WalkOffFallDelay = 0.2f;    // s in the air before a walk-off shows the fall pose
	constexpr float WalkOffFallSpeed = -250.f;  // ... or once it drops faster than this
	constexpr float JumpFallSpeed = -150.f;     // a jump turns into the fall pose past the apex
	constexpr float LandMinImpact = 300.f;      // ~46 cm drop; softer touchdowns stay in stride

	// Swimming: crawl above this speed, tread water below (hysteresis).
	constexpr float SwimStrokeOn = 70.f;
	constexpr float SwimStrokeOff = 35.f;

	/** Stance/treading reference for the swim pitch pivot (cm, avatar space). */
	const FVector SwimHip(0.0, 0.0, 95.0);
}

bool UDAAvatarComponent::PlayGesture(FName State)
{
	if (!SkelComp || State.IsNone() || !FindAnim(State))
	{
		return false;
	}
	if (!bAnimeCast)
	{
		return false;   // the single-node fallbacks have no layered action slot
	}
	if (CurrentAction != NAME_None && CurrentAction != ActiveGesture)
	{
		return false;   // jumping, landing, swimming or dueling
	}
	PendingGesture = State;
	return true;
}

void UDAAvatarComponent::UpdateBodyLean(float DeltaTime, float GroundSpeed)
{
	const AActor* Owner = GetOwner();
	if (!Owner || DeltaTime <= KINDA_SMALL_NUMBER)
	{
		return;
	}
	const float Yaw = Owner->GetActorRotation().Yaw;
	float YawRate = 0.f;
	if (bHasLastYaw)
	{
		YawRate = FMath::FindDeltaAngleDegrees(LastYaw, Yaw) / DeltaTime;
	}
	LastYaw = Yaw;
	bHasLastYaw = true;
	const float Accel = (GroundSpeed - LastGroundSpeed) / DeltaTime;
	LastGroundSpeed = GroundSpeed;

	float TargetSide = 0.f;
	float TargetForward = 0.f;
	const bool bGrounded = !bWasInAir && SwimAlpha < 0.1f;
	if (bGrounded)
	{
		// Into a turn the body leans towards the centre, tan(lean) = v * omega / g. People mostly
		// steer with their feet, so only part of the full centripetal angle shows, and it is
		// capped so turning on the spot or a sharp 180 never tips the body over.
		const float Omega = FMath::DegreesToRadians(FMath::Clamp(YawRate, -720.f, 720.f));
		TargetSide = FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan(GroundSpeed * Omega / 980.f)) * 0.45f, -8.f, 8.f);
		// Lean into acceleration, rock back while braking (only during the speed change).
		TargetForward = FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan(Accel / 980.f)) * 0.3f, -3.f, 4.f);
	}
	LeanSide = FMath::FInterpTo(LeanSide, TargetSide, DeltaTime, 6.f);
	LeanForward = FMath::FInterpTo(LeanForward, TargetForward, DeltaTime, 5.f);
}

void UDAAvatarComponent::TickSkeletal(float DeltaTime, float GroundSpeed, bool bInAir)
{
	const float VerticalSpeed = GetOwner() ? GetOwner()->GetVelocity().Z : 0.f;

	// Swimming: crawl horizontally while moving, tread water upright when (nearly) still. Only the
	// anime cast has a treading take; the other avatars keep the prone swim pose.
	const bool bCanTread = bAnimeCast && FindAnim(TEXT("Tread")) != nullptr;
	if (SwimAlpha > 0.5f)
	{
		bSwimStroke = bSwimStroke ? GroundSpeed > SwimStrokeOff * BodyScale : GroundSpeed > SwimStrokeOn * BodyScale;
	}
	else
	{
		bSwimStroke = false;
	}
	SwimMoveAlpha = FMath::FInterpTo(SwimMoveAlpha, (!bCanTread || bSwimStroke) ? 1.f : 0.f, DeltaTime, 2.5f);

	UpdateBodyLean(DeltaTime, GroundSpeed);
	if (Cast<UDAAvatarAnimInstance>(SkelComp->GetAnimInstance()))
	{
		TickNative(DeltaTime, GroundSpeed, bInAir, VerticalSpeed);
	}
	else
	{
		TickSingleNode(DeltaTime, GroundSpeed, bInAir);
		bWasInAir = bInAir;
	}

	// Whole-body orientation. The mesh faces +Y in avatar space; a positive roll tips +Z towards
	// +Y (forwards, FRotationMatrix) and a positive pitch tips +Z towards -X (the character's right).
	// On land the body leans about the feet; in the water it pitches prone about the hips and
	// is lifted to just under the surface (upright while treading water).
	const float Land01 = 1.f - FMath::Clamp(SwimAlpha, 0.f, 1.f);
	const float SwimPitch = 80.f * SwimAlpha * SwimMoveAlpha;
	const FRotator Body(LeanSide * Land01, 0.f, SwimPitch + LeanForward * Land01);
	const FVector Pivot = SwimHip * SwimAlpha;
	SkelComp->SetRelativeRotation(Body);
	SkelComp->SetRelativeLocation(Pivot - Body.RotateVector(Pivot) + FVector(0.0, 0.0, 30.0 * SwimAlpha * SwimMoveAlpha));
}

void UDAAvatarComponent::TickNative(float DeltaTime, float GroundSpeed, bool bInAir, float VerticalSpeed)
{
	UDAAvatarAnimInstance* Anim = Cast<UDAAvatarAnimInstance>(SkelComp->GetAnimInstance());
	if (!Anim)
	{
		return;
	}
	static const FName NameJump(TEXT("Jump"));
	static const FName NameFall(TEXT("Fall"));
	static const FName NameLand(TEXT("Land"));
	static const FName NameSwim(TEXT("Swim"));
	static const FName NameTread(TEXT("Tread"));
	static const FName NameDuel(TEXT("Duel"));

	// ---- air phases -------------------------------------------------------------------------
	if (bInAir && !bWasInAir)
	{
		// A new jump/fall supersedes a landing take that is still counting down.
		LandTimer = 0.f;
		LandWeight = 0.f;
		AirTime = 0.f;
		// A jump leaves the ground going up; walking off a ledge or a kerb leaves it level.
		bJumped = VerticalSpeed > JumpTakeoffSpeed;
		JumpRate = 1.f;
		if (bJumped)
		{
			if (UAnimSequence* Jump = FindAnim(NameJump))
			{
				// Time the take (launch -> tuck) to the real rise: v0 / g seconds to the apex.
				const float Rise = FMath::Max(0.15f, VerticalSpeed / OwnerGravity(GetOwner()));
				JumpRate = FMath::Clamp(Jump->GetPlayLength() / Rise, 0.6f, 1.8f);
			}
		}
	}
	if (bInAir)
	{
		AirTime += DeltaTime;
		// Remember the descent speed: by the frame IsFalling() turns false the character
		// movement component has usually already zeroed velocity.Z.
		LastAirVerticalSpeed = VerticalSpeed;
	}
	float LandRate = 1.f;
	if (bWasInAir && !bInAir)
	{
		const float Impact = -LastAirVerticalSpeed;
		UAnimSequence* Land = FindAnim(NameLand);
		if (Land && Impact > LandMinImpact)
		{
			// The absorption scales with the impact: a hop off a bench barely bends the knees,
			// a fall from a wall drops into a deep squat. Landing in stride keeps the legs
			// running and lets only part of the absorption show (and plays it quicker).
			const float Hard = FMath::Clamp((Impact - 250.f) / 550.f, 0.3f, 1.f);
			const float Moving = FMath::Clamp((GroundSpeed - 50.f) / 250.f, 0.f, 1.f);
			LandWeight = Hard * FMath::Lerp(1.f, 0.3f, Moving);
			LandRate = FMath::Lerp(1.25f, 1.f, Hard) * FMath::Lerp(1.f, 1.4f, Moving);
			LandTimer = Land->GetPlayLength() / LandRate;
		}
		AirTime = 0.f;
		bJumped = false;
	}
	bWasInAir = bInAir;
	if (LandTimer > 0.f)
	{
		LandTimer = FMath::Max(0.f, LandTimer - DeltaTime);
		// Sprinting out of a landing: hand the legs back to the run straight away.
		if (GroundSpeed > 260.f)
		{
			LandTimer = FMath::Min(LandTimer, 0.08f);
		}
	}

	// ---- gestures ---------------------------------------------------------------------------
	const bool bBusy = GroundSpeed > 40.f || bInAir || LandTimer > 0.f || SwimAlpha > 0.1f || DuelPoseAlpha > 0.05f;
	if (!PendingGesture.IsNone())
	{
		if (!bBusy && GroundSpeed < 25.f)
		{
			ActiveGesture = PendingGesture;
			GestureTime = 0.f;
		}
		PendingGesture = NAME_None;   // never queue a gesture for later
	}
	if (!ActiveGesture.IsNone())
	{
		GestureTime += DeltaTime;
		UAnimSequence* Gesture = FindAnim(ActiveGesture);
		if (!Gesture || bBusy || GestureTime >= Gesture->GetPlayLength() - 0.25f)
		{
			ActiveGesture = NAME_None;
		}
	}

	// ---- action selection -------------------------------------------------------------------
	FName Want = NAME_None;
	bool bLoop = false;
	float TargetWeight = 1.f;
	float PlayRate = 1.f;
	float BlendTime = 0.2f;
	if (SwimAlpha > 0.5f && (FindAnim(NameSwim) || FindAnim(NameTread)))
	{
		const float SwimRef = FMath::Max(1.f, SwimAnimSpeed * BodyScale);
		if ((bSwimStroke && FindAnim(NameSwim)) || !FindAnim(NameTread))
		{
			// Stroke rate follows the swim speed, so the hands pull water past the body as fast
			// as it moves (a slow drift strokes slowly, a sprint quickly).
			Want = NameSwim;
			PlayRate = FMath::Clamp(GroundSpeed / SwimRef, 0.4f, 1.6f);
		}
		else
		{
			Want = NameTread;
		}
		bLoop = true;
		TargetWeight = FMath::Clamp(SwimAlpha, 0.f, 1.f);
		BlendTime = 0.45f;
	}
	else if (bInAir)
	{
		const bool bFalling = bJumped ? VerticalSpeed < JumpFallSpeed
			: (AirTime > WalkOffFallDelay || VerticalSpeed < WalkOffFallSpeed);
		if (bFalling && FindAnim(NameFall))
		{
			Want = NameFall;
			bLoop = true;
			BlendTime = 0.3f;
		}
		else if (bJumped && FindAnim(NameJump))
		{
			Want = NameJump;
			PlayRate = JumpRate;
			BlendTime = 0.08f;
		}
		// Otherwise a short step down: the legs keep walking for the few frames in the air.
	}
	else if (LandTimer > 0.f && FindAnim(NameLand))
	{
		Want = NameLand;
		TargetWeight = LandWeight;
		PlayRate = LandRate;
		BlendTime = 0.06f;
	}
	else if (DuelPoseAlpha > 0.02f && GroundSpeed < 30.f && FindAnim(NameDuel))
	{
		Want = NameDuel;
		bLoop = true;
		TargetWeight = FMath::Clamp(DuelPoseAlpha, 0.f, 1.f);
		BlendTime = 0.35f;
	}
	else if (!ActiveGesture.IsNone())
	{
		Want = ActiveGesture;
		BlendTime = 0.25f;
	}

	if (Want != CurrentAction)
	{
		if (Want == NAME_None)
		{
			// Fade out over a time that suits what is ending: a landing recovers quickly into
			// the stride, a duel stance or a wave settles back more slowly.
			const float Out = CurrentAction == NameFall ? 0.12f
				: CurrentAction == NameLand ? 0.25f
				: CurrentAction == NameJump ? 0.15f
				: CurrentAction == NameSwim || CurrentAction == NameTread ? 0.4f
				: 0.35f;
			Anim->ClearAction(Out);
		}
		else
		{
			Anim->SetAction(FindAnim(Want), bLoop, TargetWeight, PlayRate, BlendTime);
		}
		CurrentAction = Want;
	}
	else if (Want == NameDuel || Want == NameSwim || Want == NameTread)
	{
		Anim->SetActionWeight(TargetWeight);
		Anim->SetActionPlayRate(PlayRate);
	}

	// While the full-body swim action is showing, keep the base locomotion at a standstill so it
	// cannot leak through the blend.
	const float LocomotionSpeed = (SwimAlpha > 0.5f) ? 0.f : GroundSpeed;
	Anim->SetLocomotion(LocomotionSpeed, SwimAlpha, DuelPoseAlpha);
}

void UDAAvatarComponent::TickSingleNode(float DeltaTime, float GroundSpeed, bool bInAir)
{
	static const FName NameIdle(TEXT("Idle"));
	static const FName NameWalk(TEXT("Walk"));
	static const FName NameRun(TEXT("Run"));
	static const FName NameJump(TEXT("Jump"));
	static const FName NameFall(TEXT("Fall"));
	static const FName NameSwim(TEXT("Swim"));
	static const FName NameWave(TEXT("Wave"));
	static const FName NameDuel(TEXT("Duel"));
	const float VerticalSpeed = GetOwner() ? GetOwner()->GetVelocity().Z : 0.f;
	if (bInAir && !bWasInAir)
	{
		AirTime = 0.f;
		bJumped = VerticalSpeed > JumpTakeoffSpeed;
	}
	AirTime = bInAir ? AirTime + DeltaTime : 0.f;

	// Walk / run switch with hysteresis, so a speed hovering at the threshold cannot flicker
	// between the two clips every frame.
	const float RunAt = RunThreshold > 0.f ? RunThreshold : (WalkAnimSpeed + RunAnimSpeed) * 0.5f + 60.f;
	const bool bWasRunning = CurrentAnim == NameRun;
	const bool bRun = GroundSpeed > (bWasRunning ? RunAt * 0.85f : RunAt) && FindAnim(NameRun);

	FName Want = NameIdle;
	float Rate = 1.f;
	bool bLoop = true;
	if (SwimAlpha > 0.5f)
	{
		Want = FindAnim(NameSwim) ? NameSwim : NameWalk;
		Rate = FMath::Clamp(GroundSpeed / FMath::Max(SwimAnimSpeed * BodyScale, 1.f), 0.4f, 1.6f) * (FindAnim(NameSwim) ? 1.f : 0.7f);
	}
	else if (bInAir && (bJumped || AirTime > WalkOffFallDelay) && FindAnim(NameJump))
	{
		// rising: the jump take (once); falling: the fall loop when there is one
		Want = (VerticalSpeed < JumpFallSpeed && FindAnim(NameFall)) ? NameFall : NameJump;
		bLoop = Want == NameFall;
	}
	else if (bRun)
	{
		Want = NameRun;
		// The clip's planted foot moves at RunAnimSpeed (x BodyScale) at rate 1.
		Rate = FMath::Clamp(GroundSpeed / FMath::Max(RunAnimSpeed * BodyScale, 1.f), 0.5f, 2.f);
	}
	else if (GroundSpeed > 20.f && FindAnim(NameWalk))
	{
		Want = NameWalk;
		// Exact foot speed: the play rate is the speed ratio (a single clip cannot shorten its
		// steps, so a slow walk plays slower rather than skating).
		Rate = FMath::Clamp(GroundSpeed / FMath::Max(WalkAnimSpeed * BodyScale, 1.f), 0.15f, 2.f);
	}
	else if (DuelPoseAlpha > 0.5f && (FindAnim(NameDuel) || FindAnim(NameWave)))
	{
		Want = FindAnim(NameDuel) ? NameDuel : NameWave;
		bLoop = Want == NameDuel;
	}
	if (Want != CurrentAnim)
	{
		if (UAnimSequence* Seq = FindAnim(Want))
		{
			SkelComp->PlayAnimation(Seq, bLoop);
			CurrentAnim = Want;
		}
	}
	SkelComp->SetPlayRate(Rate);
}

void UDAAvatarComponent::BeginPlay()
{
	Super::BeginPlay();

	// BodyScale 0/NaN makes the figure invisible or emits NaN transforms; a
	// zero stride would also divide by zero in the procedural gait below.
	BodyScale = FMath::IsFinite(BodyScale) && BodyScale > 0.f ? FMath::Clamp(BodyScale, 0.05f, 10.f) : 1.f;
	StrideSpeed = FMath::IsFinite(StrideSpeed) ? FMath::Max(StrideSpeed, 1.f) : 150.f;
	SwimAnimSpeed = FMath::IsFinite(SwimAnimSpeed) ? FMath::Max(SwimAnimSpeed, 1.f) : 125.f;

	if (bPreferSkeletal && SetupSkeletal())
	{
		ApplyColours();
		return;
	}

	Pelvis = NewObject<USceneComponent>(GetOwner(), NAME_None, RF_Transient);
	Pelvis->SetupAttachment(this);
	Pelvis->SetRelativeLocation(HipHeight);
	Pelvis->RegisterComponent();
	SetRelativeScale3D(FVector(BodyScale));

	Torso = MakePart(TEXT("SM_Avatar_Torso"), Pelvis, FVector::ZeroVector);
	Head = MakePart(TEXT("SM_Avatar_Head"), Torso, HeadJoint);
	ArmL = MakePart(TEXT("SM_Avatar_ArmL"), Torso, ArmLJoint);
	ArmR = MakePart(TEXT("SM_Avatar_ArmR"), Torso, ArmRJoint);
	LegL = MakePart(TEXT("SM_Avatar_LegL"), Pelvis, LegLJoint);
	LegR = MakePart(TEXT("SM_Avatar_LegR"), Pelvis, LegRJoint);
	if (bShowDuelDisk)
	{
		Disk = MakePart(TEXT("SM_Avatar_DuelDisk"), ArmL, DiskOnArm);
	}
	BreathPhase = FMath::FRand() * 6.28f;
	ApplyColours();
}

void UDAAvatarComponent::SetDorm(EDADorm NewDorm)
{
	Dorm = NewDorm;
	ApplyColours();
}

void UDAAvatarComponent::ApplyColours()
{
	if (SkelComp)
	{
		if (bAnimeCast && !bDormTint)
		{
			return;   // named characters keep their own colours
		}
		if (JacketMaterials.Num() == 0)
		{
			const TArray<FName> Slots = SkelComp->GetMaterialSlotNames();
			for (int32 i = 0; i < Slots.Num(); ++i)
			{
				const FString SlotName = Slots[i].ToString().ToLower();
				// anime cast: only the neutral "...JacketTint" / "...HairTint" slots; SK_Student: keyword match
				const bool bJacket = bAnimeCast ? SlotName.Contains(TEXT("jackettint"))
					: JacketSlotKeywords.ContainsByPredicate([&SlotName](const FString& K) { return SlotName.Contains(K); });
				const bool bHair = bAnimeCast ? SlotName.Contains(TEXT("hairtint")) : SlotName.Contains(TEXT("hair"));
				if (!bJacket && !bHair)
				{
					continue;
				}
				if (UMaterialInstanceDynamic* MID = SkelComp->CreateDynamicMaterialInstance(i))
				{
					if (bJacket)
					{
						JacketMaterials.Add(MID);
					}
					else
					{
						MID->SetVectorParameterValue(TEXT("Tint"), HairColor);
					}
				}
			}
		}
		for (UMaterialInstanceDynamic* MID : JacketMaterials)
		{
			if (MID)
			{
				MID->SetVectorParameterValue(TEXT("Tint"), DuelAcademy::DormColor(Dorm));
			}
		}
		return;
	}
	if (!Torso)
	{
		return;
	}
	if (JacketMaterials.Num() == 0)
	{
		for (UStaticMeshComponent* Part : { Torso.Get(), ArmL.Get(), ArmR.Get() })
		{
			if (!Part || !Part->GetStaticMesh())
			{
				continue;
			}
			const int32 Slot = Part->GetMaterialIndex(TEXT("M_Jacket"));
			if (Slot != INDEX_NONE)
			{
				if (UMaterialInstanceDynamic* MID = Part->CreateDynamicMaterialInstance(Slot))
				{
					JacketMaterials.Add(MID);
				}
			}
		}
		if (Head && Head->GetStaticMesh())
		{
			const int32 HairSlot = Head->GetMaterialIndex(TEXT("M_Hair"));
			if (HairSlot != INDEX_NONE)
			{
				if (UMaterialInstanceDynamic* MID = Head->CreateDynamicMaterialInstance(HairSlot))
				{
					MID->SetVectorParameterValue(TEXT("Tint"), HairColor);
				}
			}
		}
	}
	const FLinearColor Color = DuelAcademy::DormColor(Dorm);
	for (UMaterialInstanceDynamic* MID : JacketMaterials)
	{
		if (MID)
		{
			MID->SetVectorParameterValue(TEXT("Tint"), Color);
		}
	}
}

void UDAAvatarComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	const AActor* Owner = GetOwner();
	FVector Velocity = Owner ? Owner->GetVelocity() : FVector::ZeroVector;
	bool bInAir = false;
	if (const ACharacter* Char = Cast<ACharacter>(Owner))
	{
		if (const UCharacterMovementComponent* Move = Char->GetCharacterMovement())
		{
			bInAir = Move->IsFalling();
		}
	}
	const float GroundSpeed = FVector(Velocity.X, Velocity.Y, 0.0).Size();
	if (SkelComp)
	{
		TickSkeletal(DeltaTime, GroundSpeed, bInAir);
		return;
	}
	if (!Pelvis || !Torso)
	{
		return;
	}
	Time += DeltaTime;
	SmoothedSpeed = FMath::FInterpTo(SmoothedSpeed, GroundSpeed, DeltaTime, 20.f);
	// A real jump (or a drop longer than a kerb) shows the air pose; a step down stays in stride.
	AirTime = bInAir ? AirTime + DeltaTime : 0.f;
	const bool bShowAir = bInAir && SwimAlpha < 0.5f && (AirTime > WalkOffFallDelay || Velocity.Z > JumpTakeoffSpeed || Velocity.Z < WalkOffFallSpeed);
	AirAlpha = FMath::FInterpTo(AirAlpha, bShowAir ? 1.f : 0.f, DeltaTime, 10.f);
	// Swim stroke: one crawl cycle moves the body ~2 m, so the arms keep pace with the swim speed.
	SwimCycle = FMath::Fmod(SwimCycle + DeltaTime * FMath::Clamp(GroundSpeed / FMath::Max(SwimAnimSpeed * BodyScale, 1.f), 0.4f, 1.6f) / 1.6f, 1.f);

	// ---- gait: the same human cadence model as the anime cast ----------------------------------
	// Everything is solved in avatar space (the component is scaled by BodyScale). Reference walk:
	// StrideSpeed cm/s with a 1.0 s cycle; reference run: 2.8x that with a 0.7 s cycle. Below the
	// walk speed both cadence and stride shrink with sqrt(speed); between walk and run the
	// cadence rises linearly and the stance fraction drops from 60 % to 30 % (flight phases).
	const float LegLength = HipHeight.Z;
	const float V = (SwimAlpha > 0.5f || bInAir) ? 0.f : SmoothedSpeed / BodyScale;
	const float WalkV = StrideSpeed;
	const float RunV = StrideSpeed * 2.8f;
	constexpr float WalkCadence = 1.f;
	constexpr float RunCadence = 1.f / 0.7f;
	float Cadence = 0.f;
	float Duty = 0.6f;
	float Run01 = 0.f;
	if (V > 6.f)
	{
		if (V <= WalkV)
		{
			Cadence = WalkCadence * FMath::Sqrt(V / WalkV);
		}
		else
		{
			Run01 = FMath::Clamp((V - WalkV) / (RunV - WalkV), 0.f, 1.f);
			Cadence = V < RunV ? FMath::Lerp(WalkCadence, RunCadence, Run01) : RunCadence * FMath::Pow(V / RunV, 0.3f);
			Duty = FMath::Lerp(0.6f, 0.3f, Run01);
		}
	}
	Phase = FMath::Fmod(Phase + Cadence * DeltaTime, 1.f);
	const float Stride = Cadence > 0.f ? V / Cadence : 0.f;
	// The planted foot travels Stride * Duty backwards during stance: exactly V.
	const float HalfStance = FMath::Min(Stride * Duty * 0.5f, LegLength * 0.7f);
	StepAmplitude = HalfStance;
	const float Move01 = FMath::Clamp(V / FMath::Max(WalkV, 1.f), 0.f, 1.f);

	struct FLegState { float Angle; bool bStance; float LegPhase; };
	auto SolveLeg = [&](float Offset) -> FLegState
	{
		const float LP = FMath::Fmod(Phase + Offset, 1.f);
		float X;
		bool bStance;
		if (LP < Duty)
		{
			X = HalfStance * (1.f - 2.f * LP / Duty);
			bStance = true;
		}
		else
		{
			const float T = (LP - Duty) / FMath::Max(1.f - Duty, 0.01f);
			X = -HalfStance + 2.f * HalfStance * (T * T * (3.f - 2.f * T));
			bStance = false;
		}
		const float Angle = FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(X / LegLength, -0.95f, 0.95f)));
		return { Angle, bStance, LP };
	};
	const FLegState L = SolveLeg(0.f);
	const FLegState R = SolveLeg(0.5f);

	// Pelvis height: vaulting over the stance leg(s) (lowest in double support) for the walk; a
	// spring for the run - compressed in stance, a ballistic rise in the flight phase.
	float HipZ = LegLength;
	{
		float Sum = 0.f;
		int32 Count = 0;
		for (const FLegState* Leg : { &L, &R })
		{
			if (Leg->bStance)
			{
				float Z = LegLength * FMath::Cos(FMath::DegreesToRadians(Leg->Angle));
				Z -= 4.f * Run01 * FMath::Sin(PI * Leg->LegPhase / Duty);
				Sum += Z;
				++Count;
			}
		}
		const float EdgeZ = FMath::Sqrt(FMath::Max(0.f, LegLength * LegLength - HalfStance * HalfStance));
		if (Count > 0)
		{
			HipZ = Sum / Count;
		}
		else
		{
			const float Flight = FMath::Max(0.5f - Duty, 0.01f);
			const float U = FMath::Fmod(Phase, 0.5f) - Duty;
			const float Tf = Flight / FMath::Max(Cadence, 0.1f);
			const float Peak = 0.125f * 980.f / BodyScale * Tf * Tf;
			const float W = FMath::Clamp(U / Flight, 0.f, 1.f);
			HipZ = EdgeZ + 4.f * Peak * W * (1.f - W);
		}
	}
	const float Bob = HipZ - LegLength;

	const float S = FMath::Sin(2.f * PI * Phase);
	const float Breath = FMath::Sin(Time * 1.6f + BreathPhase);   // ~15 breaths a minute

	// ---- legs / arms (roll = rotation about the avatar's lateral X axis)
	float LegLAngle = L.Angle;
	float LegRAngle = R.Angle;
	// Arms swing in opposition to the legs, a little more in the run.
	const float ArmScale = FMath::Lerp(0.8f, 1.3f, Run01);
	float ArmLAngle = R.Angle * ArmScale;
	float ArmRAngle = L.Angle * ArmScale;
	float ArmSpread = 4.f + Breath * 0.6f;
	// Angles are "forward swing". The figure faces +Y in avatar space and a positive roll tips +Z towards +Y
	// (FRotationMatrix): hanging limbs swing forward with a NEGATIVE roll, the torso leans forward with a POSITIVE one.
	float TorsoLean = FMath::Lerp(2.f * Move01, 7.f, Run01);

	// Jump / fall pose
	LegLAngle = FMath::Lerp(LegLAngle, -25.f, AirAlpha);
	LegRAngle = FMath::Lerp(LegRAngle, 12.f, AirAlpha);
	ArmLAngle = FMath::Lerp(ArmLAngle, 35.f, AirAlpha);
	ArmRAngle = FMath::Lerp(ArmRAngle, 35.f, AirAlpha);
	ArmSpread = FMath::Lerp(ArmSpread, 35.f, AirAlpha);

	// Dueling pose: left (disk) arm raised forward
	ArmLAngle = FMath::Lerp(ArmLAngle, 80.f, DuelPoseAlpha);

	// Swimming: crawl stroke
	if (SwimAlpha > 0.01f)
	{
		const float SwimPhase = 2.f * PI * SwimCycle;
		ArmLAngle = FMath::Lerp(ArmLAngle, FMath::RadiansToDegrees(SwimPhase) , SwimAlpha);
		ArmRAngle = FMath::Lerp(ArmRAngle, FMath::RadiansToDegrees(SwimPhase + PI), SwimAlpha);
		// six-beat flutter kick: three kicks per leg per stroke cycle
		LegLAngle = FMath::Lerp(LegLAngle, FMath::Sin(SwimPhase * 3.f) * 12.f, SwimAlpha);
		LegRAngle = FMath::Lerp(LegRAngle, -FMath::Sin(SwimPhase * 3.f) * 12.f, SwimAlpha);
		ArmSpread = FMath::Lerp(ArmSpread, 12.f, SwimAlpha);
	}

	LegL->SetRelativeRotation(FRotator(0.f, 0.f, -LegLAngle));
	LegR->SetRelativeRotation(FRotator(0.f, 0.f, -LegRAngle));
	ArmL->SetRelativeRotation(FRotator(-ArmSpread, 0.f, -ArmLAngle));
	ArmR->SetRelativeRotation(FRotator(ArmSpread, 0.f, -ArmRAngle));

	// ---- body
	const float SwimPitch = 80.f * SwimAlpha;
	Pelvis->SetRelativeLocation(HipHeight + FVector(0.0, 0.0, Bob * (1.f - AirAlpha) - 0.3f * Breath * (1.f - Move01) + 32.0 * SwimAlpha));
	Pelvis->SetRelativeRotation(FRotator(0.f, 0.f, TorsoLean * 0.4f + SwimPitch));
	// The shoulders counter-rotate against the pelvis once per stride.
	Torso->SetRelativeRotation(FRotator(0.f, -S * FMath::Lerp(3.f, 7.f, Run01) * Move01, TorsoLean + 0.6f * Breath * (1.f - Move01)));
	Torso->SetRelativeScale3D(FVector(1.0, 1.0 + 0.008 * Breath, 1.0 + 0.005 * Breath));
	// Head: eyes level (counter the lean and the stride rotation), a slow look around when idle.
	Head->SetRelativeRotation(FRotator(0.f, FMath::Sin(Time * 0.37f + BreathPhase) * 8.f * (1.f - Move01 * 0.8f)
		+ S * FMath::Lerp(3.f, 7.f, Run01) * Move01, -TorsoLean * 0.8f - SwimPitch * 0.6f));
}
