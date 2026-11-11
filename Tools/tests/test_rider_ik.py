"""The Unreal motorcycle rider IK, compiled outside the engine.

Tools/tests/rider/extract.py copies FDARiderIKTargets and the DARiderIK namespace out of DAAvatarAnimInstance.h/.cpp
verbatim; rider/test_rider.cpp builds them against the UE stand-ins of springs/ue_mock.h and poses the cast
skeleton (with arbitrary bone axes) seated, tucked, standing on the pegs, with a foot down, as a smaller rider and
half-way through getting on. Skipped when no C++ compiler is installed.

    python -m unittest Tools.tests.test_rider_ik -v
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MODULE = REPO / "DuelAcademyIsland" / "Source" / "DuelAcademyIsland"
HEADER = MODULE / "Public" / "DAAvatarAnimInstance.h"
SOURCE = MODULE / "Private" / "DAAvatarAnimInstance.cpp"


def _compiler():
    for c in ("clang++", "g++"):
        if shutil.which(c):
            return c
    return None


@unittest.skipIf(_compiler() is None, "no C++ compiler")
class RiderIKTests(unittest.TestCase):
    def test_solver_compiles_and_poses_the_rider(self):
        with tempfile.TemporaryDirectory() as tmp:
            inc = os.path.join(tmp, "rider_extract.inc")
            subprocess.run([sys.executable, str(HERE / "rider" / "extract.py"), str(HEADER), str(SOURCE), inc],
                           check=True, capture_output=True, text=True)
            exe = os.path.join(tmp, "test_rider")
            build = subprocess.run([_compiler(), "-std=c++20", "-O1", "-Wall", "-Werror", "-Wno-unused-function",
                                    "-Wno-unused-variable", "-Wno-unused-const-variable", "-Wno-unknown-warning-option",
                                    "-Wno-subobject-linkage", "-I", tmp, "-I", str(HERE / "springs"),
                                    str(HERE / "rider" / "test_rider.cpp"), "-o", exe], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([exe], capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("RIDER OK", run.stdout)


if __name__ == "__main__":
    unittest.main()
