"""
Student avatar body parts (stylised GX uniform). Animated procedurally in C++
(ADAStudentCharacter / UDAAvatarComponent) - each part has its pivot at its joint:

  SM_Avatar_Torso   pivot at the pelvis (z = 0); shoulders at z = +0.50, neck at +0.56
  SM_Avatar_Head    pivot at the neck base
  SM_Avatar_ArmL/R  pivot at the shoulder, hanging down -Z (0.66 m incl. hand)
  SM_Avatar_LegL/R  pivot at the hip joint, hanging down -Z (0.93 m to the sole)
  SM_Avatar_DuelDisk  pivot at the wrist mount (attached to the left forearm)

The figure faces -Y (Blender) like every other asset; the C++ side rotates it.
Material slot "M_Jacket" is recoloured per dorm at runtime.
"""

import math

from ..geo import MeshBuilder, TAU
from .props import blob, tube

HIP_HEIGHT = 0.93
SHOULDER = 0.50
SHOULDER_HALF_WIDTH = 0.21
HIP_HALF_WIDTH = 0.09


def torso():
    mb = MeshBuilder("Avatar_Torso")
    # pelvis (pants)
    mb.lathe([(0.13, -0.08), (0.155, 0.0), (0.15, 0.1)], "M_Pants", seg=12, sx=1.0, sy=0.75)
    # jacket body: tapered lathe, slightly flattened front/back
    mb.lathe([(0.172, -0.06), (0.16, 0.14), (0.165, 0.30), (0.19, 0.44), (0.12, 0.53)], "M_Jacket", seg=14, sx=1.0, sy=0.68,
             cap_top=True, cap_bottom=True)
    # open front showing the dark shirt (a slightly protruding panel)
    mb.box((0, -0.112, 0.36), (0.10, 0.02, 0.32), "M_Shirt")
    # white collar / lapels
    for s in (-1, 1):
        mb.beam((s * 0.035, -0.112, 0.5), (s * 0.07, -0.117, 0.36), 0.03, 0.018, "M_WindowFrame")
    # blazer hem flaring over the hips
    mb.lathe([(0.168, 0.05), (0.178, -0.04), (0.188, -0.13)], "M_Jacket", seg=14, sx=1.0, sy=0.74,
             cap_top=False, cap_bottom=True)
    # shoulders
    for s in (-1, 1):
        mb.sphere((s * SHOULDER_HALF_WIDTH * 0.9, 0, SHOULDER - 0.03), 0.075, "M_Jacket", seg=10, rings=6)
    # neck
    mb.cylinder((0, 0, 0.5), 0.045, 0.08, "M_Skin", seg=8)
    return mb


def head():
    mb = MeshBuilder("Avatar_Head")
    mb.sphere((0, 0, 0.14), 0.115, "M_Skin", seg=14, rings=10, scale=(1.0, 0.95, 1.12))
    # eyes (big anime eyes)
    for s in (-1, 1):
        mb.sphere((s * 0.042, -0.098, 0.15), 0.024, "M_Black", seg=8, rings=6, scale=(0.8, 0.4, 1.25))
        mb.sphere((s * 0.038, -0.108, 0.162), 0.007, "M_WindowFrame", seg=6, rings=4)
    # spiky two-tone hair
    blob(mb, (0, 0.01, 0.2), 0.125, "M_Hair", seed=3, seg=12, rings=8, scale=(1.05, 1.05, 0.9), rough=0.08)
    spikes = [((0.0, -0.08, 0.27), (0.0, -0.17, 0.36)), ((0.06, -0.07, 0.26), (0.11, -0.15, 0.33)),
              ((-0.06, -0.07, 0.26), (-0.12, -0.15, 0.32)), ((0.1, 0.0, 0.25), (0.2, 0.02, 0.3)),
              ((-0.1, 0.0, 0.25), (-0.2, 0.02, 0.29)), ((0.0, 0.08, 0.27), (0.0, 0.18, 0.31)),
              ((0.07, 0.06, 0.28), (0.12, 0.15, 0.35)), ((-0.07, 0.06, 0.28), (-0.13, 0.14, 0.34)),
              ((0.0, 0.0, 0.3), (0.02, -0.04, 0.42))]
    for i, (a, b) in enumerate(spikes):
        mat = "M_Hair" if i % 3 else "M_Gold"
        tube(mb, [a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2 + 0.01), b], [0.05, 0.03, 0.002], mat, seg=6)
    # ears
    for s in (-1, 1):
        mb.sphere((s * 0.112, 0.0, 0.14), 0.022, "M_Skin", seg=6, rings=4, scale=(0.5, 1, 1.2))
    return mb


