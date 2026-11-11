// Duel Academy Island - anime cast locomotion anim instance.
//
// A small native animation graph (no AnimBlueprint asset needed):
//   * Idle / Walk / Run are blended by ground speed following a human cadence model: below the
//     walk speed both the step length (~sqrt(speed)) and the step rate drop, between walk and
//     run the cadence rises steadily. Walk and Run are kept in phase by driving both sequence
//     players from one gait phase, and the phase rate is solved from the stride of the pose
//     actually shown, so the planted foot moves backwards at exactly the character's ground
//     speed - the legs never cycle faster (or slower) than the body travels.
//   * Jump / Fall / Land / Swim / Duel are action sequences layered over the locomotion with
//     smooth crossfades (two action players, so switching Jump -> Fall or Land crossfades
//     instead of popping).
//
// The anime takes are authored at the speed configured by UDAAvatarComponent::WalkAnimSpeed /
// RunAnimSpeed (the procedural gait is 150 / 420 cm/s; the optional Fab retarget uses its measured
// 1.33-1.58 m/s walk and 5.55-6.59 m/s sprint planted-foot speeds).
// UDAAvatarComponent feeds ground speed / air / swim / duel state every tick.
//
// On top of the blended takes the proxy runs the procedural "life" layer anime game characters have:
//   * secondary motion: VRM-style verlet spring chains on the hair (HairJoint_* chains fitted to each restyled
//     head of hair, Tools/dai/anime/hairrig.py; solved level by level with a cohesion pull between neighbouring
//     chains and a cone limit, so the hair moves as one mass and keeps its style), the skirt and
//     coat-tail cloth bones (skirt_* / coattail_*, Tools/dai/anime/outfit.py) and the J_Sec_* helpers, in
//     world space so they swing when the character starts, stops and turns; a head sphere keeps hair out of
//     the face
//   * look-at: neck + head turn towards a target (the player while talking), clamped and eased
//   * face: random blinks (sometimes double), lip-sync visemes while talking, eased emotions - all on the
//     face morph targets exported with the cast (Blink, A/I/U/E/O, Joy/Angry/Sorrow/Surprised/Fun)
//   * motorcycle rider: the pelvis on the seat, the back leaning until the hands reach the grips, two-bone IK
//     arms and legs onto the bars and pegs (a foot on the ground at a stop), driven by UDAAvatarComponent from
//     the bike's FDARiderTargets (DARiderIK in the .cpp)
//   * cloth correctives: pose-space morphs (Fit_HipFwd_l ...) faded in by each thigh's pitch / spread and
//     knee flexion, the same formula the build solved them with - they keep trousers inside long coats in
//     a stride or a sit, where linear blend skinning alone collapses the seat

#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "DAAvatarAnimInstance.generated.h"

class UAnimSequence;

// ---- rider IK targets begin (extracted by Tools/tests/rider/extract.py)
/**
 * A motorcycle rider's pose targets in the mesh's component space (cm; the cast faces +Y, its left is +X,
 * +Z up). UDAAvatarComponent converts the bike's FDARiderTargets into these every tick; the proxy solves
 * the pelvis onto the seat, leans the spine until both hands reach the grips and two-bone IKs the arms
 * and legs (see DARiderIK in DAAvatarAnimInstance.cpp).
 */
struct FDARiderIKTargets
{
	/** Where the pelvis bone goes (seated on the seat, or raised when standing on the pegs). */
	FVector Pelvis = FVector::ZeroVector;
	/** Handlebar grip centres; [0] the rider's left (+X), [1] the right. */
	FVector Grip[2] = { FVector::ZeroVector, FVector::ZeroVector };
	/** Contact under the ball of each foot: the peg top, or the ground for a foot put down. */
	FVector Ball[2] = { FVector::ZeroVector, FVector::ZeroVector };
	/** Forward lean of the upper body (degrees). The solver leans further when a grip is out of reach. */
	float Lean = 16.f;
	/** Upper-body roll towards the rider's left (degrees, about +Y). */
	float Roll = 0.f;
	/** Extra neck / head roll towards the left (degrees). */
	float HeadRoll = 0.f;
	/** Toe-down pitch of each foot (degrees): a little on the pegs, tiptoe on the ground. */
	float ToeDown[2] = { 6.f, 6.f };
};
// ---- rider IK targets end

UCLASS(Transient, NotBlueprintable)
class DUELACADEMYISLAND_API UDAAvatarAnimInstance : public UAnimInstance
{
	GENERATED_BODY()

public:
	UDAAvatarAnimInstance();

	virtual void NativeInitializeAnimation() override;
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;
	virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;

	/** Copy the cast's take map and the clip ground speeds (cm/s, already scaled by BodyScale). */
	void Configure(const TMap<FName, TObjectPtr<UAnimSequence>>& InAnims, float InWalkSpeed, float InRunSpeed);

	/** Per-tick locomotion input. VerticalSpeed/bInAir were dropped (W11): the
	 *  native graph reads only ground speed plus the swim/duel alphas; the
	 *  air/jump/land action choice stays in UDAAvatarComponent's own tick. */
	void SetLocomotion(float InGroundSpeed, float InSwimAlpha, float InDuelAlpha);

