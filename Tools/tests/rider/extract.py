"""python extract.py <DAAvatarAnimInstance.h> <DAAvatarAnimInstance.cpp> [out.inc]

Pull the motorcycle rider IK out of the anim instance verbatim (FDARiderIKTargets from the header, the DARiderIK
namespace from the .cpp, both between their "rider IK ... begin / end" marker comments) so it can be compiled
against Tools/tests/springs/ue_mock.h."""
import sys


def block(path, begin, end):
    lines = open(path).read().split("\n")
    i = next(i for i, l in enumerate(lines) if l.startswith(begin))
    j = next(j for j in range(i, len(lines)) if lines[j].startswith(end))
    return lines[i:j + 1]


header, source = sys.argv[1], sys.argv[2]
out = ["// generated from " + header + " and " + source]
out += block(header, "// ---- rider IK targets begin", "// ---- rider IK targets end")
out += block(source, "// ---- rider IK begin", "// ---- rider IK end")
dst = sys.argv[3] if len(sys.argv) > 3 else "rider_extract.inc"
open(dst, "w").write("\n".join(out) + "\n")
print("extracted", len(out), "lines ->", dst)
