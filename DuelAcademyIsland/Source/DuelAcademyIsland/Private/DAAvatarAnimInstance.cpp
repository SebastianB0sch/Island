// Duel Academy Island - native locomotion anim instance implementation.

#include "DAAvatarAnimInstance.h"

#include "Animation/AnimNodeBase.h"
#include "Animation/AnimNode_SequencePlayer.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"
#include "BonePose.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"

namespace
{
	constexpr float IdleBlendSpeed = 16.f;
	constexpr float ActionBlendSpeed = 14.f;

	// Look-at limits (degrees) and the share of the turn taken by the neck (the head does the rest).
	constexpr float LookMaxYaw = 65.f;
	constexpr float LookMaxPitch = 28.f;
	constexpr float LookNeckShare = 0.4f;

	// Mesh-space forward of the cast (authored facing UE +Y, see UDAAvatarComponent).
	const FVector MeshForward(0.0, 1.0, 0.0);

	/** Spring parameters by bone-name class (VRM spring bone conventions, lengths in cm). */
	struct FDASpringParams
	{
		float Stiffness = 1.f;   // pull back to the animated direction (per second)
		float Drag = 0.4f;       // 0 = keeps swinging, 1 = no inertia
		float Gravity = 0.2f;    // m/s^2-ish pull down (VRM gravityPower)
		bool bHeadCollide = false;
	};

	bool SpringParamsFor(const FString& Name, FDASpringParams& Out)
	{
		if (Name.StartsWith(TEXT("HairJoint")) || Name.Contains(TEXT("Hair")))
		{
			Out = { 1.1f, 0.42f, 0.18f, true };
			return true;
		}
		if (Name.StartsWith(TEXT("skirt_")))
		{
			Out = { 2.2f, 0.55f, 0.3f, false };
			return true;
		}
		if (Name.StartsWith(TEXT("coattail_")) || Name.Contains(TEXT("CoatSkirt")))
		{
			Out = { 1.6f, 0.5f, 0.35f, false };
			return true;
		}
		if (Name.Contains(TEXT("Bust")) || Name.Contains(TEXT("Hood")))
		{
			return false;       // body helpers / the removed VRoid hoodie: no secondary motion
		}
		if (Name.StartsWith(TEXT("J_Sec_")))
		{
			Out = { 1.4f, 0.5f, 0.2f, false };
			return true;
		}
		return false;
	}

	const TCHAR* VisemeNames[5] = { TEXT("A"), TEXT("I"), TEXT("U"), TEXT("E"), TEXT("O") };
	const TCHAR* EmotionNames[5] = { TEXT("Joy"), TEXT("Angry"), TEXT("Sorrow"), TEXT("Surprised"), TEXT("Fun") };
}

