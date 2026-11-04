// Duel Academy Island - anime cast locomotion anim instance.
//
// A small native animation graph (no AnimBlueprint asset needed):
//   * Idle / Walk / Run are blended by ground speed. Walk and Run are kept in phase by driving
//     both sequence players from one gait phase, and the phase rate is solved from the blended
//     stride length so the planted foot moves backwards at exactly the character's speed - no
//     foot sliding at any speed between a stroll and a sprint.
//   * Jump / Fall / Land / Swim / Duel are action sequences layered over the locomotion with
//     smooth crossfades (two action players, so switching Jump -> Fall or Land crossfades
//     instead of popping).
//
// The anime takes are authored at 1.50 m/s walk and 4.20 m/s run (A_Anime_<Group>_Walk/Run).
// UDAAvatarComponent feeds ground speed / air / swim / duel state every tick.
//
// On top of the blended takes the proxy runs the procedural "life" layer anime game characters have:
//   * secondary motion: VRM-style verlet spring chains on the hair (VRoid HairJoint-* bones), the skirt and
//     coat-tail cloth bones (skirt_* / coattail_*, Tools/dai/anime/outfit.py) and the J_Sec_* helpers, in
//     world space so they swing when the character starts, stops and turns; a head sphere keeps hair out of
//     the face
//   * look-at: neck + head turn towards a target (the player while talking), clamped and eased
//   * face: random blinks (sometimes double), lip-sync visemes while talking, eased emotions - all on the
//     face morph targets exported with the cast (Blink, A/I/U/E/O, Joy/Angry/Sorrow/Surprised/Fun)

#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "DAAvatarAnimInstance.generated.h"

class UAnimSequence;

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

	/** Start (or retarget) an action. Re-sending the current sequence only updates its target weight. */
	void SetAction(UAnimSequence* Sequence, bool bLoop, float InTargetWeight = 1.f, float InPlayRate = 1.f);

	/** Fade the current action out (the action sequence and its crossfade partner keep playing). */
	void ClearAction();

	/** Update the weight of the current action while it is active (Duel pose / Swim alpha). */
	void SetActionWeight(float InTargetWeight);

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

protected:
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> IdleSequence;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> WalkSequence;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> RunSequence;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> ActionSequenceA;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> ActionSequenceB;

private:
	void UpdateActionTimes(float DeltaSeconds);
	void UpdateFace(float Dt);

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
	bool bActionLoopA = false;
	bool bActionLoopB = false;
};
