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
		bool bLegCollide = false;   // skirts / coat tails: kept out of the thigh and calf capsules
		float Cohesion = 0.f;       // 0 .. 1: pull towards the neighbouring chains' motion (hair moves as a mass)
		float Inertia = 1.f;        // share of the character's own motion the tails lag behind (1 = pure world space)
		float MaxAngle = 0.f;       // degrees from the animated direction (0 = free)
		bool bBodyCollide = false;  // long hair: kept on the back / shoulders (upper body capsule)
	};

	// leg capsule radii (cm, mesh scale): thigh at the hip / knee, calf at the knee / ankle
	constexpr float ThighRadius = 8.5f;
	constexpr float CalfRadius = 6.0f;

	FVector ClosestOnSegment(const FVector& P, const FVector& A, const FVector& B)
	{
		const FVector AB = B - A;
		const double T = FMath::Clamp(FVector::DotProduct(P - A, AB) / FMath::Max(AB.SizeSquared(), 1e-6), 0.0, 1.0);
		return A + AB * T;
	}

	bool SpringParamsFor(const FString& Name, FDASpringParams& Out)
	{
		if (Name.StartsWith(TEXT("HairJoint")) || Name.Contains(TEXT("Hair")))
		{
			// Tools/dai/anime/hairrig.py: HairJoint_<Key>_Short<nn>_<j> (styled hair over the head: stiff, nearly
			// weightless, it bounces and settles back into shape) and HairJoint_<Key>_Long<nn>_<j> (long hair
			// below the neck: heavier, swings further, lies on the back)
			Out = FDASpringParams();
			Out.bHeadCollide = true;
			if (Name.Contains(TEXT("_Long")))
			{
				Out.Stiffness = 1.6f;
				Out.Drag = 0.5f;
				Out.Gravity = 0.06f;      // the hair is modelled hanging: gravity is only a hint of weight
				Out.Cohesion = 0.5f;
				Out.MaxAngle = 50.f;
				Out.Inertia = 0.15f;
				Out.bBodyCollide = true;
			}
			else
			{
				Out.Stiffness = 3.0f;
				Out.Drag = 0.6f;
				Out.Gravity = 0.05f;
				Out.Cohesion = 0.6f;
				Out.MaxAngle = 18.f;
				Out.Inertia = 0.05f;
			}
			return true;
		}
		if (Name.StartsWith(TEXT("skirt_")))
		{
			Out = { 2.2f, 0.55f, 0.3f, false, true };
			return true;
		}
		if (Name.StartsWith(TEXT("coattail_")) || Name.Contains(TEXT("CoatSkirt")))
		{
			Out = { 1.6f, 0.5f, 0.35f, false, true };
			return true;
		}
		if (Name.Contains(TEXT("Bust")) || Name.Contains(TEXT("Hood")))
		{
			return false;       // body helpers: no secondary motion
		}
		if (Name.StartsWith(TEXT("J_Sec_")))
		{
			Out = { 1.4f, 0.5f, 0.2f, false };
			return true;
		}
		return false;
	}

	const TCHAR* VisemeNames[5] = { TEXT("A"), TEXT("I"), TEXT("U"), TEXT("E"), TEXT("O") };

	// Cloth corrective keys (Tools/dai/anime/correctives.py): chains of key angles along one motion.
	// Index: 0..2 forward pitch, 3..4 backward pitch, 5 spread, 6..7 knee flexion.
	struct FDAFitKey { const TCHAR* Name; int32 Chain; float Angle; };
	const FDAFitKey FitKeys[] = {
		{ TEXT("HipFwd1"), 0, 25.f }, { TEXT("HipFwd"), 0, 50.f }, { TEXT("HipFwd2"), 0, 90.f },
		{ TEXT("HipBack1"), 1, 15.f }, { TEXT("HipBack"), 1, 30.f },
		{ TEXT("HipOut"), 2, 30.f },
		{ TEXT("KneeBend1"), 3, 60.f }, { TEXT("KneeBend"), 3, 110.f },
	};
	constexpr int32 NumFitKeys = UE_ARRAY_COUNT(FitKeys);

	/** Tent weight of key K for the motion amount X (>= 0) along its chain (the last key extrapolates to 1.2). */
	float FitTent(int32 K, float X)
	{
		const int32 Chain = FitKeys[K].Chain;
		float Prev = 0.f;
		for (int32 J = K - 1; J >= 0; --J)
		{
			if (FitKeys[J].Chain == Chain)
			{
				Prev = FitKeys[J].Angle;
				break;
			}
		}
		const bool bLast = K + 1 >= NumFitKeys || FitKeys[K + 1].Chain != Chain;
		const float A = FitKeys[K].Angle;
		if (X <= Prev)
		{
			return 0.f;
		}
		if (!bLast && X >= FitKeys[K + 1].Angle)
		{
			return 0.f;
		}
		if (X <= A)
		{
			return (X - Prev) / FMath::Max(A - Prev, 1e-3f);
		}
		if (bLast)
		{
			return FMath::Min(1.2f, X / A);
		}
		return (FitKeys[K + 1].Angle - X) / FMath::Max(FitKeys[K + 1].Angle - A, 1e-3f);
	}

	/** Angle (deg) of K in the plane (A, -Up) - correctives.angles() */
	float PlaneAngle(const FVector& K, const FVector& A, const FVector& Up)
	{
		return FMath::RadiansToDegrees(static_cast<float>(FMath::Atan2(FVector::DotProduct(K, A), -FVector::DotProduct(K, Up))));
	}

	float BendAngle(const FVector& Hip, const FVector& Knee, const FVector& Ankle)
	{
		const FVector U = (Knee - Hip).GetSafeNormal();
		const FVector V = (Ankle - Knee).GetSafeNormal();
		return FMath::RadiansToDegrees(static_cast<float>(FMath::Acos(FMath::Clamp(FVector::DotProduct(U, V), -1.0, 1.0))));
	}
	const TCHAR* EmotionNames[5] = { TEXT("Joy"), TEXT("Angry"), TEXT("Sorrow"), TEXT("Surprised"), TEXT("Fun") };

	/** Weight interpolation rate of the idle / walk / run blend (1/s). */
	constexpr float LocomotionBlendSpeed = 14.f;
	/** Ground-speed filter (1/s): only hides velocity jitter, ~50 ms lag. */
	constexpr float SpeedFilterRate = 20.f;
	/** Below this ground speed (cm/s) the character stands; no micro-steps. */
	constexpr float MinStepSpeed = 6.f;
	/** Upper limit of the solved cadence, relative to the run clip's own cadence. */
	constexpr float MaxCadenceScale = 1.35f;
}

