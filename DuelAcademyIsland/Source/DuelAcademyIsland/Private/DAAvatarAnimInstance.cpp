// Duel Academy Island - native locomotion anim instance implementation.

#include "DAAvatarAnimInstance.h"

#include "Animation/AnimNodeBase.h"
#include "Animation/AnimNode_SequencePlayer.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"

namespace
{
	/** Weight interpolation rate of the idle / walk / run blend (1/s). */
	constexpr float LocomotionBlendSpeed = 14.f;
	/** Ground-speed filter (1/s): only hides velocity jitter, ~50 ms lag. */
	constexpr float SpeedFilterRate = 20.f;
	/** Below this ground speed (cm/s) the character stands; no micro-steps. */
	constexpr float MinStepSpeed = 6.f;
	/** Upper limit of the solved cadence, relative to the run clip's own cadence. */
	constexpr float MaxCadenceScale = 1.35f;
}

struct FDAAnimInstanceProxy : public FAnimInstanceProxy
{
	FDAAnimInstanceProxy(UAnimInstance* InInstance)
		: FAnimInstanceProxy(InInstance)
	{
	}

	FAnimNode_SequencePlayer_Standalone IdleNode;
	FAnimNode_SequencePlayer_Standalone WalkNode;
	FAnimNode_SequencePlayer_Standalone RunNode;
	FAnimNode_SequencePlayer_Standalone ActionNodeA;
	FAnimNode_SequencePlayer_Standalone ActionNodeB;

	// Thread-safe copy written by NativeUpdateAnimation (game thread) before the parallel update.
	UAnimSequence* IdleSeq = nullptr;
	UAnimSequence* WalkSeq = nullptr;
	UAnimSequence* RunSeq = nullptr;
	UAnimSequence* ActionSeqA = nullptr;
	UAnimSequence* ActionSeqB = nullptr;
	float IdleTime = 0.f;
	float Phase = 0.f;
	float IdleW = 1.f;
	float WalkW = 0.f;
	float RunW = 0.f;
	float ActionWA = 0.f;
	float ActionWB = 0.f;
	float ActionTimeA = 0.f;
	float ActionTimeB = 0.f;
	bool bLoopA = false;
	bool bLoopB = false;

	virtual void Initialize(UAnimInstance* InInstance) override
	{
		FAnimInstanceProxy::Initialize(InInstance);
		FAnimationInitializeContext InitContext(this);
		IdleNode.Initialize_AnyThread(InitContext);
		WalkNode.Initialize_AnyThread(InitContext);
		RunNode.Initialize_AnyThread(InitContext);
		ActionNodeA.Initialize_AnyThread(InitContext);
		ActionNodeB.Initialize_AnyThread(InitContext);
	}

	virtual void CacheBones() override
	{
		FAnimInstanceProxy::CacheBones();
		FAnimationCacheBonesContext Context(this);
		IdleNode.CacheBones_AnyThread(Context);
		WalkNode.CacheBones_AnyThread(Context);
		RunNode.CacheBones_AnyThread(Context);
		ActionNodeA.CacheBones_AnyThread(Context);
		ActionNodeB.CacheBones_AnyThread(Context);
	}

