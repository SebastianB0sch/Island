// Runs the motorcycle rider IK of DAAvatarAnimInstance.cpp (extracted verbatim by extract.py into rider_extract.inc)
// against ../springs/ue_mock.h on the cast skeleton (Tools/dai/anime/skeleton.py joint layout, cm, mesh space: +X the
// rider's left, +Y forward, +Z up). Every bone gets an arbitrary rest rotation, so the test also proves the solver
// does not depend on the exported bone axes. Checks, for a seated rider, a tucked one, one standing on the pegs, a
// left foot put down at a stop, a smaller rider and a half-blended mount:
//   * the pelvis sits on its target, the back leans forward and the head is pitched back up towards the track;
//   * each wrist ends at its grip (within the palm offset), each ankle where the ball of the foot is on its peg;
//   * bones keep their lengths, knees point forward and out round the tank, elbows out, palms face down;
//   * Alpha 0 leaves the take untouched and Alpha 0.5 stays finite and unstretched.
// Driven by Tools/tests/test_rider_ik.py.
#include "ue_mock.h"
#include <cstdio>
#include <random>
#include "rider_extract.inc"

namespace
{
struct Skel
{
  FReferenceSkeleton Ref;
  std::vector<FTransform> RestCS;
  int Add(const std::string& Name, int Parent, FVector Pos, const FQuat& Rot)
  {
    FTransform C(Rot, Pos);
    FTransform L;
    if (Parent < 0) L = C;
    else
    {
      const FTransform& P = RestCS[Parent];
      L.R = (P.R.Inverse() * C.R).GetNormalized();
      L.T = P.R.Inverse().RotateVector(C.T - P.T);
    }
    Ref.Names.push_back(Name); Ref.Parents.push_back(Parent); Ref.Ref.Add(L); RestCS.push_back(C);
    return (int)Ref.Names.size() - 1;
  }
  int Find(const char* N) const { return Ref.FindBoneIndex(N); }
};

std::mt19937 Rng(7);
FQuat RandomRot()
{
  std::uniform_real_distribution<double> U(-1.0, 1.0);
  FVector Axis(U(Rng), U(Rng), U(Rng));
  return FQuat(Axis.GetSafeNormal(), U(Rng) * 3.0);
}

Skel MakeCast()
{
  Skel S;
  const int Root = S.Add("root", -1, {0, 0, 0}, FQuat::Identity);
  const int Pelvis = S.Add("pelvis", Root, {0, 0, 93}, RandomRot());
  const int S1 = S.Add("spine_01", Pelvis, {0, 0, 101}, RandomRot());
  const int S2 = S.Add("spine_02", S1, {0, 0, 112}, RandomRot());
  const int S3 = S.Add("spine_03", S2, {0, 0, 123.5}, RandomRot());
  const int Neck = S.Add("neck_01", S3, {0, 0, 139.5}, RandomRot());
  S.Add("head", Neck, {0, 0, 147.5}, RandomRot());
  for (int Side = 0; Side < 2; ++Side)
  {
    const double X = Side == 0 ? 1.0 : -1.0;
    const std::string Sx = Side == 0 ? "_l" : "_r";
    const int Clav = S.Add("clavicle" + Sx, S3, {X * 3.0, 0, 140}, RandomRot());
    const int Up = S.Add("upperarm" + Sx, Clav, {X * 17.5, 0, 139}, RandomRot());
    const int Lo = S.Add("lowerarm" + Sx, Up, {X * 44.0, 0, 139}, RandomRot());
    S.Add("hand" + Sx, Lo, {X * 67.5, 0, 139}, RandomRot());
    const int Th = S.Add("thigh" + Sx, Pelvis, {X * 8.8, 0, 87.5}, RandomRot());
    const int Ca = S.Add("calf" + Sx, Th, {X * 8.8, 0.6, 47}, RandomRot());
    const int Fo = S.Add("foot" + Sx, Ca, {X * 8.8, 0, 8.5}, RandomRot());
    S.Add("ball" + Sx, Fo, {X * 8.8, 10.5, 3}, RandomRot());
  }
  return S;
}

FCSPose<FCompactPose> MakePose(const Skel& S)
{
  FCSPose<FCompactPose> CS;
  CS.Parent = S.Ref.Parents;
  for (auto& L : S.Ref.Ref) CS.Pose.L.push_back(L);
  // an "idle take": a little slouch and the arms hanging down
  auto Tilt = [&](const char* Name, const FQuat& Q) {
    const int B = S.Find(Name);
    CS.Pose.L[B].R = (CS.Pose.L[B].R * (S.RestCS[B].R.Inverse() * Q * S.RestCS[B].R)).GetNormalized();
  };
  Tilt("spine_02", FQuat(FVector(1, 0, 0), 0.06));
  Tilt("upperarm_l", FQuat(FVector(0, 1, 0), 1.3));
  Tilt("upperarm_r", FQuat(FVector(0, 1, 0), -1.3));
  return CS;
}

double Deg(double R) { return R * 57.2957795; }
FVector Pos(FCSPose<FCompactPose>& CS, const Skel& S, const char* N) { return CS.GetComponentSpaceTransform(FCompactPoseBoneIndex(S.Find(N))).T; }
FQuat Rot(FCSPose<FCompactPose>& CS, const Skel& S, const char* N) { return CS.GetComponentSpaceTransform(FCompactPoseBoneIndex(S.Find(N))).R; }
bool Finite(const FVector& V) { return std::isfinite(V.X) && std::isfinite(V.Y) && std::isfinite(V.Z); }

struct Case
{
  const char* Name;
  FDARiderIKTargets T;
  float Alpha = 1.f;
  double Scale = 1.0;   // rider size: the bike looks this much bigger to a smaller rider (mesh units)
};

// The bike's contact points in the mesh space of a 1.0 rider (DAMotorcycleComponent at ModelScale 0.95).
FDARiderIKTargets Seated()
{
  FDARiderIKTargets T;
  T.Pelvis = FVector(0, 3.8, 108.5);
  T.Grip[0] = FVector(32.3, 47.0, 118.3);
  T.Grip[1] = FVector(-32.3, 47.0, 118.3);
  T.Ball[0] = FVector(16.2, 19.0, 39.4);
  T.Ball[1] = FVector(-16.2, 19.0, 39.4);
  T.Lean = 16.f;
  return T;
}

FDARiderIKTargets ScaleTargets(FDARiderIKTargets T, double K)
{
  T.Pelvis = T.Pelvis * K; T.Grip[0] = T.Grip[0] * K; T.Grip[1] = T.Grip[1] * K; T.Ball[0] = T.Ball[0] * K; T.Ball[1] = T.Ball[1] * K;
  return T;
}
}