/** One spring chain: bones root -> tip (the last bone only provides the tail of the one before it). */
struct FDASpringChain
{
	TArray<FBoneIndexType> SkeletonBones;          // mesh (reference skeleton) indices
	TArray<FCompactPoseBoneIndex> Bones;           // resolved per CacheBones
	TArray<FVector> CurTail;                       // world space, per joint (Bones.Num() - 1)
	TArray<FVector> PrevTail;
	FDASpringParams Params;
	TArray<int32> Neighbours;                      // chains of the same hair (index into Chains) next to this one
	bool bValid = false;
	bool bInitialised = false;
};

// ---- rider IK begin (extracted by Tools/tests/rider/extract.py and compiled against Tools/tests/springs/ue_mock.h)
/**
 * Motorcycle rider IK on the cast skeleton (UE5 Mannequin names, Tools/dai/anime/skeleton.py), run on top of
 * the idle take so the breathing and the head still live:
 *   1. the pelvis goes onto the seat (or above the pegs when standing) and the back leans forward; the lean
 *      grows until both wrists are within a comfortable reach of the grips, then the shoulder blades protract
 *      for whatever is left, so the hands always close on the bars;
 *   2. the neck and head counter the lean (eyes on the track) and part of the bike's roll;
 *   3. arms and legs are two-bone IK chains: elbows out and back, knees forward and out round the tank, the
 *      ball of each foot on its peg (or the left foot down on the ground at a stop).
 * Bone rotations are rebuilt from the reference (T) pose: each bone's rest direction and hinge axis are carried
 * onto the solved direction and hinge, so the knees and elbows bend about their real axes and the palms stay
 * down on the grips. Everything is in the mesh's component space: +X the rider's left, +Y forward, +Z up.
 */
namespace DARiderIK
{
	const FVector Left(1.0, 0.0, 0.0);
	const FVector Forward(0.0, 1.0, 0.0);
	const FVector Up(0.0, 0.0, 1.0);

	/** Share of the forward lean taken by the pelvis and spine_01..03 (the rest curves the back), and of the roll. */
	constexpr float LeanShare[4] = { 0.40f, 0.26f, 0.20f, 0.14f };
	constexpr float RollShare[4] = { 0.f, 0.30f, 0.35f, 0.35f };
	/** Neck / head counter-lean (share of the lean) and their split of the head roll. */
	constexpr float NeckCounter = 0.28f;
	constexpr float HeadCounter = 0.40f;
	constexpr float NeckRollShare = 0.4f;
	constexpr float MaxLean = 58.f;
	constexpr float LeanStep = 2.f;
	/** Comfortable reach (share of the straight arm) and how far the shoulder blades may protract (cm). */
	constexpr float ReachShare = 0.93f;
	constexpr float MaxProtract = 7.f;
	/** The wrist sits this far behind the grip centre (the palm wraps the grip) and above it (cm). */
	constexpr float WristBehindGrip = 6.5f;
	constexpr float WristAboveGrip = 2.f;
	/** Knee and elbow pole directions (left side; X is mirrored for the right). */
	const FVector KneePole(0.45, 1.0, 0.2);
	const FVector ElbowPole(0.35, -0.6, 0.05);
	/** Toes turned out (degrees). */
	constexpr float ToeOut = 9.f;

	struct FLimb
	{
		int32 Bone[3] = { INDEX_NONE, INDEX_NONE, INDEX_NONE };   // compact pose indices: upper, lower, end
		FQuat RestRot[3];
		FVector RestDir[2];
		FVector RestHinge = FVector::ZeroVector;
		float Length[2] = { 0.f, 0.f };
	};

	struct FRig
	{
		bool bValid = false;
		int32 Pelvis = INDEX_NONE;
		int32 Spine[3] = { INDEX_NONE, INDEX_NONE, INDEX_NONE };
		int32 Neck = INDEX_NONE;
		int32 Head = INDEX_NONE;
		int32 Clavicle[2] = { INDEX_NONE, INDEX_NONE };
		FLimb Arm[2];
		FLimb Leg[2];
		/** Rest offset from the floor under the ball of the foot to the ankle joint. */
		FVector AnkleFromBall[2];
	};

	inline FQuat Bend(float LeanDeg, float LeftRollDeg)
	{
		// Forward lean tips +Z towards +Y (a negative turn about +X); a left roll tips +Z towards +X (+Y axis).
		return FQuat(Forward, FMath::DegreesToRadians(LeftRollDeg)) * FQuat(Left, -FMath::DegreesToRadians(LeanDeg));
	}

	/** Rotation that carries direction A (hinge HA, perpendicular to A) onto direction B with hinge HB. */
	inline FQuat AlignFrame(const FVector& A, const FVector& HA, const FVector& B, const FVector& HB)
	{
		const FQuat Swing = FQuat::FindBetweenNormals(A, B);
		const FVector H1 = Swing.RotateVector(HA);
		const FVector P1 = (H1 - B * FVector::DotProduct(H1, B)).GetSafeNormal();
		const FVector P2 = (HB - B * FVector::DotProduct(HB, B)).GetSafeNormal();
		if (P1.IsNearlyZero() || P2.IsNearlyZero())
		{
			return Swing;
		}
		const double Twist = FMath::Atan2(FVector::DotProduct(FVector::CrossProduct(P1, P2), B), FVector::DotProduct(P1, P2));
		return (FQuat(B, Twist) * Swing).GetNormalized();
	}

	/** Two-bone IK: the mid and end joints of a limb rooted at Root reaching for Target, bending towards Pole.
	 *  Out of reach the limb points straight at the target; OutHinge is the axis the middle joint bends about. */
	inline void SolveTwoBone(const FVector& Root, const FVector& Target, const FVector& Pole, float L1, float L2,
		FVector& OutMid, FVector& OutEnd, FVector& OutHinge)
	{
		const FVector ToTarget = Target - Root;
		double D = ToTarget.Size();
		const FVector Dir = D > 1e-3 ? ToTarget / D : -Up;
		D = FMath::Clamp(D, static_cast<double>(FMath::Abs(L1 - L2)) + 0.1, (static_cast<double>(L1) + L2) * 0.9995);
		FVector BendDir = (Pole - Dir * FVector::DotProduct(Pole, Dir)).GetSafeNormal();
		if (BendDir.IsNearlyZero())
		{
			BendDir = (Forward - Dir * FVector::DotProduct(Forward, Dir)).GetSafeNormal();
		}
		const double CosA = FMath::Clamp((static_cast<double>(L1) * L1 + D * D - static_cast<double>(L2) * L2) / (2.0 * L1 * D), -1.0, 1.0);
		const double SinA = FMath::Sqrt(FMath::Max(0.0, 1.0 - CosA * CosA));
		OutMid = Root + Dir * (L1 * CosA) + BendDir * (L1 * SinA);
		OutEnd = Root + Dir * D;
		// cross(upper, lower) of the bent limb points along cross(BendDir, Dir)
		OutHinge = FVector::CrossProduct(BendDir, Dir).GetSafeNormal();
	}