	virtual void UpdateAnimationNode(const FAnimationUpdateContext& InContext) override
	{
		// All players are driven manually: the gait phase is solved on the game thread so Walk and
		// Run share one contact phase, and the action players own their own clocks.
		auto Setup = [](FAnimNode_SequencePlayer_Standalone& Node, UAnimSequence* Seq, bool bLoop)
		{
			if (Node.GetSequence() != Seq)
			{
				Node.SetSequence(Seq);
			}
			Node.SetLoopAnimation(bLoop);
			Node.SetPlayRate(0.f);
		};
		Setup(IdleNode, IdleSeq, true);
		Setup(WalkNode, WalkSeq, true);
		Setup(RunNode, RunSeq, true);
		Setup(ActionNodeA, ActionSeqA, bLoopA);
		Setup(ActionNodeB, ActionSeqB, bLoopB);

		IdleNode.Update_AnyThread(InContext);
		WalkNode.Update_AnyThread(InContext);
		RunNode.Update_AnyThread(InContext);
		ActionNodeA.Update_AnyThread(InContext);
		ActionNodeB.Update_AnyThread(InContext);

		if (IdleSeq && IdleSeq->GetPlayLength() > 0.f)
		{
			IdleNode.SetAccumulatedTime(FMath::Fmod(FMath::Max(0.f, IdleTime), IdleSeq->GetPlayLength()));
		}
		if (WalkSeq && WalkSeq->GetPlayLength() > 0.f)
		{
			WalkNode.SetAccumulatedTime(FMath::Fmod(FMath::Max(0.f, Phase), 1.f) * WalkSeq->GetPlayLength());
		}
		if (RunSeq && RunSeq->GetPlayLength() > 0.f)
		{
			RunNode.SetAccumulatedTime(FMath::Fmod(FMath::Max(0.f, Phase), 1.f) * RunSeq->GetPlayLength());
		}
		if (ActionSeqA && ActionSeqA->GetPlayLength() > 0.f)
		{
			const float Len = ActionSeqA->GetPlayLength();
			ActionNodeA.SetAccumulatedTime(bLoopA ? FMath::Fmod(FMath::Max(0.f, ActionTimeA), Len) : FMath::Clamp(ActionTimeA, 0.f, Len));
		}
		if (ActionSeqB && ActionSeqB->GetPlayLength() > 0.f)
		{
			const float Len = ActionSeqB->GetPlayLength();
			ActionNodeB.SetAccumulatedTime(bLoopB ? FMath::Fmod(FMath::Max(0.f, ActionTimeB), Len) : FMath::Clamp(ActionTimeB, 0.f, Len));
		}
	}

	virtual bool Evaluate(FPoseContext& Output) override
	{
		const float ActionTotal = ActionWA + ActionWB;
		const float BaseScale = FMath::Max(0.f, 1.f - FMath::Min(1.f, ActionTotal));

		float Weights[5] = {
			(IdleSeq ? IdleW : 0.f) * BaseScale,
			(WalkSeq ? WalkW : 0.f) * BaseScale,
			(RunSeq ? RunW : 0.f) * BaseScale,
			(ActionSeqA ? ActionWA : 0.f),
			(ActionSeqB ? ActionWB : 0.f),
		};
		float Total = 0.f;
		for (float W : Weights)
		{
			Total += FMath::Max(0.f, W);
		}
		if (Total <= KINDA_SMALL_NUMBER)
		{
			Output.ResetToRefPose();
			return true;
		}
		for (float& W : Weights)
		{
			W = FMath::Max(0.f, W) / Total;
		}

		FAnimNode_SequencePlayer_Standalone* Nodes[5] = { &IdleNode, &WalkNode, &RunNode, &ActionNodeA, &ActionNodeB };
		int32 ActiveCount = 0;
		int32 SingleIndex = INDEX_NONE;
		for (int32 Index = 0; Index < 5; ++Index)
		{
			if (Weights[Index] > 0.001f)
			{
				++ActiveCount;
				SingleIndex = Index;
			}
		}
		if (ActiveCount == 0)
		{
			Output.ResetToRefPose();
			return true;
		}
		// Most NPCs only run one player (idle, or a single action): evaluate it straight into the
		// output instead of allocating and blending a full pose set.
		if (ActiveCount == 1)
		{
			Nodes[SingleIndex]->Evaluate_AnyThread(Output);
			return true;
		}

		FPoseContext C0(this);
		FPoseContext C1(this);
		FPoseContext C2(this);
		FPoseContext C3(this);
		FPoseContext C4(this);
		FPoseContext* Contexts[5] = { &C0, &C1, &C2, &C3, &C4 };

		TArray<const FCompactPose*> Poses;
		TArray<const FBlendedCurve*> Curves;
		TArray<const UE::Anim::FStackAttributeContainer*> Attributes;
		TArray<float> ActiveWeights;
		Poses.Reserve(ActiveCount);
		Curves.Reserve(ActiveCount);
		Attributes.Reserve(ActiveCount);
		ActiveWeights.Reserve(ActiveCount);
		for (int32 Index = 0; Index < 5; ++Index)
		{
			if (Weights[Index] <= 0.001f)
			{
				continue;
			}
			Nodes[Index]->Evaluate_AnyThread(*Contexts[Index]);
			Poses.Add(&Contexts[Index]->Pose);
			Curves.Add(&Contexts[Index]->Curve);
			Attributes.Add(&Contexts[Index]->CustomAttributes);
			ActiveWeights.Add(Weights[Index]);
		}

		FAnimationPoseData OutData(Output);
		FAnimationRuntime::BlendPosesTogetherIndirect(
			TArrayView<const FCompactPose* const>(Poses.GetData(), Poses.Num()),
			TArrayView<const FBlendedCurve* const>(Curves.GetData(), Curves.Num()),
			TArrayView<const UE::Anim::FStackAttributeContainer* const>(Attributes.GetData(), Attributes.Num()),
			TArrayView<const float>(ActiveWeights.GetData(), ActiveWeights.Num()),
			OutData);
		return true;
	}
};

