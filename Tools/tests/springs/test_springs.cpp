// Runs the spring solver of DAAvatarAnimInstance.cpp (extracted verbatim by extract.py into solver_extract.inc)
// against ue_mock.h on a synthetic head of hair (cm, Z up, mesh forward +Y): ten short chains round the head
// and four long chains down the back. Checks the solver compiles, stays finite, keeps every joint inside its
// cone (short 18, long 50 degrees) idle / running at 4.2 m/s / running into a 90 deg/s turn, and that the
// cohesion pull keeps a kicked long lock with its neighbour. Driven by Tools/tests/test_hair_springs.py.
#include "ue_mock.h"
#include <cstdio>
#include "solver_extract.inc"

struct Scene {
  FReferenceSkeleton Ref;
  std::vector<FTransform> CSRef;
  int Add(const std::string& n, int parent, FVector cs) {
    Ref.Names.push_back(n); Ref.Parents.push_back(parent);
    FVector loc = parent < 0 ? cs : cs - CSRef[parent].T;
    Ref.Ref.Add(FTransform(FQuat::Identity, loc)); CSRef.push_back(FTransform(FQuat::Identity, cs));
    return (int)Ref.Names.size() - 1;
  }
};

struct Result { double mean = 0, peak = 0, short_peak = 0, long_peak = 0, spread = 0; bool finite = true; int chains = 0; };

Result Run(double speed, double yaw_rate, double bob, bool cohesion, int frames = 150, double kick = 0) {
  Scene S;
  int root = S.Add("root", -1, {0, 0, 0});
  int spine = S.Add("spine_02", root, {0, 0, 125});
  int neck = S.Add("neck_01", spine, {0, 0, 145});
  int head = S.Add("head", neck, {0, 0, 152});
  FVector hc(0, -1, 161);
  char nm[64];
  for (int c = 0; c < 10; ++c) {                       // short hair round the head
    double az = 2 * M_PI * c / 10; FVector out(std::sin(az), std::cos(az), 0);
    FVector p = hc + out * 9.0 + FVector(0, 0, 4);
    int parent = head;
    for (int j = 0; j < 5; ++j) {
      snprintf(nm, sizeof nm, "HairJoint_Test_Short%02d_%d", c, j);
      parent = S.Add(nm, parent, p + out * (1.5 * j) + FVector(0, 0, -3.5 * j));
    }
  }
  for (int c = 0; c < 4; ++c) {                        // long hair down the back
    double x = -6 + 4 * c;
    int parent = head;
    for (int j = 0; j < 7; ++j) {
      snprintf(nm, sizeof nm, "HairJoint_Test_Long%02d_%d", c, j);
      parent = S.Add(nm, parent, FVector(x, -11 - 0.6 * j, 158 - 7.0 * j));
    }
  }
  FDAAnimInstanceProxy P;
  P.BuildChains(S.Ref);
  for (auto& Ch : P.Chains) {
    Ch.Bones.Reset();
    for (auto b : Ch.SkeletonBones) Ch.Bones.Add(FCompactPoseBoneIndex(b));
    Ch.bValid = true;
    if (!cohesion) Ch.Params.Cohesion = 0.f;
  }
  P.HeadIndex = FCompactPoseBoneIndex(head); P.NeckIndex = FCompactPoseBoneIndex(neck); P.SpineIndex = FCompactPoseBoneIndex(spine);
  Result R; R.chains = P.Chains.Num();
  const double dt = 1.0 / 30.0; double yaw = 0; FVector pos;
  int counted = 0;
  for (int f = 0; f < frames; ++f) {
    double t = f * dt;
    yaw += yaw_rate * dt;
    FQuat q(FVector(0, 0, 1), yaw * M_PI / 180.0);
    pos += q.RotateVector(FVector(0, speed * dt, 0));
    P.SimComponentToWorld = FTransform(q, pos);
    P.SimDt = (float)dt;
    FCSPose<FCompactPose> CS;
    CS.Parent = S.Ref.Parents;
    for (auto& l : S.Ref.Ref) CS.Pose.L.push_back(l);
    CS.Pose.L[head].T.Z += bob * std::sin(2 * M_PI * t / 0.35);   // two bobs per 0.7 s stride
    if (kick > 0 && f == 40) { for (int j = 1; j < P.Chains[10].CurTail.Num(); ++j) P.Chains[10].CurTail[j] += FVector(kick, 0, 0); }
    P.ApplySprings(CS);
    // per chain: joint deflection from the animated direction, and joint-0 deviation for the cohesion spread
    std::vector<FVector> dev;
    std::vector<int> isShort;
    for (auto& Ch : P.Chains) {
      for (int j = 0; j + 1 < Ch.Bones.Num(); ++j) {
        FTransform simB = CS.GetComponentSpaceTransform(Ch.Bones[j]);
        FTransform simC = CS.GetComponentSpaceTransform(Ch.Bones[j + 1]);
        FVector simDir = (simC.T - simB.T).GetSafeNormal();
        FVector animDir = simB.R.RotateVector(CS.Pose.L[Ch.Bones[j + 1].GetInt()].T).GetSafeNormal();
        // bone j itself was turned: its animated direction is the parent's frame applied to the child offset
        FTransform parentCS = CS.GetComponentSpaceTransform(FCompactPoseBoneIndex(S.Ref.Parents[Ch.Bones[j].GetInt()]));
        animDir = parentCS.R.RotateVector(CS.Pose.L[Ch.Bones[j + 1].GetInt()].T).GetSafeNormal();
        double ang = std::acos(std::max(-1.0, std::min(1.0, FVector::DotProduct(simDir, animDir)))) * 57.2958;
        if (!std::isfinite(ang) || !std::isfinite(simC.T.X)) R.finite = false;
        bool sh = Ch.Params.MaxAngle < 30.f;
        if (f >= 30) { if (sh) R.short_peak = std::max(R.short_peak, ang); else R.long_peak = std::max(R.long_peak, ang); }
      }
      FVector d = Ch.CurTail[0] - P.SimComponentToWorld.TransformPosition(
          (CS.Pose.L[Ch.Bones[1].GetInt()] * (CS.Pose.L[Ch.Bones[0].GetInt()] * CS.GetComponentSpaceTransform(FCompactPoseBoneIndex(head)))).T);
      dev.push_back(d); isShort.push_back(Ch.Params.MaxAngle < 30.f);
    }
    if (f >= 30) {
      R.mean += P.StatMaxDeflection; R.peak = std::max(R.peak, (double)P.StatMaxDeflection); ++counted;
      double num = 0, den = 0;
      for (int c = 0; c < 10; ++c) { num += (dev[c] - dev[(c + 1) % 10]).Size(); den += dev[c].Size(); }
      if (kick > 0) { if (f >= 41 && f <= 70) { FVector t10 = P.Chains[10].CurTail.Last(), t11 = P.Chains[11].CurTail.Last(); R.spread += std::fabs((t10 - t11).Size() - 4.0); } }
      else if (den > 1e-6) R.spread += num / den;
    }
  }
  R.mean /= counted; R.spread /= (kick > 0 ? 30 : counted);
  return R;
}

