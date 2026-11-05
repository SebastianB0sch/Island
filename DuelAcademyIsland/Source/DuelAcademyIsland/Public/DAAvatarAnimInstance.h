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
// The anime takes are authored at 1.50 m/s walk (1.0 s cycle, 120 steps/min) and 4.20 m/s run
// (0.733 s cycle, ~164 steps/min) (A_Anime_<Group>_Walk/Run).
// UDAAvatarComponent feeds ground speed / air / swim / duel state every tick.

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