UDAAvatarAnimInstance::UDAAvatarAnimInstance()
{
}

FAnimInstanceProxy* UDAAvatarAnimInstance::CreateAnimInstanceProxy()
{
	return new FDAAnimInstanceProxy(this);
}

void UDAAvatarAnimInstance::NativeInitializeAnimation()
{
	Super::NativeInitializeAnimation();
	// A reinitialised instance must not inherit a previous mesh's action slot or
	// blend state; Configure() only replaces the locomotion takes.
	GroundSpeed = SwimAlpha = DuelAlpha = 0.f;
	SmoothedSpeed = 0.f;
	BlendedGroundSpeed = 0.f;
	Phase = 0.f;
	IdleTime = 0.f;
	IdleBlend = 1.f;
	WalkBlendValue = RunBlendValue = 0.f;
	WalkBlend = RunBlend = 0.f;
	ActionSequenceA = nullptr;
	ActionSequenceB = nullptr;
	ActionTimeA = ActionTimeB = 0.f;
	ActionWeightA = ActionWeightB = 0.f;
	ActionTargetA = 0.f;
	ActionPlayRateA = ActionPlayRateB = 1.f;
	ActionBlendRateA = ActionBlendRateB = 1.f / 0.2f;
	BlendedCadence = 0.f;
	bActionLoopA = bActionLoopB = false;
}

void UDAAvatarAnimInstance::Configure(const TMap<FName, TObjectPtr<UAnimSequence>>& InAnims, float InWalkSpeed, float InRunSpeed)
{
	IdleSequence = InAnims.FindRef(FName(TEXT("Idle")));
	WalkSequence = InAnims.FindRef(FName(TEXT("Walk")));
	RunSequence = InAnims.FindRef(FName(TEXT("Run")));
	WalkGroundSpeed = FMath::Max(1.f, InWalkSpeed);
	RunGroundSpeed = FMath::Max(WalkGroundSpeed + 1.f, InRunSpeed);
	BlendedGroundSpeed = 0.f;
	Phase = 0.f;
	IdleTime = 0.f;
	UE_LOG(LogTemp, Log, TEXT("DAAvatarAnim: configured %s idle=%s walk=%s run=%s walkSpeed=%.0f runSpeed=%.0f"),
		*GetName(), IdleSequence ? *IdleSequence->GetName() : TEXT("none"),
		WalkSequence ? *WalkSequence->GetName() : TEXT("none"), RunSequence ? *RunSequence->GetName() : TEXT("none"),
		WalkGroundSpeed, RunGroundSpeed);
}

