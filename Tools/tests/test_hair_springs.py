"""The Unreal hair spring solver, compiled outside the engine.

Tools/tests/springs/extract.py copies the spring solver out of DAAvatarAnimInstance.cpp verbatim (the
spring parameter namespace, FDASpringChain, BuildChains, ApplySprings); test_springs.cpp builds it against
small stand-ins for the UE types (springs/ue_mock.h) and runs it on a synthetic head of hair. Skipped when
no C++ compiler is installed.

    python -m unittest Tools.tests.test_hair_springs -v
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent / "springs"
SOURCE = REPO / "DuelAcademyIsland" / "Source" / "DuelAcademyIsland" / "Private" / "DAAvatarAnimInstance.cpp"


def _compiler():
    for c in ("clang++", "g++"):
        if shutil.which(c):
            return c
    return None


@unittest.skipIf(_compiler() is None, "no C++ compiler")
class HairSpringSolverTests(unittest.TestCase):
    def test_solver_compiles_and_behaves(self):
        with tempfile.TemporaryDirectory() as tmp:
            inc = os.path.join(tmp, "solver_extract.inc")
            subprocess.run([sys.executable, str(HERE / "extract.py"), str(SOURCE), inc], check=True,
                           capture_output=True, text=True)
            exe = os.path.join(tmp, "test_springs")
            build = subprocess.run([_compiler(), "-std=c++20", "-O1", "-Wall", "-Werror", "-Wno-unused-function",
                                    "-Wno-unused-variable", "-Wno-unused-const-variable", "-Wno-unknown-warning-option",
                                    "-Wno-subobject-linkage", "-I", tmp, "-I", str(HERE),
                                    str(HERE / "test_springs.cpp"), "-o", exe], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([exe], capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("SPRINGS OK", run.stdout)


if __name__ == "__main__":
    unittest.main()