	template <class FResolve>
	void Build(FRig& Rig, const FReferenceSkeleton& Ref, FResolve&& Resolve)
	{
		Rig = FRig();
		const int32 Num = Ref.GetNum();
		TArray<FTransform> RestCS;
		RestCS.SetNum(Num);
		const TArray<FTransform>& RefLocal = Ref.GetRefBonePose();
		for (int32 i = 0; i < Num; ++i)
		{
			const int32 P = Ref.GetParentIndex(i);
			RestCS[i] = P == INDEX_NONE ? RefLocal[i] : RefLocal[i] * RestCS[P];
		}
		bool bOk = true;
		// A bone of the expected chain: present, child of Parent (a reference index), and kept by this LOD.
		auto Find = [&](const TCHAR* Name, int32 Parent, int32& OutRef) -> int32
		{
			OutRef = Ref.FindBoneIndex(Name);
			if (OutRef == INDEX_NONE || (Parent != INDEX_NONE && Ref.GetParentIndex(OutRef) != Parent))
			{
				bOk = false;
				return INDEX_NONE;
			}
			const int32 Compact = Resolve(OutRef).GetInt();
			bOk &= Compact != INDEX_NONE;
			return Compact;
		};
		int32 PelvisRef = INDEX_NONE, Spine1Ref = INDEX_NONE, Spine2Ref = INDEX_NONE, Spine3Ref = INDEX_NONE, NeckRef = INDEX_NONE, HeadRef = INDEX_NONE;
		Rig.Pelvis = Find(TEXT("pelvis"), INDEX_NONE, PelvisRef);
		if (!bOk)
		{
			return;
		}
		Rig.Spine[0] = Find(TEXT("spine_01"), PelvisRef, Spine1Ref);
		Rig.Spine[1] = Find(TEXT("spine_02"), Spine1Ref, Spine2Ref);
		Rig.Spine[2] = Find(TEXT("spine_03"), Spine2Ref, Spine3Ref);
		Rig.Neck = Find(TEXT("neck_01"), Spine3Ref, NeckRef);
		Rig.Head = Find(TEXT("head"), NeckRef, HeadRef);
		if (!bOk)
		{
			return;
		}
		const TCHAR* ArmNames[2][4] = { { TEXT("clavicle_l"), TEXT("upperarm_l"), TEXT("lowerarm_l"), TEXT("hand_l") },
		                                { TEXT("clavicle_r"), TEXT("upperarm_r"), TEXT("lowerarm_r"), TEXT("hand_r") } };
		const TCHAR* LegNames[2][4] = { { TEXT("thigh_l"), TEXT("calf_l"), TEXT("foot_l"), TEXT("ball_l") },
		                                { TEXT("thigh_r"), TEXT("calf_r"), TEXT("foot_r"), TEXT("ball_r") } };
		auto SetupLimb = [&](FLimb& Limb, const int32 (&RefIdx)[3], const FVector& FlexDir)
		{
			for (int32 k = 0; k < 3; ++k)
			{
				Limb.RestRot[k] = RestCS[RefIdx[k]].GetRotation().GetNormalized();
			}
			const FVector P0 = RestCS[RefIdx[0]].GetLocation();
			const FVector P1 = RestCS[RefIdx[1]].GetLocation();
			const FVector P2 = RestCS[RefIdx[2]].GetLocation();
			Limb.Length[0] = static_cast<float>((P1 - P0).Size());
			Limb.Length[1] = static_cast<float>((P2 - P1).Size());
			Limb.RestDir[0] = (P1 - P0).GetSafeNormal();
			Limb.RestDir[1] = (P2 - P1).GetSafeNormal();
			// The limb flexes towards FlexDir from the T-pose (elbows bring the forearm forward, knees the calf back).
			Limb.RestHinge = FVector::CrossProduct(Limb.RestDir[0], FlexDir).GetSafeNormal();
			bOk &= Limb.Length[0] > 1.f && Limb.Length[1] > 1.f && !Limb.RestHinge.IsNearlyZero();
		};
		for (int32 Side = 0; Side < 2 && bOk; ++Side)
		{
			int32 ClavRef = INDEX_NONE;
			int32 ArmRef[3] = { INDEX_NONE, INDEX_NONE, INDEX_NONE };
			Rig.Clavicle[Side] = Find(ArmNames[Side][0], Spine3Ref, ClavRef);
			Rig.Arm[Side].Bone[0] = Find(ArmNames[Side][1], ClavRef, ArmRef[0]);
			Rig.Arm[Side].Bone[1] = Find(ArmNames[Side][2], ArmRef[0], ArmRef[1]);
			Rig.Arm[Side].Bone[2] = Find(ArmNames[Side][3], ArmRef[1], ArmRef[2]);
			int32 LegRef[3] = { INDEX_NONE, INDEX_NONE, INDEX_NONE };
			Rig.Leg[Side].Bone[0] = Find(LegNames[Side][0], PelvisRef, LegRef[0]);
			Rig.Leg[Side].Bone[1] = Find(LegNames[Side][1], LegRef[0], LegRef[1]);
			Rig.Leg[Side].Bone[2] = Find(LegNames[Side][2], LegRef[1], LegRef[2]);
			if (!bOk)
			{
				break;
			}
			SetupLimb(Rig.Arm[Side], ArmRef, Forward);
			SetupLimb(Rig.Leg[Side], LegRef, -Forward);
			const FVector Ankle = RestCS[LegRef[2]].GetLocation();
			const int32 BallRef = Ref.FindBoneIndex(LegNames[Side][3]);
			const FVector Ball = BallRef != INDEX_NONE ? RestCS[BallRef].GetLocation() : Ankle + Forward * 10.5;
			// the rest pose stands on the floor at Z = 0
			Rig.AnkleFromBall[Side] = Ankle - FVector(Ball.X, Ball.Y, 0.0);
		}
		Rig.bValid = bOk;
	}

	struct FTorso
	{
		FTransform Bone[4];        // pelvis, spine_01..03
		FTransform Clavicle[2];
		FVector Shoulder[2];       // upperarm joints
	};