void UDAAvatarAnimInstance::SetLocomotion(float InGroundSpeed, float InSwimAlpha, float InDuelAlpha)
{
	// W11: bInAir/VerticalSpeed were written here and never read by the
	// graph (the action layer in UDAAvatarComponent owns the air state), so
	// the feed and the fields are gone.
	GroundSpeed = FMath::Max(0.f, InGroundSpeed);
	SwimAlpha = FMath::Clamp(InSwimAlpha, 0.f, 1.f);
	DuelAlpha = FMath::Clamp(InDuelAlpha, 0.f, 1.f);
}

void UDAAvatarAnimInstance::SetAction(UAnimSequence* Sequence, bool bLoop, float InTargetWeight, float InPlayRate, float InBlendTime)
{
	const float BlendRate = 1.f / FMath::Max(InBlendTime, 0.02f);
	if (!Sequence)
	{
		return;
	}
	const bool bActionWasCleared = ActionTargetA <= KINDA_SMALL_NUMBER;
	if (ActionSequenceA == Sequence)
	{
		bActionLoopA = bLoop;
		ActionTargetA = FMath::Clamp(InTargetWeight, 0.f, 1.f);
		ActionPlayRateA = FMath::Max(0.f, InPlayRate);
		ActionBlendRateA = BlendRate;
		if (bActionWasCleared)
		{
			// ClearAction() leaves the old A at its final frame until the weight
			// has faded. Re-triggering the same take (a second landing, another
			// wave) must start it again, not resume the clamped tail.
			ActionTimeA = 0.f;
		}
		return;
	}

	// Crossfade: the outgoing action keeps its clock and weight in B while A starts
	// the new one. If the still-fading B is the stronger pose, keep it instead of
	// cutting a rapid Jump -> Fall -> Land chain short.
	if (ActionWeightB <= 0.002f || ActionWeightA >= ActionWeightB)
	{
		ActionSequenceB = ActionSequenceA;
		ActionTimeB = ActionTimeA;
		ActionWeightB = ActionWeightA;
		ActionPlayRateB = ActionPlayRateA;
		bActionLoopB = bActionLoopA;
	}
	// The outgoing pose fades out over the incoming action's blend time (a symmetric crossfade).
	ActionBlendRateB = BlendRate;

	ActionSequenceA = Sequence;
	ActionTimeA = 0.f;
	ActionWeightA = 0.f;
	ActionTargetA = FMath::Clamp(InTargetWeight, 0.f, 1.f);
	ActionPlayRateA = FMath::Max(0.f, InPlayRate);
	ActionBlendRateA = BlendRate;
	bActionLoopA = bLoop;
}

void UDAAvatarAnimInstance::ClearAction(float InBlendTime)
{
	ActionTargetA = 0.f;
	if (InBlendTime > 0.f)
	{
		ActionBlendRateA = 1.f / FMath::Max(InBlendTime, 0.02f);
	}
}

void UDAAvatarAnimInstance::SetActionPlayRate(float InPlayRate)
{
	ActionPlayRateA = FMath::IsFinite(InPlayRate) ? FMath::Max(0.f, InPlayRate) : 1.f;
}

float UDAAvatarAnimInstance::GetActionTimeRemaining() const
{
	if (!ActionSequenceA || bActionLoopA || ActionTargetA <= KINDA_SMALL_NUMBER)
	{
		return 0.f;
	}
	const float Rate = FMath::Max(ActionPlayRateA, KINDA_SMALL_NUMBER);
	return FMath::Max(0.f, ActionSequenceA->GetPlayLength() - ActionTimeA) / Rate;
}

void UDAAvatarAnimInstance::SetActionWeight(float InTargetWeight)
{
	ActionTargetA = FMath::Clamp(InTargetWeight, 0.f, 1.f);
}

