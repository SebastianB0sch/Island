"""Where the land meets the water.

  * the lake has arms (config.LAKE_INLETS): the girls' dorm jetty stands in one instead of a dry hollow 70 m
    from the shore; the terrain cuts it (terrain.inlet_q, merged into the lake's q), the lake mesh, the water
    raster and the engine's water query (water.json "inlets", added like the rivers by level.py) all see it;
  * the harbour basin is dredged flat right up to the quay wall (no shelf of the quay's apron in front of it);
  * every boat floats: at the water's surface, over water deep enough for its hull (alignment_check BOATS);
  * a road turns into the stretch it is carried on by on a curve, not a kink (strips.round_joints).

    python -m unittest Tools.tests.test_waterside -v
"""

import json
import math
import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Tools"))
sys.path.insert(0, str(REPO / "Tools" / "tests"))

import numpy as np  # noqa: E402

from dai import config as C  # noqa: E402
from dai import shoreline as SH  # noqa: E402
from dai import strips  # noqa: E402

try:
    from dai import terrain as T  # noqa: E402 - needs scipy
except ImportError:
    T = None

DATA = REPO / "DuelAcademyIsland" / "SourceAssets" / "Data"
CACHE = REPO / "Tools" / ".cache" / "terrain_info.json"


def _constants(module, *names):
    """Module-level constants of a location module (Tools/dai/assets/<module>.py), read without importing it
    (the asset modules need Blender)."""
    import ast
    tree = ast.parse((REPO / "Tools" / "dai" / "assets" / f"{module}.py").read_text(encoding="utf-8"))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id in names:
                    found[tgt.id] = ast.literal_eval(node.value)
                elif isinstance(tgt, ast.Tuple):
                    for i, el in enumerate(tgt.elts):
                        if isinstance(el, ast.Name) and el.id in names:
                            found[el.id] = ast.literal_eval(node.value.elts[i])
    return types.SimpleNamespace(**found)


def _dist_to_line(p, pts):
    best = math.inf
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        t = min(max(((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy), 0.0), 1.0)
        best = min(best, math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy))
    return best


class InletFieldTests(unittest.TestCase):
    ARM = [dict(id="a", name="A", depth=2.0, bank=40.0, pts=[(0.0, 0.0), (100.0, 0.0)], half=[10.0, 20.0],
                landing=None)]

    def test_q_is_zero_on_the_middle_line_one_at_the_edge_and_grows_with_the_bank(self):
        q, depth = SH.inlet_q(np.array([50.0, 50.0, 50.0, 50.0]), np.array([0.0, 15.0, 25.0, 55.0]), self.ARM)
        np.testing.assert_allclose(q, [0.0, 1.0, 1.25, 2.0], atol=1e-9)        # half width 15 m half-way along
        np.testing.assert_allclose(depth, 2.0)
        q, _ = SH.inlet_q(np.array([-10.0]), np.array([0.0]), self.ARM)       # round head: 10 m past the end
        self.assertAlmostEqual(float(q[0]), 1.0)

    def test_no_arms_no_water_and_any_shape(self):
        q, depth = SH.inlet_q(np.zeros((3, 4)), np.zeros((3, 4)), [])
        self.assertEqual(q.shape, (3, 4))
        self.assertTrue(np.isinf(q).all())
        q, _ = SH.inlet_q(np.zeros((2, 2)), np.zeros((2, 2)), self.ARM)
        self.assertEqual(q.shape, (2, 2))

    def test_lake_q_is_the_ellipse_or_an_arm(self):
        self.assertAlmostEqual(float(SH.lake_q(*C.LAKE_CENTER)), 0.0)
        for rec in C.lake_inlets():
            x, y = rec["pts"][1]
            self.assertLess(float(SH.lake_q(x, y)), 0.2, rec["id"])
            a = math.radians(C.LAKE_ROT)
            dx, dy = x - C.LAKE_CENTER[0], y - C.LAKE_CENTER[1]
            ell = math.hypot((dx * math.cos(a) + dy * math.sin(a)) / C.LAKE_RADII[0],
                             (-dx * math.sin(a) + dy * math.cos(a)) / C.LAKE_RADII[1])
            self.assertGreater(ell, 1.2, "the arm reaches beyond the ellipse - else it is not needed")
            # it opens into the lake proper
            ex, ey = rec["pts"][-1]
            dx, dy = ex - C.LAKE_CENTER[0], ey - C.LAKE_CENTER[1]
            self.assertLess(math.hypot((dx * math.cos(a) + dy * math.sin(a)) / C.LAKE_RADII[0],
                                       (-dx * math.sin(a) + dy * math.cos(a)) / C.LAKE_RADII[1]), 0.9, rec["id"])