/** One spring chain: bones root -> tip (the last bone only provides the tail of the one before it). */
struct FDASpringChain
{
	TArray<FBoneIndexType> SkeletonBones;          // mesh (reference skeleton) indices
	TArray<FCompactPoseBoneIndex> Bones;           // resolved per CacheBones
	TArray<FVector> CurTail;                       // world space, per joint (Bones.Num() - 1)
	TArray<FVector> PrevTail;
	FDASpringParams Params;
	bool bValid = false;
	bool bInitialised = false;
};

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

	// procedural layer (written on the game thread before the parallel update)
	FTransform SimComponentToWorld = FTransform::Identity;
	float SimDt = 0.f;               // > 0 once per game frame: the springs integrate only then
	bool bSprings = true;
	float LookAlpha = 0.f;
	FVector LookTargetCS = FVector::ZeroVector;

	// worker-thread state
	TArray<FDASpringChain> Chains;
	bool bChainsBuilt = false;
	FCompactPoseBoneIndex HeadIndex = FCompactPoseBoneIndex(INDEX_NONE);
	FCompactPoseBoneIndex NeckIndex = FCompactPoseBoneIndex(INDEX_NONE);
	FVector LastHeadWorld = FVector::ZeroVector;
	// stats for the game thread (read in NativeUpdateAnimation, after the previous evaluation)
	int32 StatChains = 0;
	float StatMaxDeflection = 0.f;

	void BuildChains(const FReferenceSkeleton& Ref)
	{
		Chains.Reset();
		const int32 Num = Ref.GetNum();
		TArray<TArray<int32>> Children;
		Children.SetNum(Num);
		for (int32 i = 0; i < Num; ++i)
		{
			const int32 P = Ref.GetParentIndex(i);
			if (P != INDEX_NONE)
			{
				Children[P].Add(i);
			}
		}
		FDASpringParams Params;
		for (int32 i = 0; i < Num; ++i)
		{
			const FString Name = Ref.GetBoneName(i).ToString();
			if (!SpringParamsFor(Name, Params))
			{
				continue;
			}
			const int32 P = Ref.GetParentIndex(i);
			FDASpringParams Unused;
			if (P != INDEX_NONE && SpringParamsFor(Ref.GetBoneName(P).ToString(), Unused))
			{
				continue;           // not a chain root
			}
			FDASpringChain Chain;
			Chain.Params = Params;
			int32 B = i;
			while (B != INDEX_NONE && Chain.SkeletonBones.Num() < 8)
			{
				Chain.SkeletonBones.Add(static_cast<FBoneIndexType>(B));
				B = Children[B].Num() ? Children[B][0] : INDEX_NONE;
			}
			if (Chain.SkeletonBones.Num() >= 2)
			{
				Chains.Add(MoveTemp(Chain));
			}
		}
		bChainsBuilt = true;
	}

	void ResolveBones()
	{
		const FBoneContainer& BC = GetRequiredBones();
		if (!BC.IsValid())
		{
			return;
		}
		if (!bChainsBuilt)
		{
			BuildChains(BC.GetReferenceSkeleton());
		}
		auto Resolve = [&BC](int32 MeshIndex) -> FCompactPoseBoneIndex
		{
			if (MeshIndex == INDEX_NONE)
			{
				return FCompactPoseBoneIndex(INDEX_NONE);
			}
			return BC.MakeCompactPoseIndex(FMeshPoseBoneIndex(MeshIndex));
		};
		const FReferenceSkeleton& Ref = BC.GetReferenceSkeleton();
		HeadIndex = Resolve(Ref.FindBoneIndex(TEXT("head")));
		NeckIndex = Resolve(Ref.FindBoneIndex(TEXT("neck_01")));
		for (FDASpringChain& Chain : Chains)
		{
			Chain.Bones.Reset();
			Chain.bValid = true;
			for (FBoneIndexType B : Chain.SkeletonBones)
			{
				const FCompactPoseBoneIndex C = Resolve(B);
				if (C.GetInt() == INDEX_NONE)
				{
					Chain.bValid = false;      // a LOD dropped part of the chain
					break;
				}
				Chain.Bones.Add(C);
			}
			Chain.bInitialised = false;
		}
	}

	/** Neck + head turn towards LookTargetCS (component space), blended by LookAlpha. */
	void ApplyLookAt(FCSPose<FCompactPose>& CS)
	{
		if (LookAlpha <= 0.001f || HeadIndex.GetInt() == INDEX_NONE || NeckIndex.GetInt() == INDEX_NONE)
		{
			return;
		}
		const FTransform NeckCS = CS.GetComponentSpaceTransform(NeckIndex);
		const FCompactPose& Local = CS.GetPose();
		const FTransform HeadCS = Local[HeadIndex] * NeckCS;
		FVector To = LookTargetCS - HeadCS.GetLocation();
		if (To.SizeSquared() < 100.f)
		{
			return;
		}
		To.Normalize();
		// clamp yaw / pitch relative to the body's forward (+Y in mesh space)
		float Yaw = static_cast<float>(FMath::RadiansToDegrees(FMath::Atan2(To.X, To.Y)));
		float Pitch = static_cast<float>(FMath::RadiansToDegrees(FMath::Asin(FMath::Clamp(To.Z, -1.0, 1.0))));
		const float Fade = 1.f - FMath::SmoothStep(LookMaxYaw + 15.f, LookMaxYaw + 60.f, FMath::Abs(Yaw));   // behind: let go
		Yaw = FMath::Clamp(Yaw, -LookMaxYaw, LookMaxYaw);
		Pitch = FMath::Clamp(Pitch, -LookMaxPitch, LookMaxPitch);
		const float Yr = FMath::DegreesToRadians(Yaw);
		const float Pr = FMath::DegreesToRadians(Pitch);
		const FVector Want(FMath::Sin(Yr) * FMath::Cos(Pr), FMath::Cos(Yr) * FMath::Cos(Pr), FMath::Sin(Pr));
		const FQuat Full = FQuat::FindBetweenNormals(MeshForward, Want);
		const float A = LookAlpha * Fade;
		const FQuat NeckRot = FQuat::Slerp(FQuat::Identity, Full, A * LookNeckShare);
		const FQuat HeadRot = FQuat::Slerp(FQuat::Identity, Full, A * (1.f - LookNeckShare));
		FTransform NewNeck = NeckCS;
		NewNeck.SetRotation((NeckRot * NeckCS.GetRotation()).GetNormalized());
		FTransform NewHead = HeadCS;
		NewHead.SetLocation(NeckCS.GetLocation() + NeckRot.RotateVector(HeadCS.GetLocation() - NeckCS.GetLocation()));
		NewHead.SetRotation((HeadRot * NeckRot * HeadCS.GetRotation()).GetNormalized());
		CS.SetComponentSpaceTransform(NeckIndex, NewNeck);
		CS.SetComponentSpaceTransform(HeadIndex, NewHead);
	}

	/** VRM spring bones: each joint's tail is a verlet particle pulled back to its animated direction. */
	void ApplySprings(FCSPose<FCompactPose>& CS)
	{
		if (!bSprings || Chains.Num() == 0)
		{
			return;
		}
		const float Dt = FMath::Clamp(SimDt, 0.f, 1.f / 20.f);
		const FCompactPose& Local = CS.GetPose();
		// head sphere (hair must not swing into the face / skull)
		FVector HeadCenterW = FVector::ZeroVector;
		float HeadRadius = 0.f;
		bool bTeleported = false;
		if (HeadIndex.GetInt() != INDEX_NONE)
		{
			const FTransform HeadCS = CS.GetComponentSpaceTransform(HeadIndex);
			const float Scale = static_cast<float>(SimComponentToWorld.GetScale3D().Z);
			HeadCenterW = SimComponentToWorld.TransformPosition(HeadCS.GetLocation() + FVector(0.0, -1.0, 9.0));
			HeadRadius = 9.5f * Scale;
			bTeleported = !LastHeadWorld.IsZero() && FVector::DistSquared(LastHeadWorld, HeadCenterW) > FMath::Square(120.f);
			LastHeadWorld = HeadCenterW;
		}
		const FVector GravityDir(0.0, 0.0, -1.0);
		int32 ValidChains = 0;
		float MaxDeflection = 0.f;
		for (FDASpringChain& Chain : Chains)
		{
			if (!Chain.bValid)
			{
				continue;
			}
			const int32 Joints = Chain.Bones.Num() - 1;
			if (Chain.CurTail.Num() != Joints)
			{
				Chain.CurTail.SetNum(Joints);
				Chain.PrevTail.SetNum(Joints);
				Chain.bInitialised = false;
			}
			for (int32 j = 0; j < Joints; ++j)
			{
				const FCompactPoseBoneIndex B = Chain.Bones[j];
				const FCompactPoseBoneIndex Child = Chain.Bones[j + 1];
				const FTransform BoneCS = CS.GetComponentSpaceTransform(B);
				const FVector AnimTailCS = (Local[Child] * BoneCS).GetLocation();
				const FVector HeadW = SimComponentToWorld.TransformPosition(BoneCS.GetLocation());
				const FVector AnimTailW = SimComponentToWorld.TransformPosition(AnimTailCS);
				const FVector RestW = AnimTailW - HeadW;
				const float Len = static_cast<float>(RestW.Size());
				if (Len < KINDA_SMALL_NUMBER)
				{
					continue;
				}
				if (!Chain.bInitialised || bTeleported)
				{
					Chain.CurTail[j] = Chain.PrevTail[j] = AnimTailW;
				}
				FVector Next = Chain.CurTail[j];
				if (Dt > 0.f)
				{
					const FVector Inertia = (Chain.CurTail[j] - Chain.PrevTail[j]) * (1.f - Chain.Params.Drag);
					// stiffness scaled by the bone length so short and long bones behave alike (VRM is in metres)
					const FVector Stiff = (RestW / Len) * (Chain.Params.Stiffness * Dt * Len * 20.f);
					const FVector Grav = GravityDir * (Chain.Params.Gravity * Dt * 100.f);
					Next = Chain.CurTail[j] + Inertia + Stiff + Grav;
				}
				Next = HeadW + (Next - HeadW).GetSafeNormal() * Len;
				if (Chain.Params.bHeadCollide && HeadRadius > 0.f)
				{
					// never push a strand further out than its own animated rest (bangs lie close to the face)
					const float Radius = FMath::Min(HeadRadius, 0.95f * static_cast<float>(FVector::Dist(AnimTailW, HeadCenterW)));
					const FVector Off = Next - HeadCenterW;
					const float D = static_cast<float>(Off.Size());
					if (D < Radius && D > KINDA_SMALL_NUMBER)
					{
						Next = HeadCenterW + Off / D * Radius;
						Next = HeadW + (Next - HeadW).GetSafeNormal() * Len;
					}
				}
				if (Dt > 0.f)
				{
					Chain.PrevTail[j] = Chain.CurTail[j];
					Chain.CurTail[j] = Next;
				}
				const FVector SimCS = SimComponentToWorld.InverseTransformVectorNoScale(Next - HeadW).GetSafeNormal();
				const FVector AnimCS = (AnimTailCS - BoneCS.GetLocation()).GetSafeNormal();
				if (SimCS.IsNearlyZero() || AnimCS.IsNearlyZero())
				{
					continue;
				}
				const FQuat Delta = FQuat::FindBetweenNormals(AnimCS, SimCS);
				MaxDeflection = FMath::Max(MaxDeflection, FMath::RadiansToDegrees(static_cast<float>(Delta.GetAngle())));
				FTransform NewCS = BoneCS;
				NewCS.SetRotation((Delta * BoneCS.GetRotation()).GetNormalized());
				CS.SetComponentSpaceTransform(B, NewCS);
			}
			Chain.bInitialised = true;
			++ValidChains;
		}
		StatChains = ValidChains;
		StatMaxDeflection = MaxDeflection;
		SimDt = 0.f;
	}

	void ApplyProcedural(FPoseContext& Output)
	{
		const bool bAny = (bSprings && Chains.Num() > 0) || LookAlpha > 0.001f;
		if (!bAny)
		{
			SimDt = 0.f;
			return;
		}
		FCSPose<FCompactPose> CS;
		CS.InitPose(Output.Pose);
		ApplyLookAt(CS);
		ApplySprings(CS);
		FCSPose<FCompactPose>::ConvertComponentPosesToLocalPoses(MoveTemp(CS), Output.Pose);
	}

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
		ResolveBones();
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

	bool EvaluateBase(FPoseContext& Output)
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
	virtual bool Evaluate(FPoseContext& Output) override
	{
		const bool bResult = EvaluateBase(Output);
		ApplyProcedural(Output);
		return bResult;
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
	bActionLoopA = bActionLoopB = false;
	bTalking = false;
	bLookAt = false;
	LookAlpha = 0.f;
	EmotionTargets.Reset();
	EmotionWeights.Reset();
	FaceRng.Initialize(static_cast<int32>(GetTypeHash(GetOuter() ? GetOuter()->GetFName() : NAME_None)));
	BlinkTimer = FaceRng.FRandRange(0.5f, 3.f);
	BlinkClock = -1.f;
	bHasFace = false;
	if (const USkeletalMeshComponent* Comp = GetSkelMeshComponent())
	{
		if (const USkeletalMesh* Mesh = Comp->GetSkeletalMeshAsset())
		{
			bHasFace = Mesh->FindMorphTarget(TEXT("Blink")) != nullptr;
		}
	}
}

