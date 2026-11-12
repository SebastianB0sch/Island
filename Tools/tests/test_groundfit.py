"""Tests for the vegetation ground fit and spacing (Tools/dai/groundfit.py).

Only the numpy parts are exercised (measuring a prop needs Blender), so this runs in CI.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from dai import groundfit  # noqa: E402


def slope(gx, gy):
    """A planar terrain z = gx * x + gy * y (vectorised like the terrain samplers)."""
    return lambda x, y: gx * np.asarray(x, np.float64) + gy * np.asarray(y, np.float64)


def boulder():
    """A 2 m wide, 1 m tall half-dome."""
    v = []
    for i in range(13):
        a = 2 * math.pi * i / 13
        for k in range(5):
            el = (math.pi / 2) * k / 4
            v.append((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el)))
    return groundfit.Footprint("rock", v, reach=0.2)


def hover(hf, fp, x, y, yaw, s, z, M):
    """Largest height of any underside point above the ground."""
    worst = -1e9
    for (px, py, b) in fp.pts:
        d = M @ np.array([px, py, b + fp.z0]) * s
        worst = max(worst, z + d[2] - float(hf(x + d[0], y + d[1])))
    return worst


class GroundFitTests(unittest.TestCase):
    def test_nothing_hovers_on_a_slope(self) -> None:
        fp = boulder()
        hf = slope(0.6, -0.2)
        for tilt in (0.0, 0.8):
            z, buried, _step, M, out = groundfit.seat(hf, [3.0], [4.0], [40.0], [1.5], fp, gap=0.0, tilt=tilt,
                                                      max_tilt=40.0)
            self.assertLessEqual(hover(hf, fp, 3.0, 4.0, 40.0, 1.5, z[0], M[0]), 1e-6)
            self.assertGreater(out[0], 0.2, "the boulder still stands out of the slope")

    def test_bedding_into_the_slope_buries_less(self) -> None:
        fp = boulder()
        hf = slope(0.7, 0.0)
        upright = groundfit.seat(hf, [0.0], [0.0], [0.0], [1.0], fp, tilt=0.0)
        bedded = groundfit.seat(hf, [0.0], [0.0], [0.0], [1.0], fp, tilt=0.8, max_tilt=40.0)
        self.assertLess(bedded[1][0], upright[1][0])
        self.assertGreater(bedded[4][0], upright[4][0])

    def test_flat_ground_seats_on_the_surface(self) -> None:
        fp = boulder()
        z, buried, step, _M, out = groundfit.seat(slope(0.0, 0.0), [1.0], [1.0], [0.0], [1.0], fp, gap=0.03)
        self.assertAlmostEqual(z[0], 0.03, places=6)
        self.assertAlmostEqual(step[0], 0.0, places=6)
        self.assertAlmostEqual(out[0], 1.03, places=6)

    def test_rotator_round_trip_and_bare_yaw(self) -> None:
        hf = slope(0.4, 0.25)
        M = groundfit.tilt_matrices(np.array([0.0, 5.0]), np.array([0.0, 2.0]), np.array([30.0, 200.0]), hf,
                                    1.0, 0.8, 30.0)
        yaw, pitch, roll = groundfit.ue_rotator(M)
        for i in range(2):
            np.testing.assert_allclose(groundfit.blender_matrix(yaw[i], pitch[i], roll[i]), M[i], atol=1e-9)
        # the local up axis leans down the fall line
        self.assertLess(M[0][0, 2], 0.0)
        self.assertLess(M[0][1, 2], 0.0)
        # no tilt: Unreal's yaw is Blender's mirrored, pitch and roll stay level
        flat = groundfit.tilt_matrices(np.array([0.0]), np.array([0.0]), np.array([30.0]), hf, 1.0, 0.0, 30.0)
        yaw, pitch, roll = groundfit.ue_rotator(flat)
        self.assertAlmostEqual(yaw[0], -30.0, places=6)
        self.assertAlmostEqual(pitch[0], 0.0, places=6)
        self.assertAlmostEqual(roll[0], 0.0, places=6)

    def test_spacing_keeps_trunks_apart_and_lets_crowns_interlock(self) -> None:
        sp = groundfit.Spacing()
        sp.add(0.0, 0.0, 0.6, 5.0)
        self.assertFalse(sp.ok(0.9, 0.0, 0.6, 5.0, interlock=1.0), "trunks overlap")
        self.assertFalse(sp.ok(4.0, 0.0, 0.6, 5.0, interlock=0.5), "crowns would merge")
        self.assertTrue(sp.ok(5.5, 0.0, 0.6, 5.0, interlock=0.5), "crowns interlock by half")
        self.assertTrue(sp.ok(2.0, 0.0, 0.3, 0.0), "an understory plant only keeps off the trunk")


if __name__ == "__main__":
    unittest.main()