	/** Start (or retarget) an action. Re-sending the current sequence only updates its target weight,
	 *  play rate and blend time. InBlendTime is the crossfade duration in seconds. */
	void SetAction(UAnimSequence* Sequence, bool bLoop, float InTargetWeight = 1.f, float InPlayRate = 1.f, float InBlendTime = 0.2f);

	/** Fade the current action out (the action sequence and its crossfade partner keep playing).
	 *  InBlendTime <= 0 keeps the action's own blend time. */
	void ClearAction(float InBlendTime = -1.f);

	/** Change the play rate of the current action (swim stroke rate follows the swim speed). */
	void SetActionPlayRate(float InPlayRate);

	/** Seconds until the current one-shot action reaches its end (0 for loops / no action). */
	float GetActionTimeRemaining() const;

	/** The action currently fading in or held (null when none). */
	UAnimSequence* GetActionSequence() const { return ActionTargetA > KINDA_SMALL_NUMBER ? ActionSequenceA.Get() : nullptr; }

	/** Update the weight of the current action while it is active (Duel pose / Swim alpha). */
	void SetActionWeight(float InTargetWeight);

	/** Motorcycle rider IK (component space targets) blended in by Alpha (0 = off, the takes play untouched). */
	void SetRider(const FDARiderIKTargets& InTargets, float InAlpha);

	/** Lip-sync: cycle the mouth visemes while true. */
	void SetTalking(bool bInTalking) { bTalking = bInTalking; }

	/** Ease an emotion morph (Joy, Angry, Sorrow, Surprised, Fun) towards Weight; NAME_None clears all. */
	void SetEmotion(FName Emotion, float Weight);

	/** Turn the head towards a world location (bEnable false eases back to the animation). */
	void SetLookAtTarget(const FVector& WorldLocation, bool bEnable);

	/** Self-test / debug: spring chains on this skeleton, the largest spring deflection (degrees) of the last
	 *  evaluated frame, and the current look-at weight (-DACastLifeTest). */
	int32 GetSpringChainCount() const { return SpringChainCount; }
	float GetSpringDeflection() const { return SpringDeflection; }
	float GetLookAlpha() const { return LookAlpha; }

	/** Turn the spring chains on or off (e.g. for a debug comparison). */
	UPROPERTY(Transient, BlueprintReadWrite, Category = "Duel Academy|Animation")
	bool bSecondaryMotion = true;

	UFUNCTION(BlueprintPure, Category = "Duel Academy|Animation")
	float GetLocomotionPhase() const { return Phase; }

	/** Exposed for the self-test / debug HUD. */
	UPROPERTY(Transient, BlueprintReadOnly, Category = "Duel Academy|Animation")
	float BlendedGroundSpeed = 0.f;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "Duel Academy|Animation")
	float WalkBlend = 0.f;

	UPROPERTY(Transient, BlueprintReadOnly, Category = "Duel Academy|Animation")
	float RunBlend = 0.f;

	/** Gait cycles per second currently played (two steps per cycle). */
	UPROPERTY(Transient, BlueprintReadOnly, Category = "Duel Academy|Animation")
	float BlendedCadence = 0.f;

protected:
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> IdleSequence;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> WalkSequence;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> RunSequence;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> ActionSequenceA;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> ActionSequenceB;

private:
	void UpdateActionTimes(float DeltaSeconds);
	void UpdateFace(float Dt);
	/** Thigh / knee driven cloth corrective morphs (Fit_*, Tools/dai/anime/correctives.py). */
	void UpdateCorrectives();

	// corrective morphs present on this mesh: name -> index into the key table, per side
	TArray<TPair<FName, int32>> FitMorphs[2];
	bool bFitChecked = false;

	// face
	bool bTalking = false;
	bool bHasFace = false;
	float BlinkTimer = 2.f;
	float BlinkClock = -1.f;
	bool bDoubleBlink = false;
	float TalkClock = 0.f;
	float VisemeHold = 0.f;
	int32 Viseme = 0;
	float VisemeWeights[5] = { 0.f, 0.f, 0.f, 0.f, 0.f };
	TMap<FName, float> EmotionTargets;
	TMap<FName, float> EmotionWeights;
	FRandomStream FaceRng;

	// spring stats copied back from the proxy (previous frame)
	int32 SpringChainCount = 0;
	float SpringDeflection = 0.f;

	// motorcycle rider IK
	FDARiderIKTargets RiderTargets;
	float RiderAlpha = 0.f;

	// look-at
	FVector LookTargetWorld = FVector::ZeroVector;
	bool bLookAt = false;
	float LookAlpha = 0.f;

	float GroundSpeed = 0.f;
	float SwimAlpha = 0.f;
	float DuelAlpha = 0.f;

	float WalkGroundSpeed = 150.f;
	float RunGroundSpeed = 420.f;
	float SmoothedSpeed = 0.f;
	float Phase = 0.f;
	float IdleTime = 0.f;
	float IdleBlend = 1.f;
	float WalkBlendValue = 0.f;
	float RunBlendValue = 0.f;

	float ActionTimeA = 0.f;
	float ActionTimeB = 0.f;
	float ActionWeightA = 0.f;
	float ActionWeightB = 0.f;
	float ActionTargetA = 0.f;
	float ActionPlayRateA = 1.f;
	float ActionPlayRateB = 1.f;
	float ActionBlendRateA = 5.f;
	float ActionBlendRateB = 5.f;
	bool bActionLoopA = false;
	bool bActionLoopB = false;
};