	inline void PoseTorso(const FRig& Rig, const FCompactPose& Local, const FTransform& Pelvis0, const FVector& PelvisAt,
		float Lean, float Roll, FTorso& Out)
	{
		Out.Bone[0] = Pelvis0;
		Out.Bone[0].SetLocation(PelvisAt);
		Out.Bone[0].SetRotation((Bend(Lean * LeanShare[0], Roll * RollShare[0]) * Pelvis0.GetRotation()).GetNormalized());
		for (int32 i = 0; i < 3; ++i)
		{
			FTransform C = Local[FCompactPoseBoneIndex(Rig.Spine[i])] * Out.Bone[i];
			C.SetRotation((Bend(Lean * LeanShare[i + 1], Roll * RollShare[i + 1]) * C.GetRotation()).GetNormalized());
			Out.Bone[i + 1] = C;
		}
		for (int32 Side = 0; Side < 2; ++Side)
		{
			Out.Clavicle[Side] = Local[FCompactPoseBoneIndex(Rig.Clavicle[Side])] * Out.Bone[3];
			Out.Shoulder[Side] = (Local[FCompactPoseBoneIndex(Rig.Arm[Side].Bone[0])] * Out.Clavicle[Side]).GetLocation();
		}
	}

	inline FVector WristTarget(const FVector& Grip, const FVector& Shoulder)
	{
		return Grip + (Shoulder - Grip).GetSafeNormal() * WristBehindGrip + Up * WristAboveGrip;
	}

	inline FTransform Slerped(const FTransform& Follow, const FQuat& Solved, float Alpha)
	{
		FTransform Out = Follow;
		Out.SetRotation(FQuat::Slerp(Follow.GetRotation(), Solved, Alpha).GetNormalized());
		return Out;
	}

	/** Poses a solved limb by forward kinematics from its parent, each bone's rotation blended from the take
	 *  towards the solution by Alpha, so the bones never stretch during the blend. */
	inline void WriteLimb(FCSPose<FCompactPose>& CS, const FCompactPose& Local, const FLimb& Limb, const FTransform& ParentCS,
		const FQuat (&Solved)[3], float Alpha)
	{
		FTransform Parent = ParentCS;
		for (int32 k = 0; k < 3; ++k)
		{
			const FCompactPoseBoneIndex B(Limb.Bone[k]);
			const FTransform T = Slerped(Local[B] * Parent, Solved[k], Alpha);
			CS.SetComponentSpaceTransform(B, T);
			Parent = T;
		}
	}