void UDAAvatarAnimInstance::SetEmotion(FName Emotion, float Weight)
{
	if (Emotion.IsNone())
	{
		for (TPair<FName, float>& Pair : EmotionTargets)
		{
			Pair.Value = 0.f;
		}
		return;
	}
	EmotionTargets.FindOrAdd(Emotion) = FMath::Clamp(Weight, 0.f, 1.f);
}

void UDAAvatarAnimInstance::SetLookAtTarget(const FVector& WorldLocation, bool bEnable)
{
	LookTargetWorld = WorldLocation;
	bLookAt = bEnable;
}

void UDAAvatarAnimInstance::UpdateFace(float Dt)
{
	if (!bHasFace)
	{
		return;
	}
	// Blink: close 0.07 s, hold 0.04 s, open 0.12 s; every 2-6 s, one in five a double blink.
	float Blink = 0.f;
	BlinkTimer -= Dt;
	if (BlinkTimer <= 0.f && BlinkClock < 0.f)
	{
		BlinkClock = 0.f;
		bDoubleBlink = FaceRng.FRand() < 0.2f;
	}
	if (BlinkClock >= 0.f)
	{
		BlinkClock += Dt;
		auto Curve = [](float T)
		{
			if (T < 0.07f) return T / 0.07f;
			if (T < 0.11f) return 1.f;
			if (T < 0.23f) return 1.f - (T - 0.11f) / 0.12f;
			return 0.f;
		};
		Blink = Curve(BlinkClock);
		if (bDoubleBlink && BlinkClock > 0.26f)
		{
			Blink = Curve(BlinkClock - 0.26f);
		}
		if (BlinkClock > (bDoubleBlink ? 0.5f : 0.24f))
		{
			BlinkClock = -1.f;
			BlinkTimer = FaceRng.FRandRange(2.f, 6.f);
		}
	}
	SetMorphTarget(TEXT("Blink"), FMath::SmoothStep(0.f, 1.f, Blink));

	// Lip-sync: a new vowel every 70-150 ms (with an occasional closed-mouth pause), eased per viseme.
	float Targets[5] = { 0.f, 0.f, 0.f, 0.f, 0.f };
	if (bTalking)
	{
		TalkClock += Dt;
		VisemeHold -= Dt;
		if (VisemeHold <= 0.f)
		{
			VisemeHold = FaceRng.FRandRange(0.07f, 0.15f);
			Viseme = FaceRng.FRand() < 0.15f ? INDEX_NONE : FaceRng.RandRange(0, 4);
		}
		if (Viseme != INDEX_NONE)
		{
			Targets[Viseme] = Viseme == 0 ? 0.75f : 0.6f;      // "A" opens widest
		}
	}
	else
	{
		TalkClock = 0.f;
	}
	for (int32 i = 0; i < 5; ++i)
	{
		VisemeWeights[i] = FMath::FInterpTo(VisemeWeights[i], Targets[i], Dt, 22.f);
		SetMorphTarget(VisemeNames[i], VisemeWeights[i]);
	}

	for (const TCHAR* Name : EmotionNames)
	{
		const FName Key(Name);
		const float Target = EmotionTargets.FindRef(Key);
		float& W = EmotionWeights.FindOrAdd(Key);
		W = FMath::FInterpTo(W, Target, Dt, 6.f);
		// the emotion's own eyes compete with the blink: blinking wins
		SetMorphTarget(Key, W * (1.f - 0.6f * Blink));
	}
}