class GirlsJettyTests(unittest.TestCase):
    """The jetty, its arm of the lake and the walk to it agree with each other."""

    @classmethod
    def setUpClass(cls):
        cls.O = O = _constants("obelisk", "JETTY_OFFSET", "JETTY_LENGTH", "JETTY_DECK_Z", "JETTY_LAND_Z", "LAKE_Z")
        cls.arm = next(r for r in C.lake_inlets() if r["id"] == "girls_jetty")
        cls.pad = 33.0                       # terrain.pad_specs()["obelisk_girls"]["h"] (checked where scipy is)

    def test_the_pad_height_used_here_is_the_terrains(self):
        if T is None:
            self.skipTest("needs scipy")
        self.assertEqual(T.pad_specs()["obelisk_girls"]["h"], self.pad)

    def jetty(self, lx, ly):
        ox, oy = self.O.JETTY_OFFSET
        return C.world_point(("obelisk_girls", ox + lx, oy + ly))

    def test_the_deck_and_its_boats_are_in_the_arm(self):
        arm, O = self.arm, self.O
        for ly in np.arange(0.0, -O.JETTY_LENGTH - 0.01, -2.5):
            p = self.jetty(0.0, ly)
            self.assertLess(float(SH.inlet_q(np.array([p[0]]), np.array([p[1]]))[0][0]), 1.0, ly)
        for bx in (-2.9, 2.9):
            for by in (-10.2, -16.2):
                p = self.jetty(bx, by)
                d = _dist_to_line(p, arm["pts"])
                self.assertLess(d + 2.0, 12.0, "a boat keeps 2 m of water to the bank")

    def test_the_bed_is_under_the_piles_and_the_landing_on_the_bank(self):
        arm, O = self.arm, self.O
        bed = C.LAKE_LEVEL - 0.6 - arm["depth"]                  # the arm's middle line
        self.assertGreaterEqual(bed, self.pad - 6.0, "the piles (down to local -6) reach the bed")
        self.assertLess(bed, self.pad + O.JETTY_DECK_Z - 2.0)
        self.assertAlmostEqual(self.pad + O.LAKE_Z, C.LAKE_LEVEL, places=6)     # the boats sit on the lake
        (lx, ly), z = arm["landing"]
        self.assertAlmostEqual(z, self.pad + O.JETTY_LAND_Z, places=6)
        land = self.jetty(0.0, 9.0)                                            # the shore end of the landing
        self.assertLess(math.hypot(land[0] - lx, land[1] - ly), 0.05)
        q = float(SH.inlet_q(np.array([lx]), np.array([ly]))[0][0])
        self.assertGreater(q, 1.1, "the landing is on dry ground")

    def test_the_garden_walk_runs_on_to_the_landing(self):
        p = next(p for p in C.PATHS if p["id"] == "girls_jetty")
        (lx, ly), _z = self.arm["landing"]
        self.assertLess(math.hypot(p["pts"][-1][0] - lx, p["pts"][-1][1] - ly), 0.05)
        walk_end = C.world_point(("obelisk_girls", 0.0, -62.5))          # obelisk.py: slab(..., -62.5, ...)
        self.assertLess(math.hypot(p["pts"][0][0] - walk_end[0], p["pts"][0][1] - walk_end[1]), 0.05)
        ext = C.path_extension("girls_jetty")
        self.assertIn("start_edge", ext)
        self.assertIn("end_edge", ext)
        self.assertEqual(self.O.JETTY_OFFSET[0], 0.0, "the jetty stands on the axis of the garden walk")