	inline void Apply(const FRig& Rig, FCSPose<FCompactPose>& CS, const FDARiderIKTargets& T, float InAlpha)
	{
		if (!Rig.bValid || InAlpha <= 0.001f)
		{
			return;
		}
		const float Alpha = FMath::Clamp(InAlpha, 0.f, 1.f);
		const FCompactPose& Local = CS.GetPose();
		const FTransform Pelvis0 = CS.GetComponentSpaceTransform(FCompactPoseBoneIndex(Rig.Pelvis));

		// ---- torso: lean until both wrists are within a comfortable reach (solved for the full pose; a
		// partial Alpha, while getting on, then scales the pelvis move, the lean and the roll)
		float Lean = FMath::Clamp(T.Lean, 0.f, MaxLean);
		FTorso Torso;
		for (;;)
		{
			PoseTorso(Rig, Local, Pelvis0, T.Pelvis, Lean, T.Roll, Torso);
			float Need = 0.f;
			for (int32 Side = 0; Side < 2; ++Side)
			{
				const FLimb& Arm = Rig.Arm[Side];
				const double Dist = (WristTarget(T.Grip[Side], Torso.Shoulder[Side]) - Torso.Shoulder[Side]).Size();
				Need = FMath::Max(Need, static_cast<float>(Dist / (Arm.Length[0] + Arm.Length[1])));
			}
			if (Need <= ReachShare || Lean >= MaxLean)
			{
				break;
			}
			Lean = FMath::Min(Lean + LeanStep, MaxLean);
		}
		if (Alpha < 1.f)
		{
			const FVector PelvisAt = FMath::Lerp(Pelvis0.GetLocation(), T.Pelvis, static_cast<double>(Alpha));
			PoseTorso(Rig, Local, Pelvis0, PelvisAt, Lean * Alpha, T.Roll * Alpha, Torso);
		}
		CS.SetComponentSpaceTransform(FCompactPoseBoneIndex(Rig.Pelvis), Torso.Bone[0]);
		for (int32 i = 0; i < 3; ++i)
		{
			CS.SetComponentSpaceTransform(FCompactPoseBoneIndex(Rig.Spine[i]), Torso.Bone[i + 1]);
		}

		// ---- neck and head: eyes on the track
		{
			const float A = Alpha;
			FTransform Neck = Local[FCompactPoseBoneIndex(Rig.Neck)] * Torso.Bone[3];
			Neck.SetRotation((Bend(-Lean * NeckCounter * A, T.HeadRoll * NeckRollShare * A) * Neck.GetRotation()).GetNormalized());
			FTransform Head = Local[FCompactPoseBoneIndex(Rig.Head)] * Neck;
			Head.SetRotation((Bend(-Lean * HeadCounter * A, T.HeadRoll * (1.f - NeckRollShare) * A) * Head.GetRotation()).GetNormalized());
			CS.SetComponentSpaceTransform(FCompactPoseBoneIndex(Rig.Neck), Neck);
			CS.SetComponentSpaceTransform(FCompactPoseBoneIndex(Rig.Head), Head);
		}

		// ---- arms: shoulder blades protract for what the lean could not reach, then two-bone IK to the grips
		for (int32 Side = 0; Side < 2; ++Side)
		{
			const FLimb& Arm = Rig.Arm[Side];
			const double Mirror = Side == 0 ? 1.0 : -1.0;
			FTransform Clav = Torso.Clavicle[Side];
			FVector Shoulder = Torso.Shoulder[Side];
			const FVector Grip = T.Grip[Side];
			FVector Wrist = WristTarget(Grip, Shoulder);
			const double Reach = ReachShare * (Arm.Length[0] + Arm.Length[1]);
			const double Short = (Wrist - Shoulder).Size() - Reach;
			if (Short > 0.0 && Alpha > 0.5f)
			{
				const FVector C = Clav.GetLocation();
				const double ClavLen = (Shoulder - C).Size();
				const FVector Wanted = Shoulder + (Wrist - Shoulder).GetSafeNormal() * FMath::Min(Short, static_cast<double>(MaxProtract));
				const FVector NewShoulder = C + (Wanted - C).GetSafeNormal() * ClavLen;
				const FQuat Protract = FQuat::FindBetweenNormals((Shoulder - C).GetSafeNormal(), (NewShoulder - C).GetSafeNormal());
				Clav.SetRotation((Protract * Clav.GetRotation()).GetNormalized());
				Shoulder = NewShoulder;
				Wrist = WristTarget(Grip, Shoulder);
			}
			CS.SetComponentSpaceTransform(FCompactPoseBoneIndex(Rig.Clavicle[Side]), Clav);

			const FVector Pole(ElbowPole.X * Mirror, ElbowPole.Y, ElbowPole.Z);
			FVector Elbow, Hand, Hinge;
			SolveTwoBone(Shoulder, Wrist, Pole.GetSafeNormal(), Arm.Length[0], Arm.Length[1], Elbow, Hand, Hinge);
			const FQuat Upper = AlignFrame(Arm.RestDir[0], Arm.RestHinge, (Elbow - Shoulder).GetSafeNormal(), Hinge) * Arm.RestRot[0];
			const FQuat ForearmDelta = AlignFrame(Arm.RestDir[1], Arm.RestHinge, (Hand - Elbow).GetSafeNormal(), Hinge);
			const FQuat Solved[3] = { Upper.GetNormalized(), (ForearmDelta * Arm.RestRot[1]).GetNormalized(),
			                          (ForearmDelta * Arm.RestRot[2]).GetNormalized() };   // straight wrist, palm on the grip
			WriteLimb(CS, Local, Arm, Clav, Solved, Alpha);
		}

		// ---- legs: ball of the foot on the peg (or the ground), knees forward and out round the tank
		for (int32 Side = 0; Side < 2; ++Side)
		{
			const FLimb& Leg = Rig.Leg[Side];
			const double Mirror = Side == 0 ? 1.0 : -1.0;
			const FVector Hip = (Local[FCompactPoseBoneIndex(Leg.Bone[0])] * Torso.Bone[0]).GetLocation();
			const FQuat FootDelta = (FQuat(Up, -Mirror * FMath::DegreesToRadians(ToeOut)) *
				FQuat(Left, -FMath::DegreesToRadians(FMath::Clamp(T.ToeDown[Side], -20.f, 60.f)))).GetNormalized();
			const FVector Ankle = T.Ball[Side] + FootDelta.RotateVector(Rig.AnkleFromBall[Side]);
			const FVector Pole(KneePole.X * Mirror, KneePole.Y, KneePole.Z);
			FVector Knee, Foot, Hinge;
			SolveTwoBone(Hip, Ankle, Pole.GetSafeNormal(), Leg.Length[0], Leg.Length[1], Knee, Foot, Hinge);
			const FQuat Solved[3] = {
				(AlignFrame(Leg.RestDir[0], Leg.RestHinge, (Knee - Hip).GetSafeNormal(), Hinge) * Leg.RestRot[0]).GetNormalized(),
				(AlignFrame(Leg.RestDir[1], Leg.RestHinge, (Foot - Knee).GetSafeNormal(), Hinge) * Leg.RestRot[1]).GetNormalized(),
				(FootDelta * Leg.RestRot[2]).GetNormalized() };
			WriteLimb(CS, Local, Leg, Torso.Bone[0], Solved, Alpha);
		}
	}
}
// ---- rider IK end

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
	float RiderAlpha = 0.f;
	FDARiderIKTargets Rider;

	// worker-thread state
	DARiderIK::FRig RiderRig;
	TArray<FDASpringChain> Chains;
	bool bChainsBuilt = false;
	FCompactPoseBoneIndex HeadIndex = FCompactPoseBoneIndex(INDEX_NONE);
	FCompactPoseBoneIndex NeckIndex = FCompactPoseBoneIndex(INDEX_NONE);
	FCompactPoseBoneIndex SpineIndex = FCompactPoseBoneIndex(INDEX_NONE);
	FCompactPoseBoneIndex LegIndex[2][3] = {
		{ FCompactPoseBoneIndex(INDEX_NONE), FCompactPoseBoneIndex(INDEX_NONE), FCompactPoseBoneIndex(INDEX_NONE) },
		{ FCompactPoseBoneIndex(INDEX_NONE), FCompactPoseBoneIndex(INDEX_NONE), FCompactPoseBoneIndex(INDEX_NONE) } };
	FVector LastHeadWorld = FVector::ZeroVector;
	FTransform LastSimComponentToWorld = FTransform::Identity;
	bool bHaveLastC2W = false;
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
		// neighbouring chains of one head of hair (HairJoint_<Key>_Short03_0 -> group "HairJoint_<Key>_Short"):
		// the two whose tips are nearest in the reference pose, for the cohesion pull
		TArray<FTransform> RefCS;
		RefCS.SetNum(Num);
		const TArray<FTransform>& RefLocal = Ref.GetRefBonePose();
		for (int32 i = 0; i < Num; ++i)
		{
			const int32 P = Ref.GetParentIndex(i);
			RefCS[i] = P == INDEX_NONE ? RefLocal[i] : RefLocal[i] * RefCS[P];
		}
		TArray<FString> Groups;
		for (const FDASpringChain& Ch : Chains)
		{
			FString G = Ref.GetBoneName(Ch.SkeletonBones[0]).ToString();
			int32 Us = INDEX_NONE;
			if (G.FindLastChar(TEXT('_'), Us))
			{
				G.LeftInline(Us);                                    // drop "_<joint>"
			}
			while (G.Len() > 0 && FChar::IsDigit(G[G.Len() - 1]))
			{
				G.LeftChopInline(1);                                 // drop the chain number
			}
			Groups.Add(G);
		}
		for (int32 c = 0; c < Chains.Num(); ++c)
		{
			FDASpringChain& Ch = Chains[c];
			Ch.Neighbours.Reset();
			if (Ch.Params.Cohesion <= 0.f)
			{
				continue;
			}
			const FVector Tip = RefCS[Ch.SkeletonBones.Last()].GetLocation();
			TArray<TPair<double, int32>> Near;
			for (int32 o = 0; o < Chains.Num(); ++o)
			{
				if (o == c || Groups[o] != Groups[c])
				{
					continue;
				}
				const double D = FVector::Dist(Tip, RefCS[Chains[o].SkeletonBones.Last()].GetLocation());
				if (D < 25.0)
				{
					Near.Add(TPair<double, int32>(D, o));
				}
			}
			Near.Sort([](const TPair<double, int32>& A, const TPair<double, int32>& B) { return A.Key < B.Key; });
			for (int32 k = 0; k < FMath::Min(2, Near.Num()); ++k)
			{
				Ch.Neighbours.Add(Near[k].Value);
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
		SpineIndex = Resolve(Ref.FindBoneIndex(TEXT("spine_02")));
		const TCHAR* LegNames[2][3] = { { TEXT("thigh_l"), TEXT("calf_l"), TEXT("foot_l") },
		                                { TEXT("thigh_r"), TEXT("calf_r"), TEXT("foot_r") } };
		for (int32 Side = 0; Side < 2; ++Side)
		{
			for (int32 J = 0; J < 3; ++J)
			{
				LegIndex[Side][J] = Resolve(Ref.FindBoneIndex(LegNames[Side][J]));
			}
		}
		DARiderIK::Build(RiderRig, Ref, Resolve);
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

	/** VRM spring bones: each joint's tail is a verlet particle pulled back to its animated direction.
	 *  The chains are solved level by level (every chain's first joint, then every chain's second, ...) so a
	 *  joint can be pulled towards the motion of its neighbouring chains at the same depth (Cohesion): a head
	 *  of hair swings as one soft mass instead of separate strands drifting apart. MaxAngle keeps a joint
	 *  within a cone round its animated direction (styled anime hair holds its shape). */
	void ApplySprings(FCSPose<FCompactPose>& CS)
	{
		if (!bSprings || Chains.Num() == 0)
		{
			return;
		}
		const float Dt = FMath::Clamp(SimDt, 0.f, 1.f / 20.f);
		const FCompactPose& Local = CS.GetPose();
		const float Scale = static_cast<float>(SimComponentToWorld.GetScale3D().Z);
		// head sphere (hair must not swing into the face / skull)
		FVector HeadCenterW = FVector::ZeroVector;
		float HeadRadius = 0.f;
		bool bTeleported = false;
		if (HeadIndex.GetInt() != INDEX_NONE)
		{
			const FTransform HeadCS = CS.GetComponentSpaceTransform(HeadIndex);
			HeadCenterW = SimComponentToWorld.TransformPosition(HeadCS.GetLocation() + FVector(0.0, -1.0, 9.0));
			HeadRadius = 9.5f * Scale;
			bTeleported = !LastHeadWorld.IsZero() && FVector::DistSquared(LastHeadWorld, HeadCenterW) > FMath::Square(120.f);
			LastHeadWorld = HeadCenterW;
		}
		// upper body capsule (long hair lies on the back and shoulders): spine_02 -> neck_01
		FVector BodyA = FVector::ZeroVector, BodyB = FVector::ZeroVector;
		const bool bBody = SpineIndex.GetInt() != INDEX_NONE && NeckIndex.GetInt() != INDEX_NONE;
		if (bBody)
		{
			BodyA = SimComponentToWorld.TransformPosition(CS.GetComponentSpaceTransform(SpineIndex).GetLocation());
			BodyB = SimComponentToWorld.TransformPosition(CS.GetComponentSpaceTransform(NeckIndex).GetLocation());
		}
		const float BodyRadius = 11.f * Scale;
		// leg capsules (world space): hip -> knee and knee -> ankle per side
		FVector Leg[2][3];
		bool bLegs = true;
		for (int32 Side = 0; Side < 2 && bLegs; ++Side)
		{
			for (int32 J = 0; J < 3; ++J)
			{
				if (LegIndex[Side][J].GetInt() == INDEX_NONE)
				{
					bLegs = false;
					break;
				}
				Leg[Side][J] = SimComponentToWorld.TransformPosition(CS.GetComponentSpaceTransform(LegIndex[Side][J]).GetLocation());
			}
		}
		auto PushOutOfLegs = [&](FVector& P)
		{
			if (!bLegs)
			{
				return;
			}
			for (int32 Side = 0; Side < 2; ++Side)
			{
				for (int32 Seg = 0; Seg < 2; ++Seg)
				{
					const FVector C = ClosestOnSegment(P, Leg[Side][Seg], Leg[Side][Seg + 1]);
					const float R = (Seg == 0 ? ThighRadius : CalfRadius) * Scale;
					const FVector Off = P - C;
					const double D = Off.Size();
					if (D < R && D > KINDA_SMALL_NUMBER)
					{
						P = C + Off / D * R;
					}
				}
			}
		};
		// the tails ride along with (1 - Inertia) of the character's own move since the last step, so walking and
		// running give a lively sway instead of a wind tunnel (all of the lag at 4 m/s would blow the hair back)
		const bool bCarry = Dt > 0.f && bHaveLastC2W && !bTeleported;
		const FTransform LastC2W = LastSimComponentToWorld;
		if (Dt > 0.f)
		{
			LastSimComponentToWorld = SimComponentToWorld;
			bHaveLastC2W = true;
		}
		const FVector GravityDir(0.0, 0.0, -1.0);
		int32 MaxJoints = 0;
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
			if (bCarry && Chain.bInitialised && Chain.Params.Inertia < 1.f)
			{
				const float K = 1.f - Chain.Params.Inertia;
				for (int32 j = 0; j < Joints; ++j)
				{
					const FVector C = SimComponentToWorld.TransformPosition(LastC2W.InverseTransformPosition(Chain.CurTail[j]));
					const FVector P = SimComponentToWorld.TransformPosition(LastC2W.InverseTransformPosition(Chain.PrevTail[j]));
					Chain.CurTail[j] = FMath::Lerp(Chain.CurTail[j], C, K);
					Chain.PrevTail[j] = FMath::Lerp(Chain.PrevTail[j], P, K);
				}
			}
			MaxJoints = FMath::Max(MaxJoints, Joints);
		}
		struct FLevel
		{
			FVector HeadW, AnimTailW, Next;
			FTransform BoneCS;
			FVector AnimTailCS;
			float Len = 0.f;
			bool bActive = false;
		};
		TArray<FLevel, TInlineAllocator<64>> Lv;
		TArray<FVector, TInlineAllocator<64>> Cohered;
		Lv.SetNum(Chains.Num());
		Cohered.SetNum(Chains.Num());
		float MaxDeflection = 0.f;
		for (int32 j = 0; j < MaxJoints; ++j)
		{
			// 1. integrate every chain's joint j
			for (int32 c = 0; c < Chains.Num(); ++c)
			{
				FDASpringChain& Chain = Chains[c];
				FLevel& L = Lv[c];
				L.bActive = false;
				if (!Chain.bValid || j >= Chain.Bones.Num() - 1)
				{
					continue;
				}
				const FCompactPoseBoneIndex B = Chain.Bones[j];
				const FCompactPoseBoneIndex Child = Chain.Bones[j + 1];
				L.BoneCS = CS.GetComponentSpaceTransform(B);
				L.AnimTailCS = (Local[Child] * L.BoneCS).GetLocation();
				L.HeadW = SimComponentToWorld.TransformPosition(L.BoneCS.GetLocation());
				L.AnimTailW = SimComponentToWorld.TransformPosition(L.AnimTailCS);
				const FVector RestW = L.AnimTailW - L.HeadW;
				L.Len = static_cast<float>(RestW.Size());
				if (L.Len < KINDA_SMALL_NUMBER)
				{
					continue;
				}
				if (!Chain.bInitialised || bTeleported)
				{
					Chain.CurTail[j] = Chain.PrevTail[j] = L.AnimTailW;
				}
				FVector Next = Chain.CurTail[j];
				if (Dt > 0.f)
				{
					const FVector Inertia = (Chain.CurTail[j] - Chain.PrevTail[j]) * (1.f - Chain.Params.Drag);
					// stiffness scaled by the bone length so short and long bones behave alike (VRM is in metres)
					const FVector Stiff = (RestW / L.Len) * (Chain.Params.Stiffness * Dt * L.Len * 20.f);
					const FVector Grav = GravityDir * (Chain.Params.Gravity * Dt * 100.f);
					Next = Chain.CurTail[j] + Inertia + Stiff + Grav;
				}
				L.Next = L.HeadW + (Next - L.HeadW).GetSafeNormal() * L.Len;
				L.bActive = true;
			}
			// 2. cohesion: each joint's deviation from its animated tail blends towards its neighbours' mean
			for (int32 c = 0; c < Chains.Num(); ++c)
			{
				const FLevel& L = Lv[c];
				Cohered[c] = L.Next;
				const FDASpringChain& Chain = Chains[c];
				if (!L.bActive || Chain.Params.Cohesion <= 0.f || Chain.Neighbours.Num() == 0)
				{
					continue;
				}
				FVector Sum = FVector::ZeroVector;
				int32 N = 0;
				for (int32 Nb : Chain.Neighbours)
				{
					if (Lv.IsValidIndex(Nb) && Lv[Nb].bActive)
					{
						Sum += Lv[Nb].Next - Lv[Nb].AnimTailW;
						++N;
					}
				}
				if (N > 0)
				{
					const FVector Own = L.Next - L.AnimTailW;
					const FVector Dev = FMath::Lerp(Own, Sum / N, Chain.Params.Cohesion);
					Cohered[c] = L.HeadW + (L.AnimTailW + Dev - L.HeadW).GetSafeNormal() * L.Len;
				}
			}
			// 3. constraints, state, bone rotation
			for (int32 c = 0; c < Chains.Num(); ++c)
			{
				FDASpringChain& Chain = Chains[c];
				const FLevel& L = Lv[c];
				if (!L.bActive)
				{
					continue;
				}
				FVector Next = Cohered[c];
				const FVector RestDir = (L.AnimTailW - L.HeadW) / L.Len;
				if (Chain.Params.MaxAngle > 0.f)
				{
					const FVector Dir = (Next - L.HeadW).GetSafeNormal();
					const float Ang = FMath::RadiansToDegrees(FMath::Acos(FMath::Clamp(static_cast<float>(FVector::DotProduct(Dir, RestDir)), -1.f, 1.f)));
					if (Ang > Chain.Params.MaxAngle)
					{
						const FQuat Q = FQuat::FindBetweenNormals(RestDir, Dir);
						const FQuat Lim = FQuat::Slerp(FQuat::Identity, Q, Chain.Params.MaxAngle / Ang);
						Next = L.HeadW + Lim.RotateVector(RestDir) * L.Len;
					}
				}
				if (Chain.Params.bHeadCollide && HeadRadius > 0.f)
				{
					// never push a strand further out than its own animated rest (bangs lie close to the face)
					const float Radius = FMath::Min(HeadRadius, 0.95f * static_cast<float>(FVector::Dist(L.AnimTailW, HeadCenterW)));
					const FVector Off = Next - HeadCenterW;
					const float D = static_cast<float>(Off.Size());
					if (D < Radius && D > KINDA_SMALL_NUMBER)
					{
						Next = HeadCenterW + Off / D * Radius;
						Next = L.HeadW + (Next - L.HeadW).GetSafeNormal() * L.Len;
					}
				}
				if (Chain.Params.bBodyCollide && bBody)
				{
					// long hair stays on the back / shoulders: no closer to the spine than its animated rest
					const FVector AxisRest = ClosestOnSegment(L.AnimTailW, BodyA, BodyB);
					const float Radius = FMath::Min(BodyRadius, 0.95f * static_cast<float>(FVector::Dist(L.AnimTailW, AxisRest)));
					const FVector C = ClosestOnSegment(Next, BodyA, BodyB);
					const FVector Off = Next - C;
					const float D = static_cast<float>(Off.Size());
					if (D < Radius && D > KINDA_SMALL_NUMBER)
					{
						Next = C + Off / D * Radius;
						Next = L.HeadW + (Next - L.HeadW).GetSafeNormal() * L.Len;
					}
				}
				if (Chain.Params.bLegCollide)
				{
					// a swinging skirt / coat panel never ends up inside a leg
					PushOutOfLegs(Next);
					Next = L.HeadW + (Next - L.HeadW).GetSafeNormal() * L.Len;
				}
				if (Dt > 0.f)
				{
					Chain.PrevTail[j] = Chain.CurTail[j];
					Chain.CurTail[j] = Next;
				}
				const FVector SimCS = SimComponentToWorld.InverseTransformVectorNoScale(Next - L.HeadW).GetSafeNormal();
				const FVector AnimCS = (L.AnimTailCS - L.BoneCS.GetLocation()).GetSafeNormal();
				if (SimCS.IsNearlyZero() || AnimCS.IsNearlyZero())
				{
					continue;
				}
				const FQuat Delta = FQuat::FindBetweenNormals(AnimCS, SimCS);
				MaxDeflection = FMath::Max(MaxDeflection, FMath::RadiansToDegrees(static_cast<float>(Delta.GetAngle())));
				FTransform NewCS = L.BoneCS;
				NewCS.SetRotation((Delta * L.BoneCS.GetRotation()).GetNormalized());
				CS.SetComponentSpaceTransform(Chain.Bones[j], NewCS);
			}
		}
		int32 ValidChains = 0;
		for (FDASpringChain& Chain : Chains)
		{
			if (Chain.bValid)
			{
				Chain.bInitialised = true;
				++ValidChains;
			}
		}
		StatChains = ValidChains;
		StatMaxDeflection = MaxDeflection;
		SimDt = 0.f;
	}

	void ApplyProcedural(FPoseContext& Output)
	{
		const bool bRider = RiderRig.bValid && RiderAlpha > 0.001f;
		const bool bAny = (bSprings && Chains.Num() > 0) || LookAlpha > 0.001f || bRider;
		if (!bAny)
		{
			SimDt = 0.f;
			return;
		}
		FCSPose<FCompactPose> CS;
		CS.InitPose(Output.Pose);
		// The rider pose first: the head turn and the hair / cloth springs then work from the seated body.
		if (bRider)
		{
			DARiderIK::Apply(RiderRig, CS, Rider, RiderAlpha);
		}
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
	RiderAlpha = 0.f;
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
	bTalking = false;
	bLookAt = false;
	LookAlpha = 0.f;
	EmotionTargets.Reset();
	EmotionWeights.Reset();
	FaceRng.Initialize(static_cast<int32>(GetTypeHash(GetOuter() ? GetOuter()->GetFName() : NAME_None)));
	BlinkTimer = FaceRng.FRandRange(0.5f, 3.f);
	BlinkClock = -1.f;
	bHasFace = false;
	bFitChecked = false;
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

void UDAAvatarAnimInstance::UpdateCorrectives()
{
	const USkeletalMeshComponent* Comp = GetSkelMeshComponent();
	const USkeletalMesh* Mesh = Comp ? Comp->GetSkeletalMeshAsset() : nullptr;
	if (!Mesh)
	{
		return;
	}
	if (!bFitChecked)
	{
		bFitChecked = true;
		for (int32 Side = 0; Side < 2; ++Side)
		{
			FitMorphs[Side].Reset();
			for (int32 K = 0; K < NumFitKeys; ++K)
			{
				const FName Name(*FString::Printf(TEXT("Fit_%s_%s"), FitKeys[K].Name, Side == 0 ? TEXT("l") : TEXT("r")));
				if (Mesh->FindMorphTarget(Name))
				{
					FitMorphs[Side].Add(TPair<FName, int32>(Name, K));
				}
			}
		}
	}
	if (FitMorphs[0].Num() == 0 && FitMorphs[1].Num() == 0)
	{
		return;
	}
	const TArray<FTransform>& Pose = Comp->GetComponentSpaceTransforms();
	const FReferenceSkeleton& Ref = Mesh->GetRefSkeleton();
	const int32 Pelvis = Comp->GetBoneIndex(TEXT("pelvis"));
	if (Pelvis == INDEX_NONE || !Pose.IsValidIndex(Pelvis))
	{
		return;
	}
	const FQuat PelvisRest = FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, Pelvis).GetRotation();
	const FQuat PelvisPose = Pose[Pelvis].GetRotation();
	// rest-pose axes of the cast in mesh space: forward +Y, up +Z, the left side +X
	const FVector Fwd = PelvisRest.UnrotateVector(FVector(0.0, 1.0, 0.0));
	const FVector Up = PelvisRest.UnrotateVector(FVector(0.0, 0.0, 1.0));
	const TCHAR* Suffix[2] = { TEXT("l"), TEXT("r") };
	for (int32 Side = 0; Side < 2; ++Side)
	{
		if (FitMorphs[Side].Num() == 0)
		{
			continue;
		}
		const int32 Thigh = Comp->GetBoneIndex(FName(*FString::Printf(TEXT("thigh_%s"), Suffix[Side])));
		const int32 Calf = Comp->GetBoneIndex(FName(*FString::Printf(TEXT("calf_%s"), Suffix[Side])));
		const int32 Foot = Comp->GetBoneIndex(FName(*FString::Printf(TEXT("foot_%s"), Suffix[Side])));
		if (Thigh == INDEX_NONE || Calf == INDEX_NONE || Foot == INDEX_NONE ||
			!Pose.IsValidIndex(Thigh) || !Pose.IsValidIndex(Calf) || !Pose.IsValidIndex(Foot))
		{
			continue;
		}
		const FVector Out = PelvisRest.UnrotateVector(FVector(Side == 0 ? 1.0 : -1.0, 0.0, 0.0));
		const FVector Hip0 = FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, Thigh).GetLocation();
		const FVector Knee0 = FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, Calf).GetLocation();
		const FVector Ankle0 = FAnimationRuntime::GetComponentSpaceTransformRefPose(Ref, Foot).GetLocation();
		const FVector Hip1 = Pose[Thigh].GetLocation();
		const FVector Knee1 = Pose[Calf].GetLocation();
		const FVector Ankle1 = Pose[Foot].GetLocation();
		const FVector K0 = PelvisRest.UnrotateVector(Knee0 - Hip0);
		const FVector K1 = PelvisPose.UnrotateVector(Knee1 - Hip1);
		const float Pitch = PlaneAngle(K1, Fwd, Up) - PlaneAngle(K0, Fwd, Up);
		const float Spread = PlaneAngle(K1, Out, Up) - PlaneAngle(K0, Out, Up);
		const float Knee = BendAngle(Hip1, Knee1, Ankle1) - BendAngle(Hip0, Knee0, Ankle0);
		const float Amount[4] = { FMath::Max(0.f, Pitch), FMath::Max(0.f, -Pitch), FMath::Max(0.f, Spread), FMath::Max(0.f, Knee) };
		for (const TPair<FName, int32>& M : FitMorphs[Side])
		{
			SetMorphTarget(M.Key, FitTent(M.Value, Amount[FitKeys[M.Value].Chain]));
		}
	}
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
	if (IdleSequence && IdleSequence->GetPlayLength() > 0.f)
	{
		// Every character starts elsewhere in the idle loop: a group must not breathe,
		// shift its weight and glance aside in unison.
		IdleTime = FaceRng.FRandRange(0.f, IdleSequence->GetPlayLength());
	}
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