void UDAAvatarAnimInstance::UpdateActionTimes(float DeltaSeconds)
{
	if (ActionSequenceA)
	{
		const float Len = ActionSequenceA->GetPlayLength();
		if (Len > 0.f)
		{
			ActionTimeA += DeltaSeconds * ActionPlayRateA;
			ActionTimeA = bActionLoopA ? FMath::Fmod(ActionTimeA, Len) : FMath::Min(ActionTimeA, Len);
		}
	}
	if (ActionSequenceB)
	{
		const float Len = ActionSequenceB->GetPlayLength();
		if (Len > 0.f)
		{
			ActionTimeB += DeltaSeconds * ActionPlayRateB;
			ActionTimeB = bActionLoopB ? FMath::Fmod(ActionTimeB, Len) : FMath::Min(ActionTimeB, Len);
		}
	}
}

void UDAAvatarAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
	Super::NativeUpdateAnimation(DeltaSeconds);

	const float Dt = FMath::Clamp(DeltaSeconds, 1.f / 240.f, 0.1f);

	// ---- speed ------------------------------------------------------------------------------
	// The feet must travel at the speed the capsule really moves. The character movement
	// component already limits acceleration, so only a light filter is applied (to hide
	// per-frame velocity jitter on stairs and slopes); a heavy one makes the legs lag behind
	// the body on every start, stop and sprint.
	const float PreviousSpeed = SmoothedSpeed;
	SmoothedSpeed = FMath::FInterpTo(SmoothedSpeed, GroundSpeed, Dt, SpeedFilterRate);
	BlendedGroundSpeed = SmoothedSpeed;
	const float Speed = SmoothedSpeed >= MinStepSpeed ? SmoothedSpeed : 0.f;

	// ---- clip strides ---------------------------------------------------------------------
	const float WalkLen = (WalkSequence && WalkSequence->GetPlayLength() > 0.f) ? WalkSequence->GetPlayLength() : 1.f;
	const float RunLen = (RunSequence && RunSequence->GetPlayLength() > 0.f) ? RunSequence->GetPlayLength() : 0.7333f;
	const float WalkStride = WalkGroundSpeed * WalkLen;   // cm travelled per cycle (two steps) at rate 1
	const float RunStride = RunGroundSpeed * RunLen;
	const float WalkCadence = 1.f / WalkLen;              // cycles per second at rate 1
	const float RunCadence = 1.f / RunLen;

	// ---- target blend from a human cadence model ---------------------------------------------
	// People do not slow down by keeping their step rate and shuffling: both the step length
	// and the step rate drop (step length ~ sqrt(speed) for a slow walk), and between a walk and
	// a run the cadence rises steadily. The blend weights are derived from the stride that
	// cadence implies, so the cadence actually played below is the realistic one *and* the
	// planted foot keeps moving at exactly the ground speed.
	float TargetIdle = 1.f;
	float TargetWalk = 0.f;
	float TargetRun = 0.f;
	if (Speed > 0.f)
	{
		if (Speed <= WalkGroundSpeed || !RunSequence)
		{
			// Stride = WalkStride * sqrt(v / Vwalk): the walk clip blended with the feet-together
			// idle shortens the step in proportion to the walk weight.
			TargetWalk = FMath::Clamp(FMath::Sqrt(Speed / WalkGroundSpeed), 0.f, 1.f);
			TargetIdle = 1.f - TargetWalk;
		}
		else if (Speed < RunGroundSpeed)
		{
			const float T = (Speed - WalkGroundSpeed) / FMath::Max(1.f, RunGroundSpeed - WalkGroundSpeed);
			const float Cadence = FMath::Lerp(WalkCadence, RunCadence, T);
			const float Stride = Speed / FMath::Max(Cadence, KINDA_SMALL_NUMBER);
			TargetRun = FMath::Clamp((Stride - WalkStride) / FMath::Max(1.f, RunStride - WalkStride), 0.f, 1.f);
			TargetWalk = 1.f - TargetRun;
			TargetIdle = 0.f;
		}
		else
		{
			TargetRun = 1.f;
			TargetWalk = 0.f;
			TargetIdle = 0.f;
		}
	}

	// Start every walk from a contact phase, so the idle -> walk blend reads as a first step
	// instead of fading into a random point of the cycle.
	if (PreviousSpeed < MinStepSpeed && SmoothedSpeed >= MinStepSpeed && WalkBlendValue + RunBlendValue < 0.05f)
	{
		Phase = 0.f;
	}

	IdleBlend = FMath::FInterpTo(IdleBlend, TargetIdle, Dt, LocomotionBlendSpeed);
	WalkBlendValue = FMath::FInterpTo(WalkBlendValue, TargetWalk, Dt, LocomotionBlendSpeed);
	RunBlendValue = FMath::FInterpTo(RunBlendValue, TargetRun, Dt, LocomotionBlendSpeed);
	const float WeightSum = IdleBlend + WalkBlendValue + RunBlendValue;
	if (WeightSum > KINDA_SMALL_NUMBER)
	{
		IdleBlend /= WeightSum;
		WalkBlendValue /= WeightSum;
		RunBlendValue /= WeightSum;
	}
	else
	{
		IdleBlend = 1.f;
		WalkBlendValue = RunBlendValue = 0.f;
	}
	WalkBlend = WalkBlendValue;
	RunBlend = RunBlendValue;

	// ---- cadence -----------------------------------------------------------------------------
	// One gait phase drives both clips. The cadence is solved from the stride of the pose that
	// is actually shown (the blended weights, idle contributing no stride), so the planted
	// contact travels backwards at exactly the current speed. While the weights are still
	// catching up the solved cadence is limited to a human range instead of spinning the legs.
	const float ShownStride = WalkBlendValue * WalkStride + RunBlendValue * RunStride;
	float Cadence = 0.f;
	if (Speed > 0.f && ShownStride > 1.f)
	{
		Cadence = FMath::Min(Speed / ShownStride, MaxCadenceScale * RunCadence);
	}
	BlendedCadence = Cadence;
	Phase = FMath::Fmod(Phase + Cadence * Dt, 1.f);

	const float IdleLen = (IdleSequence && IdleSequence->GetPlayLength() > 0.f) ? IdleSequence->GetPlayLength() : 8.f;
	IdleTime = FMath::Fmod(IdleTime + Dt, IdleLen);

	// Action layer: crossfade in/out and keep a second outgoing action alive during switches.
	// Linear (constant-time) fades read as a deliberate crossfade; the rate is per action
	// (a landing snaps in, a wave eases in).
	ActionWeightA = FMath::FInterpConstantTo(ActionWeightA, ActionTargetA, Dt, ActionBlendRateA);
	ActionWeightB = FMath::FInterpConstantTo(ActionWeightB, 0.f, Dt, ActionBlendRateB);
	// Drop finished slots so their sequences do not linger at zero weight. A is
	// only released after its fade-out; B always fades out on its own.
	if (ActionWeightA < 0.002f && ActionTargetA <= KINDA_SMALL_NUMBER)
	{
		ActionSequenceA = nullptr;
		ActionTimeA = 0.f;
		ActionWeightA = 0.f;
	}
	if (ActionSequenceB && ActionWeightB < 0.002f)
	{
		ActionSequenceB = nullptr;
		ActionTimeB = 0.f;
		ActionWeightB = 0.f;
	}
	UpdateActionTimes(Dt);

	FDAAnimInstanceProxy& Proxy = GetProxyOnGameThread<FDAAnimInstanceProxy>();
	Proxy.IdleSeq = IdleSequence;
	Proxy.WalkSeq = WalkSequence;
	Proxy.RunSeq = RunSequence;
	Proxy.ActionSeqA = ActionSequenceA;
	Proxy.ActionSeqB = ActionSequenceB;
	Proxy.IdleTime = IdleTime;
	Proxy.Phase = Phase;
	Proxy.IdleW = IdleBlend;
	Proxy.WalkW = WalkBlendValue;
	Proxy.RunW = RunBlendValue;
	Proxy.ActionWA = ActionWeightA;
	Proxy.ActionWB = ActionWeightB;
	Proxy.ActionTimeA = ActionTimeA;
	Proxy.ActionTimeB = ActionTimeB;
	Proxy.bLoopA = bActionLoopA;
	Proxy.bLoopB = bActionLoopB;
}
