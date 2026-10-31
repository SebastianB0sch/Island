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

	/** Per-tick locomotion input. */
	void SetLocomotion(float InGroundSpeed, bool bInAir, float InVerticalSpeed, float InSwimAlpha, float InDuelAlpha);

	/** Start (or retarget) an action. Re-sending the current sequence only updates its target weight. */
	void SetAction(UAnimSequence* Sequence, bool bLoop, float InTargetWeight = 1.f, float InPlayRate = 1.f);

	/** Fade the current action out (the action sequence and its crossfade partner keep playing). */
	void ClearAction();

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

protected:
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> IdleSequence;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> WalkSequence;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> RunSequence;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> ActionSequenceA;
	UPROPERTY(Transient) TObjectPtr<UAnimSequence> ActionSequenceB;

private:
	void UpdateActionTimes(float DeltaSeconds);

	float GroundSpeed = 0.f;
	float VerticalSpeed = 0.f;
	float SwimAlpha = 0.f;
	float DuelAlpha = 0.f;
	bool bInAir = false;

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