void UDAAvatarAnimInstance::SetRider(const FDARiderIKTargets& InTargets, float InAlpha)
{
	RiderTargets = InTargets;
	RiderAlpha = FMath::Clamp(InAlpha, 0.f, 1.f);
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

	// procedural layer: springs integrate once per game frame in world space; look-at target in mesh space
	if (const USkeletalMeshComponent* Comp = GetSkelMeshComponent())
	{
		Proxy.SimComponentToWorld = Comp->GetComponentTransform();
		LookAlpha = FMath::FInterpTo(LookAlpha, bLookAt ? 1.f : 0.f, Dt, 4.f);
		Proxy.LookAlpha = LookAlpha * (1.f - FMath::Clamp(ActionWeightA + ActionWeightB, 0.f, 1.f) * 0.7f) * (1.f - RiderAlpha);
		Proxy.LookTargetCS = Proxy.SimComponentToWorld.InverseTransformPosition(LookTargetWorld);
	}
	Proxy.Rider = RiderTargets;
	Proxy.RiderAlpha = RiderAlpha;
	Proxy.SimDt = Dt;
	Proxy.bSprings = bSecondaryMotion;
	UpdateCorrectives();
	SpringChainCount = Proxy.StatChains;
	SpringDeflection = Proxy.StatMaxDeflection;
	UpdateFace(Dt);
}