void UDAAvatarAnimInstance::Configure(const TMap<FName, TObjectPtr<UAnimSequence>>& InAnims, float InWalkSpeed, float InRunSpeed)
{
	IdleSequence = InAnims.FindRef(FName(TEXT("Idle")));
	WalkSequence = InAnims.FindRef(FName(TEXT("Walk")));
	RunSequence = InAnims.FindRef(FName(TEXT("Run")));
	WalkGroundSpeed = FMath::Max(1.f, InWalkSpeed);
	RunGroundSpeed = FMath::Max(WalkGroundSpeed + 1.f, InRunSpeed);
	if (const USkeletalMeshComponent* Comp = GetSkelMeshComponent())
	{
		const USkeletalMesh* Mesh = Comp->GetSkeletalMeshAsset();
		bHasFace = Mesh && Mesh->FindMorphTarget(TEXT("Blink")) != nullptr;
	}
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

void UDAAvatarAnimInstance::SetAction(UAnimSequence* Sequence, bool bLoop, float InTargetWeight, float InPlayRate)
{
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

	ActionSequenceA = Sequence;
	ActionTimeA = 0.f;
	ActionWeightA = 0.f;
	ActionTargetA = FMath::Clamp(InTargetWeight, 0.f, 1.f);
	ActionPlayRateA = FMath::Max(0.f, InPlayRate);
	bActionLoopA = bLoop;
}

void UDAAvatarAnimInstance::ClearAction()
{
	ActionTargetA = 0.f;
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
	const float PreviousSpeed = SmoothedSpeed;
	SmoothedSpeed = FMath::FInterpTo(SmoothedSpeed, GroundSpeed, Dt, 10.f);
	BlendedGroundSpeed = SmoothedSpeed;
	// Start every walk from a contact phase, so the idle -> walk blend reads as a first step
	// instead of fading into a random point of the cycle.
	if (PreviousSpeed < 1.f && SmoothedSpeed >= 1.f)
	{
		Phase = 0.f;
	}

	// Blend Idle -> Walk -> Run by speed. Below the walk speed the walk plays at its natural
	// cadence and fades to idle, which keeps the tiny steps of a slow start in sync too.
	float TargetIdle = 0.f;
	float TargetWalk = 0.f;
	float TargetRun = 0.f;
	if (SmoothedSpeed <= WalkGroundSpeed)
	{
		TargetWalk = WalkGroundSpeed > 0.f ? FMath::Clamp(SmoothedSpeed / WalkGroundSpeed, 0.f, 1.f) : 0.f;
		TargetIdle = 1.f - TargetWalk;
	}
	else
	{
		TargetRun = FMath::Clamp((SmoothedSpeed - WalkGroundSpeed) / FMath::Max(1.f, RunGroundSpeed - WalkGroundSpeed), 0.f, 1.f);
		TargetWalk = 1.f - TargetRun;
	}

	IdleBlend = FMath::FInterpTo(IdleBlend, TargetIdle, Dt, IdleBlendSpeed);
	WalkBlendValue = FMath::FInterpTo(WalkBlendValue, TargetWalk, Dt, IdleBlendSpeed);
	RunBlendValue = FMath::FInterpTo(RunBlendValue, TargetRun, Dt, IdleBlendSpeed);
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

	// One gait phase drives both clips; the cadence is solved from the blended stride so the
	// planted contact travels backwards at exactly SmoothedSpeed (no sliding).
	const float WalkLen = (WalkSequence && WalkSequence->GetPlayLength() > 0.f) ? WalkSequence->GetPlayLength() : 0.8f;
	const float RunLen = (RunSequence && RunSequence->GetPlayLength() > 0.f) ? RunSequence->GetPlayLength() : 0.4667f;
	float Cadence = 0.f;
	if (SmoothedSpeed > 1.f)
	{
		if (SmoothedSpeed <= WalkGroundSpeed)
		{
			Cadence = 1.f / WalkLen;
		}
		else
		{
			const float WalkStride = WalkGroundSpeed * WalkLen;
			const float RunStride = RunGroundSpeed * RunLen;
			const float Stride = RunBlendValue * RunStride + WalkBlendValue * WalkStride;
			Cadence = Stride > 1.f ? SmoothedSpeed / Stride : 0.f;
		}
	}
	Phase = FMath::Fmod(Phase + Cadence * Dt, 1.f);

	const float IdleLen = (IdleSequence && IdleSequence->GetPlayLength() > 0.f) ? IdleSequence->GetPlayLength() : 3.f;
	IdleTime = FMath::Fmod(IdleTime + Dt, IdleLen);

	// Action layer: crossfade in/out and keep a second outgoing action alive during switches.
	ActionWeightA = FMath::FInterpTo(ActionWeightA, ActionTargetA, Dt, ActionBlendSpeed);
	ActionWeightB = FMath::FInterpTo(ActionWeightB, 0.f, Dt, ActionBlendSpeed);
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

	// procedural layer: springs integrate once per game frame in world space; look-at target in mesh space
	if (const USkeletalMeshComponent* Comp = GetSkelMeshComponent())
	{
		Proxy.SimComponentToWorld = Comp->GetComponentTransform();
		LookAlpha = FMath::FInterpTo(LookAlpha, bLookAt ? 1.f : 0.f, Dt, 4.f);
		Proxy.LookAlpha = LookAlpha * (1.f - FMath::Clamp(ActionWeightA + ActionWeightB, 0.f, 1.f) * 0.7f);
		Proxy.LookTargetCS = Proxy.SimComponentToWorld.InverseTransformPosition(LookTargetWorld);
	}
	Proxy.SimDt = Dt;
	Proxy.bSprings = bSecondaryMotion;
	SpringChainCount = Proxy.StatChains;
	SpringDeflection = Proxy.StatMaxDeflection;
	UpdateFace(Dt);
}
