"""
Reproducible builds: Python randomises string hashing per process, so the iteration order of any set of
names can change between runs - and the cloth fit (tie-breaking in relaxation, region choices) follows it.
pin_hash_seed() re-launches the current script with PYTHONHASHSEED=0 when it is not pinned already, so the
same inputs always give the same cast (and the fit audit measures exactly what the build exported).
"""

import os
import sys


def pin_hash_seed():
    if os.environ.get("PYTHONHASHSEED") == "0":
        return
    env = dict(os.environ, PYTHONHASHSEED="0")
    os.execve(sys.executable, [sys.executable] + sys.argv, env)