class HarbourTests(unittest.TestCase):
    def test_the_basin_reaches_the_quay_wall_and_the_piles_reach_its_bed(self):
        H = _constants("harbor", "QY", "WALL_BOT", "BED")
        hx, hy, hhx, hhy = C.HARBOR_RECT
        self.assertEqual(C.HARBOR_BASIN[3], hy - hhy, "dredged right up to the quay face")
        z0 = C.LOCATIONS["harbor"]["height"]
        self.assertAlmostEqual(hy - hhy, C.LOCATIONS["harbor"]["pos"][1] + H.QY)
        self.assertLessEqual(z0 + H.WALL_BOT, C.HARBOR_DEPTH, "the quay wall stands on (in) the bed")
        self.assertAlmostEqual(z0 + H.BED, C.HARBOR_DEPTH, msg="the pier's piles stand on the bed")


class RoundJointTests(unittest.TestCase):
    def test_a_corner_becomes_a_curve_tangent_to_both_legs(self):
        line = strips.resample([(0.0, 0.0), (40.0, 0.0), (40.0, 40.0)], 2.0)
        out = strips.round_joints(line, [20], radius=12.0)
        self.assertEqual(out[0], line[0])
        self.assertEqual(out[-1], line[-1])
        for p in out:                                    # untouched far from the corner, inside it near it
            if p[0] <= 28.0 - 1e-6:
                self.assertAlmostEqual(p[1], 0.0)
            if p[1] >= 12.0 + 1e-6:
                self.assertAlmostEqual(p[0], 40.0)
        self.assertNotIn((40.0, 0.0), out)
        ang = [math.atan2(b[1] - a[1], b[0] - a[0]) for a, b in zip(out, out[1:]) if a != b]
        turn = max(abs((b - a + math.pi) % (2 * math.pi) - math.pi) for a, b in zip(ang, ang[1:]))
        self.assertLess(math.degrees(turn), 12.0)
        self.assertGreater(min(math.hypot(x - 40.0, y) for x, y in out), 3.0)

    def test_close_corners_do_not_overlap_and_ends_and_straights_stay(self):
        line = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (20.0, 4.0)]
        out = strips.round_joints(line, [1, 2], radius=12.0)
        xs = [p[0] for p in out]
        self.assertEqual(xs, sorted(xs), "the line still runs one way")
        self.assertEqual(strips.round_joints(line, [], 12.0), line)
        self.assertEqual(strips.round_joints(line, [0, 3], 12.0), line)
        straight = strips.resample([(0.0, 0.0), (10.0, 0.0), (30.0, 0.0)], 2.0)
        for (x, y) in strips.round_joints(straight, [5], 12.0):
            self.assertAlmostEqual(y, 0.0)

    def test_extended_line_marks_where_the_path_meets_its_extension(self):
        own = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
        pts, joints = strips.extended_line(own, dict(start=[(0.0, -20.0)], end=[(20.0, 10.0), (30.0, 10.0)]))
        self.assertEqual(pts, [(0.0, -20.0)] + own + [(20.0, 10.0), (30.0, 10.0)])
        self.assertEqual([pts[j] for j in joints], [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0)])
        pts, joints = strips.extended_line(own, dict(start=[(0.0, -20.0)]), step=2.0)
        self.assertEqual(pts[joints[0]], (0.0, 0.0))
        self.assertEqual(len(pts), 10 + 3)