int main()
{
  const Skel S = MakeCast();
  DARiderIK::FRig Rig;
  DARiderIK::Build(Rig, S.Ref, [](int32 I) { return FCompactPoseBoneIndex(I); });
  bool Ok = Rig.bValid;
  printf("rig valid %d  arm %.1f + %.1f  leg %.1f + %.1f\n", Rig.bValid, Rig.Arm[0].Length[0], Rig.Arm[0].Length[1],
         Rig.Leg[0].Length[0], Rig.Leg[0].Length[1]);

  std::vector<Case> Cases;
  Cases.push_back({"seated", Seated()});
  { FDARiderIKTargets T = Seated(); T.Lean = 32.f; T.Pelvis = T.Pelvis + FVector(0, 2, -1); Cases.push_back({"tucked", T}); }
  { FDARiderIKTargets T = Seated(); T.Lean = 40.f; T.Pelvis = FVector(0, -2.2, 121.0); Cases.push_back({"standing on the pegs", T}); }
  { FDARiderIKTargets T = Seated(); T.Pelvis = FVector(12, 3.8, 104.5); T.Ball[0] = FVector(46, 26, -12); T.ToeDown[0] = 30.f;
    T.Roll = 7.f; Cases.push_back({"left foot down", T}); }
  Cases.push_back({"small rider (0.85)", ScaleTargets(Seated(), 1.0 / 0.85), 1.f, 0.85});
  Cases.push_back({"getting on (alpha 0.5)", Seated(), 0.5f});

  for (const Case& C : Cases)
  {
    FCSPose<FCompactPose> CS = MakePose(S);
    DARiderIK::Apply(Rig, CS, C.T, C.Alpha);
    bool CaseOk = true;
    // bone lengths
    double Stretch = 0;
    for (int B = 1; B < S.Ref.GetNum(); ++B)
    {
      const int P = S.Ref.Parents[B];
      if (P == 0) continue;   // the pelvis itself moves off the root onto the seat
      const double Rest = (S.RestCS[B].T - S.RestCS[P].T).Size();
      const double Now = (CS.GetComponentSpaceTransform(FCompactPoseBoneIndex(B)).T - CS.GetComponentSpaceTransform(FCompactPoseBoneIndex(P)).T).Size();
      Stretch = std::max(Stretch, std::fabs(Rest - Now));
      CaseOk &= Finite(CS.GetComponentSpaceTransform(FCompactPoseBoneIndex(B)).T);
    }
    CaseOk &= Stretch < 0.01;
    const FVector Pelvis = Pos(CS, S, "pelvis");
    const FVector Spine3 = Pos(CS, S, "spine_03");
    const double Lean = Deg(std::atan2(Spine3.Y - Pelvis.Y, Spine3.Z - Pelvis.Z));
    printf("%-24s stretch %.4f  pelvis err %.2f  back lean %.1f deg\n", C.Name, Stretch, (Pelvis - C.T.Pelvis).Size(), Lean);
    if (C.Alpha < 1.f)
    {
      // halfway on: unstretched, finite, the pelvis halfway between the take and the seat
      const double Half = (Pelvis - (FVector(0, 0, 93) + C.T.Pelvis) * 0.5).Size();
      printf("    halfway pelvis err %.2f\n", Half);
      CaseOk &= Half < 0.5;
      Ok &= CaseOk;
      printf("    %s\n", CaseOk ? "ok" : "FAIL");
      continue;
    }
    CaseOk &= (Pelvis - C.T.Pelvis).Size() < 0.01 && Lean > 8.0;
    // head pitched back up relative to the chest
    {
      const FQuat Chest = Rot(CS, S, "spine_03") * S.RestCS[S.Find("spine_03")].R.Inverse();
      const FQuat HeadQ = Rot(CS, S, "head") * S.RestCS[S.Find("head")].R.Inverse();
      const double ChestFwd = Chest.RotateVector(FVector(0, 0, 1)).Y, HeadFwd = HeadQ.RotateVector(FVector(0, 0, 1)).Y;
      printf("    head up-vector forward %.2f vs chest %.2f\n", HeadFwd, ChestFwd);
      CaseOk &= HeadFwd < ChestFwd;
    }
    for (int Side = 0; Side < 2; ++Side)
    {
      const char* Sx = Side == 0 ? "l" : "r";
      const double M = Side == 0 ? 1.0 : -1.0;
      char N[32];
      auto P = [&](const char* Bone) { snprintf(N, sizeof N, "%s_%s", Bone, Sx); return Pos(CS, S, N); };
      auto R = [&](const char* Bone) { snprintf(N, sizeof N, "%s_%s", Bone, Sx); return Rot(CS, S, N) * S.RestCS[S.Find(N)].R.Inverse(); };
      // arm: wrist at the grip, elbow out, palm down
      const FVector Sh = P("upperarm"), El = P("lowerarm"), Wr = P("hand");
      const double ToGrip = (Wr - C.T.Grip[Side]).Size();
      const FVector Line = (Wr - Sh).GetSafeNormal();
      const FVector ElbowOff = (El - Sh) - Line * FVector::DotProduct(El - Sh, Line);
      const FVector Palm = R("hand").RotateVector(FVector(0, 0, -1));   // T-pose palms face down
      const double Reach = (Wr - Sh).Size() / (Rig.Arm[Side].Length[0] + Rig.Arm[Side].Length[1]);
      // leg: ankle where the ball of the foot sits on its contact, knee forward and out
      const FVector Hip = P("thigh"), Kn = P("calf"), An = P("foot"), Ball = P("ball");
      const FVector Contact = FVector(Ball.X, Ball.Y, Ball.Z) - R("foot").RotateVector(FVector(0, 0, 3));
      const double ToPeg = (Contact - C.T.Ball[Side]).Size();
      const FVector LegLine = (An - Hip).GetSafeNormal();
      const FVector KneeOff = (Kn - Hip) - LegLine * FVector::DotProduct(Kn - Hip, LegLine);
      printf("    %s: wrist-grip %.1f (reach %.2f)  elbow out %.1f back %.1f  palm z %.2f | ball-contact err %.1f  knee fwd %.1f out %.1f (knee x %.1f)\n",
             Sx, ToGrip, Reach, ElbowOff.X * M, -ElbowOff.Y, Palm.Z, ToPeg, KneeOff.Y, KneeOff.X * M, Kn.X * M);
      const bool Reachable = !(Side == 0 && C.T.ToeDown[0] > 20.f);   // the foot-down leg may end short of the ground
      CaseOk &= ToGrip < DARiderIK::WristBehindGrip + 2.5 && ElbowOff.X * M > 1.0 && Palm.Z < -0.3;
      if (Reachable) CaseOk &= ToPeg < 1.0 && KneeOff.Y > 3.0 && KneeOff.X * M > 1.0;
      else
      {
        // short of the ground: the leg points straight at it
        const double Aim = Deg(std::acos(FVector::DotProduct((An - Hip).GetSafeNormal(), (C.T.Ball[Side] - Hip).GetSafeNormal())));
        printf("    foot-down leg aims %.1f deg off the ground point, %.1f cm short\n", Aim, ToPeg);
        CaseOk &= Aim < 12.0;
      }
    }
    Ok &= CaseOk;
    printf("    %s\n", CaseOk ? "ok" : "FAIL");
  }

  // Alpha 0: untouched
  {
    FCSPose<FCompactPose> CS = MakePose(S);
    FCSPose<FCompactPose> Ref = MakePose(S);
    DARiderIK::Apply(Rig, CS, Seated(), 0.f);
    double D = 0;
    for (int B = 0; B < S.Ref.GetNum(); ++B)
      D = std::max(D, (CS.GetComponentSpaceTransform(FCompactPoseBoneIndex(B)).T - Ref.GetComponentSpaceTransform(FCompactPoseBoneIndex(B)).T).Size());
    printf("alpha 0 max joint move %.4f\n", D);
    Ok &= D < 1e-6;
  }
  // a skeleton without the chain is rejected
  {
    Skel Bad = MakeCast();
    Bad.Ref.Names[Bad.Find("calf_r")] = "knee_r";
    DARiderIK::FRig BadRig;
    DARiderIK::Build(BadRig, Bad.Ref, [](int32 I) { return FCompactPoseBoneIndex(I); });
    printf("rig without calf_r valid %d\n", BadRig.bValid);
    Ok &= !BadRig.bValid;
  }
  printf(Ok ? "RIDER OK\n" : "RIDER FAIL\n");
  return Ok ? 0 : 1;
}