def arm(side):
    mb = MeshBuilder(f"Avatar_Arm{'L' if side < 0 else 'R'}")
    tube(mb, [(0, 0, 0.02), (0, 0, -0.28), (0, 0, -0.52)], [0.06, 0.052, 0.045], "M_Jacket", seg=10)
    # white cuff
    tube(mb, [(0, 0, -0.5), (0, 0, -0.545)], [0.05, 0.05], "M_WindowFrame", seg=10)
    # hand
    blob(mb, (0, -0.01, -0.6), 0.045, "M_Skin", seed=7, seg=8, rings=6, scale=(0.8, 1.0, 1.4), rough=0.05)
    return mb


def leg(side):
    mb = MeshBuilder(f"Avatar_Leg{'L' if side < 0 else 'R'}")
    tube(mb, [(0, 0, 0.02), (0, 0, -0.42), (0, 0, -0.82)], [0.075, 0.06, 0.055], "M_Pants", seg=10)
    # shoe (points forward, -Y)
    blob(mb, (0, -0.045, -0.885), 0.07, "M_Shoes", seed=11, seg=10, rings=6, scale=(0.75, 1.55, 0.6), rough=0.02,
         flat_bottom=0.35)
    return mb


def duel_disk():
    mb = MeshBuilder("Avatar_DuelDisk")
    # forearm mount + disk body + card blade (stylised, original)
    # round centre piece on the outside of the forearm, card blade folded along the arm
    with mb.at((-0.035, 0, 0.0), rot_y=-90):
        mb.cylinder((0, 0, -0.02), 0.085, 0.04, "M_DuelDisk", seg=14)
        mb.cylinder((0, 0, 0.02), 0.04, 0.02, "M_Gold", seg=10)
    mb.box((-0.045, 0.0, 0.14), (0.025, 0.13, 0.36), "M_DuelDisk")
    for k in range(5):
        mb.box((-0.06, 0.0, 0.0 + k * 0.065 + 0.03), (0.008, 0.095, 0.05), "M_DuelFieldGlow")
    return mb


PARTS = {
    "Avatar_Torso": torso,
    "Avatar_Head": head,
    "Avatar_ArmL": lambda: arm(-1),
    "Avatar_ArmR": lambda: arm(1),
    "Avatar_LegL": lambda: leg(-1),
    "Avatar_LegR": lambda: leg(1),
    "Avatar_DuelDisk": duel_disk,
}

# joint offsets relative to the pelvis pivot (metres, Blender axes, figure faces -Y)
JOINTS = {
    "Avatar_Head": (0.0, 0.0, 0.56),
    "Avatar_ArmL": (-SHOULDER_HALF_WIDTH, 0.0, SHOULDER - 0.02),
    "Avatar_ArmR": (SHOULDER_HALF_WIDTH, 0.0, SHOULDER - 0.02),
    "Avatar_LegL": (-HIP_HALF_WIDTH, 0.0, 0.0),
    "Avatar_LegR": (HIP_HALF_WIDTH, 0.0, 0.0),
    "Avatar_DuelDisk": (-0.04, 0.0, -0.40),   # relative to the LEFT arm pivot
}


def build_preview():
    """AssetSet with an assembled avatar (for preview_asset.py avatar)."""
    from . import AssetSet
    a = AssetSet("avatar")
    full = a.mesh("Avatar_Assembled")
    full.extend(torso(), (0, 0, HIP_HEIGHT))
    full.extend(head(), (0, 0, HIP_HEIGHT + JOINTS["Avatar_Head"][2]))
    for k in ("Avatar_ArmL", "Avatar_ArmR", "Avatar_LegL", "Avatar_LegR"):
        j = JOINTS[k]
        full.extend(PARTS[k](), (j[0], j[1], HIP_HEIGHT + j[2]))
    jl = JOINTS["Avatar_ArmL"]
    jd = JOINTS["Avatar_DuelDisk"]
    full.extend(duel_disk(), (jl[0] + jd[0], jl[1] + jd[1], HIP_HEIGHT + jl[2] + jd[2]))
    return a


PLACEMENTS = {"avatar": build_preview}