class WaterJsonTests(unittest.TestCase):
    @unittest.skipUnless((DATA / "water.json").exists(), "generated water.json not present")
    def test_the_arms_are_in_water_json_at_the_lakes_level(self):
        data = json.loads((DATA / "water.json").read_text(encoding="utf-8"))
        arms = {a["id"]: a for a in data.get("inlets", [])}
        self.assertEqual(set(arms), {r["id"] for r in C.LAKE_INLETS})
        for rec in C.lake_inlets():
            pts = arms[rec["id"]]["points"]
            self.assertEqual(len(pts), len(rec["pts"]))
            for (x, y), hw, p in zip(rec["pts"], rec["half"], pts):
                self.assertEqual(p, [round(x * 100.0, 1), round(-y * 100.0, 1), C.LAKE_LEVEL * 100.0,
                                     round(hw * 100.0, 1)])

    def test_level_adds_the_arms_like_the_rivers(self):
        from test_water_engine import load_editor_module
        level = load_editor_module("level")
        calls = []

        class Manager:
            def clear_water_data(self):
                calls.append("clear")

            def set_wave_set(self, lake, packed):
                pass

            def set_wave_mask_base64(self, *a):
                return True

            def add_river(self, rid, packed):
                calls.append((rid, packed))

        data = dict(ocean={}, lake={}, rivers=[dict(id="r", points=[[0, 0, 100, 50], [10, 0, 90, 50]])],
                    inlets=[dict(id="arm", points=[[0, 100, 3000, 800], [0, 200, 3000, 900]])])
        placer = types.SimpleNamespace(ysign=-1.0, pack_waves=level.Placer.pack_waves,
                                       mirror_mask=level.Placer.mirror_mask)
        saved = level.C.load_json
        level.C.load_json = lambda name: data
        try:
            self.assertTrue(level.Placer.water(placer, Manager()))
        finally:
            level.C.load_json = saved
        self.assertEqual(calls[0], "clear")
        self.assertEqual(calls[2], ("arm", [0.0, -100.0, 3000.0, 800.0, 0.0, -200.0, 3000.0, 900.0]))


try:
    import bpy  # noqa: F401
    import scipy  # noqa: F401
    HAVE_PIPELINE = CACHE.exists()
except ImportError:
    HAVE_PIPELINE = False


@unittest.skipUnless(HAVE_PIPELINE, "needs Blender's bpy, scipy and a built terrain (Tools/.cache)")
class BuiltTerrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from dai import waterways
        cls.ground = T.load_cached()[0]
        cls.waterways = waterways

    def test_the_jetty_stands_in_water_over_its_bed(self):
        O = _constants("obelisk", "JETTY_OFFSET", "JETTY_LENGTH")
        pad = T.pad_specs()["obelisk_girls"]["h"]
        for ly in np.arange(-1.0, -O.JETTY_LENGTH - 0.01, -2.0):
            x, y = C.world_point(("obelisk_girls", O.JETTY_OFFSET[0], O.JETTY_OFFSET[1] + ly))
            g = float(self.ground(x, y))
            self.assertEqual(self.waterways.water_level(x, y), C.LAKE_LEVEL, ly)
            self.assertLess(g, C.LAKE_LEVEL - 1.0, ly)
            self.assertGreaterEqual(g, pad - 6.0 - 0.05, f"the piles reach the bed at {ly}")
        (lx, ly_), z = next(r for r in C.lake_inlets() if r["id"] == "girls_jetty")["landing"]
        self.assertAlmostEqual(float(self.ground(lx, ly_)), z - 0.06, delta=0.03)
        self.assertIsNone(self.waterways.water_level(lx, ly_))

    def test_the_water_in_front_of_the_quay_is_deep(self):
        hx, hy, hhx, hhy = C.HARBOR_RECT
        for x in np.arange(hx - hhx + 20.0, hx + hhx - 20.0, 10.0):
            if math.hypot(x - 221.0, 0.0) < 40.0:              # the breakwater's embankment starts at the quay
                continue
            self.assertLess(float(self.ground(x, hy - hhy - 3.0)), C.HARBOR_DEPTH + 1.0, x)
            self.assertGreater(float(self.ground(x, hy - hhy + 3.0)), 2.9, x)      # the quay itself stays put


if __name__ == "__main__":
    unittest.main()
