"""python extract.py <DAAvatarAnimInstance.cpp> [out.inc]

Pull the spring solver out of DAAvatarAnimInstance.cpp verbatim (namespace helpers, FDASpringChain, the proxy's
spring members, BuildChains and ApplySprings) so it can be compiled against ue_mock.h."""
import re, sys
src = open(sys.argv[1]).read()
lines = src.split("\n")
ns0 = next(i for i, l in enumerate(lines) if l.strip() == "namespace")
ns1 = next(i for i in range(ns0, len(lines)) if lines[i] == "}")
ch0 = next(i for i, l in enumerate(lines) if l.startswith("struct FDASpringChain"))
ch1 = next(i for i in range(ch0, len(lines)) if lines[i] == "};")

def func(name):
    i = next(i for i, l in enumerate(lines) if re.match(r"\s*void %s\(" % name, l))
    # include the doc comment above
    j = i
    while lines[j - 1].strip().startswith(("/**", "*", "//")) and lines[j - 1].strip():
        j -= 1
    depth, k, started = 0, i, False
    while True:
        depth += lines[k].count("{") - lines[k].count("}")
        if "{" in lines[k]:
            started = True
        if started and depth == 0:
            break
        k += 1
    return "\n".join(lines[j:k + 1])

out = ["// generated from " + sys.argv[1]]
out += lines[ns0:ns1 + 1]
out += lines[ch0:ch1 + 1]
out.append('''struct FDAAnimInstanceProxy
{
	FTransform SimComponentToWorld = FTransform::Identity;
	float SimDt = 0.f;
	bool bSprings = true;
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
	int32 StatChains = 0;
	float StatMaxDeflection = 0.f;''')
out.append(func("BuildChains"))
out.append(func("ApplySprings"))
out.append("};")
dst = sys.argv[2] if len(sys.argv) > 2 else "solver_extract.inc"
open(dst, "w").write("\n".join(out) + "\n")
print("extracted", len(out), "blocks ->", dst)