int main() {
  struct { const char* name; double v, yaw, bob; bool coh; } cases[] = {
    {"idle          ", 0, 0, 0.3, true}, {"run 4.2 m/s   ", 420, 0, 3.0, true},
    {"run + turn    ", 420, 90, 3.0, true}, {"run + turn, no cohesion", 420, 90, 3.0, false}};
  bool ok = true;
  for (auto& c : cases) {
    Result r = Run(c.v, c.yaw, c.bob, c.coh);
    printf("%-24s chains %d  mean %.1f  peak %.1f  short peak %.1f (cone 18)  long peak %.1f (cone 50)  neighbour spread %.2f  finite %d\n",
           c.name, r.chains, r.mean, r.peak, r.short_peak, r.long_peak, r.spread, r.finite);
    ok &= r.finite && r.short_peak <= 18.5 && r.long_peak <= 50.5;
  }
  Result a = Run(0, 0, 0.3, true, 150, 6.0), b = Run(0, 0, 0.3, false, 150, 6.0);
  printf("kick one long lock 6 cm sideways: change in tip gap to its neighbour (rest 4 cm) over the next second %.2f cm with cohesion, %.2f cm without\n", a.spread, b.spread);
  ok &= a.spread < b.spread;
  printf(ok ? "SPRINGS OK\n" : "SPRINGS FAIL\n");
  return ok ? 0 : 1;
}
