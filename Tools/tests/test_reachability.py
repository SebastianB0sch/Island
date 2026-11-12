"""Tests for the walk-in reachability audit's pure parts (Tools/world/navgrid.py, check_reachability.py).

Synthetic triangle scenes only - the full world check (minutes, needs the exported meshes) is not run here.
Needs numpy (the audit's only dependency).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

WORLD = Path(__file__).resolve().parents[1] / "world"
sys.path.insert(0, str(WORLD))

import check_reachability as CR  # noqa: E402
import navgrid as NG  # noqa: E402


def quad(x0, y0, x1, y1, z):
    """Horizontal rectangle as two upward-facing triangles."""
    return [[(x0, y0, z), (x1, y0, z), (x1, y1, z)], [(x0, y0, z), (x1, y1, z), (x0, y1, z)]]


def box(x0, y0, z0, x1, y1, z1):
    """Closed axis-aligned box (12 triangles, outward normals)."""
    p = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7),
             (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return [[p[a], p[b], p[c]] for a, b, c in faces]


def field(tris, size=(6.0, 4.0, 4.0), cs=0.1, agent=NG.Agent()):
    t = np.asarray(tris, np.float64)
    return NG.build_field(t, np.zeros(len(t), np.int8), np.array([0.0, 0.0, -0.5]), np.array(size), cs, agent)


def reach(f, a, b, origin=(0.0, 0.0, -0.5)):
    o = np.asarray(origin)
    ia = f.snap(*(np.asarray(a) - o), reach=0.3, dz=0.3)
    ib = f.snap(*(np.asarray(b) - o), reach=0.3, dz=0.3)
    if ia < 0 or ib < 0:
        return False
    return bool(f.flood([ia])[ib])


def wall_with_gap(gap, x=3.0, y0=0.0, y1=4.0, h=3.0):
    """A wall across the room at x (0.2 m thick) with a doorway of width `gap` centred at y = 2."""
    a, b = 2.0 - gap / 2, 2.0 + gap / 2
    return box(x - 0.1, y0, 0.0, x + 0.1, a, h) + box(x - 0.1, b, 0.0, x + 0.1, y1, h)


class NavgridTests(unittest.TestCase):
    def test_open_floor_is_connected(self):
        f = field(quad(0, 0, 6, 4, 0.0))
        self.assertTrue(reach(f, (1.0, 2.0, 0.0), (5.0, 2.0, 0.0)))

    def test_wall_separates_and_doorway_connects(self):
        floor = quad(0, 0, 6, 4, 0.0)
        self.assertFalse(reach(field(floor + wall_with_gap(0.0)), (1.0, 2.0, 0.0), (5.0, 2.0, 0.0)))
        self.assertFalse(reach(field(floor + wall_with_gap(0.5)), (1.0, 2.0, 0.0), (5.0, 2.0, 0.0)))
        self.assertTrue(reach(field(floor + wall_with_gap(1.0)), (1.0, 2.0, 0.0), (5.0, 2.0, 0.0)))

    def test_step_height_limit(self):
        for rise, ok in ((0.40, True), (0.55, False)):
            tris = quad(0, 0, 3, 4, 0.0) + box(3, 0, 0.0, 6, 4, rise)
            self.assertEqual(reach(field(tris), (1.0, 2.0, 0.0), (5.0, 2.0, rise)), ok, rise)

    def test_low_ceiling_blocks(self):
        floor = quad(0, 0, 6, 4, 0.0)
        for zc, ok in ((2.1, True), (1.6, False)):
            lintel = box(2.8, 0.0, zc, 3.2, 4.0, zc + 0.3)          # a beam across the whole room
            self.assertEqual(reach(field(floor + lintel), (1.0, 2.0, 0.0), (5.0, 2.0, 0.0)), ok, zc)

    def test_small_hole_is_bridged_large_is_not(self):
        for gap, ok in ((0.2, True), (0.8, False)):
            tris = quad(0, 0, 3 - gap / 2, 4, 0.0) + quad(3 + gap / 2, 0, 6, 4, 0.0)
            self.assertEqual(reach(field(tris), (1.0, 2.0, 0.0), (5.0, 2.0, 0.0)), ok, gap)

    def test_npc_radius_mask_is_less_strict(self):
        # a 0.75 m corridor between two walls: wider than the 36 cm NPC needs on a fine grid, narrower than the
        # 38 cm player
        tris = quad(0, 0, 6, 4, 0.0) + box(0, 0, 0, 6, 1.625, 3.0) + box(0, 2.375, 0, 6, 4, 3.0)
        f = field(tris, cs=0.025)
        i = f.snap(3.0, 2.0, 0.5, reach=0.05, dz=0.3, standable=False)
        self.assertGreaterEqual(i, 0)
        self.assertFalse(bool(f.stand[i]))
        self.assertTrue(bool(f.stand_mask(0.36)[i]))
        self.assertGreaterEqual(f.snap(3.0, 2.0, 0.5, reach=0.05, dz=0.3, stand=f.stand_mask(0.36)), 0)

    def test_components_count_separate_rooms(self):
        f = field(quad(0, 0, 6, 4, 0.0) + wall_with_gap(0.0))
        lab, n = f.components(f.stand & (np.abs(f.fz - 0.5) < 0.1))     # the floor (not the top of the wall)
        self.assertEqual(n, 2)

    def test_thin_wall_does_not_leak(self):
        # walls 0.2 and 0.3 m thick read like a bridgeable gap between their face columns; the floors beside
        # them must still get the radius test (regression: the flood used to walk through such walls)
        for t in (0.2, 0.3):
            tris = quad(0, 0, 6, 4, 0.0) + box(3.0 - t / 2, 0.0, 0.0, 3.0 + t / 2, 4.0, 3.0)
            self.assertFalse(reach(field(tris), (1.0, 2.0, 0.0), (5.0, 2.0, 0.0)), t)


class AuditHelperTests(unittest.TestCase):
    def test_ue_round_trip(self):
        p = np.array([12.5, -3.25, 4.0])
        self.assertTrue(np.allclose(CR.from_ue(CR.to_ue(p)), p))
        self.assertEqual(CR.to_ue([1.0, 2.0, 3.0]), [100.0, -200.0, 300.0])

    def test_rot_z(self):
        q = CR.rot_z(np.array([1.0, 0.0, 0.5]), 90.0)
        self.assertTrue(np.allclose(q, [0.0, 1.0, 0.5]))

    def test_ray_hits(self):
        tris = np.asarray(box(2.0, -1.0, -1.0, 3.0, 1.0, 1.0), np.float64)
        d = CR.ray_hits(np.zeros(3), np.array([1.0, 0.0, 0.0]), tris, 10.0)
        self.assertAlmostEqual(d, 2.0, places=6)
        self.assertEqual(CR.ray_hits(np.zeros(3), np.array([-1.0, 0.0, 0.0]), tris, 10.0), 10.0)

    def test_measure_door(self):
        # 0.9 x 2.1 m opening in a wall along x (door yaw 0: the wall runs along x, its normal is y)
        w, h = 0.9, 2.1
        wall = box(-3.0, -0.1, 0.0, -w / 2, 0.1, 3.0) + box(w / 2, -0.1, 0.0, 3.0, 0.1, 3.0) + \
            box(-w / 2, -0.1, h, w / 2, 0.1, 3.0) + quad(-3.0, -1.0, 3.0, 1.0, 0.0)
        cw, ch = CR.measure_door(np.zeros(3), 0.0, 1.0, 2.2, np.asarray(wall, np.float64))
        self.assertAlmostEqual(cw, w, places=3)
        self.assertAlmostEqual(ch, h, places=3)

    def test_storeys_merge_close_levels(self):
        f = field(quad(0, 0, 6, 4, 0.0) + quad(0, 0, 6, 4, 0.5) + quad(0, 0, 6, 4, 3.0), size=(6.0, 4.0, 6.0))
        st = CR.storeys(f, f.stand)
        self.assertEqual(len(st), 2)                     # 0.0 and 0.5 are one storey (STOREY_BAND), 3.0 another

    def test_accept_list_matches_boxes(self):
        acc = {"town": [{"box": [0, 0, 0, 2, 2, 2], "reason": "sealed void"}]}
        self.assertEqual(CR.accepted(acc, "town", np.array([1.0, 1.0, 1.0])), "sealed void")
        self.assertIsNone(CR.accepted(acc, "town", np.array([3.0, 1.0, 1.0])))
        self.assertIsNone(CR.accepted(acc, "other", np.array([1.0, 1.0, 1.0])))

    def test_accept_ring_matches_annulus(self):
        acc = {"arena": [{"ring": [0, 0, 2, 4, 0, 1], "reason": "hollow under the stands"}]}
        self.assertEqual(CR.accepted(acc, "arena", np.array([0.0, 3.0, 0.5])), "hollow under the stands")
        self.assertIsNone(CR.accepted(acc, "arena", np.array([1.0, 0.0, 0.5])))      # inside the inner radius
        self.assertIsNone(CR.accepted(acc, "arena", np.array([0.0, 3.0, 1.5])))      # above the band

    def test_shipped_accept_list_is_well_formed(self):
        if not CR.ACCEPT.exists():
            self.skipTest("no accept list")
        data = json.loads(CR.ACCEPT.read_text(encoding="utf-8"))
        for group, entries in data.items():
            if group.startswith("_"):
                continue
            for e in entries:
                self.assertGreater(len(e["reason"]), 20, (group, e))
                if "ring" in e:
                    r = e["ring"]
                    self.assertEqual(len(r), 6, group)
                    self.assertTrue(0 <= r[2] <= r[3] and r[4] <= r[5], (group, r))
                    continue
                self.assertEqual(len(e["box"]), 6, group)
                self.assertTrue(all(e["box"][k] <= e["box"][k + 3] for k in range(3)), (group, e["box"]))


class HullTests(unittest.TestCase):
    """Floors inside a prop's convex collision hull (solid in Unreal) are not floors."""

    def test_hull_planes_box(self):
        h = CR.hull_planes(np.asarray(box(0, 0, 0, 2, 6, 2.6), np.float64))
        self.assertIsNotNone(h)
        nrm, d, lo, hi = h
        inside = np.all(np.array([1.0, 3.0, 0.05]) @ nrm.T - d < 0)
        outside = np.all(np.array([3.0, 3.0, 0.05]) @ nrm.T - d < 0)
        self.assertTrue(inside)
        self.assertFalse(outside)
        self.assertTrue(np.allclose(lo, [0, 0, 0]) and np.allclose(hi, [2, 6, 2.6]))

    def test_hull_planes_rejects_non_convex(self):
        # an L-shaped prism (two boxes sharing a face) is not one convex body
        tris = box(0, 0, 0, 2, 1, 1) + box(0, 1, 0, 1, 2, 1)
        self.assertIsNone(CR.hull_planes(np.asarray(tris, np.float64)))

    def test_buried_floors_under_a_container(self):
        # a 2.6 m tall closed box (a shipping container's UCX hull) on an open floor: its sides wall in a
        # standable sheet of floor that Unreal treats as solid
        floor = quad(0, 0, 6, 8, 0.0)
        hull = box(-1.2, -3.0, 0.0, 1.2, 3.0, 2.6)                       # hull in the prop's own frame
        pos = np.array([3.0, 4.0, 0.0])
        f = field(floor + [[tuple(np.asarray(v) + pos) for v in t] for t in hull], size=(6.0, 8.0, 4.0))
        inside = f.snap(3.0, 4.0, 0.5, reach=0.2, dz=0.3)
        self.assertGreaterEqual(inside, 0)                               # before: a closed 'room' under the hull

        class Stub:
            props = [("SM_Box", np.array([[pos[0] * 100.0, -pos[1] * 100.0, 0.0, 0.0, 1.0]]))]

            def hull_parts(self, name):
                return [CR.hull_planes(np.asarray(hull, np.float64))]
        buried = CR.World.buried_floors(Stub(), f, np.array([0.0, 0.0, -0.5]))
        self.assertTrue(buried[inside])
        outside = f.snap(0.5, 4.0, 0.5, reach=0.2, dz=0.3)
        self.assertGreaterEqual(outside, 0)
        self.assertFalse(buried[outside])


if __name__ == "__main__":
    unittest.main()
