"""Pipeline side of the water / waterways upgrade (Tools/dai/water.py, terrain.py helpers, the generated data).

Pure numpy for the wave model and the committed data; the terrain helpers need scipy and are skipped without it
(CI installs numpy + pillow only). The engine side has its own suite: test_water_engine.py.

    python -m unittest Tools.tests.test_water_pipeline -v
"""

import base64
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Tools"))

from dai import config as C  # noqa: E402
from dai import water as W  # noqa: E402

DATA = REPO / "DuelAcademyIsland" / "SourceAssets" / "Data"
MESHES = REPO / "DuelAcademyIsland" / "SourceAssets" / "Meshes"
TEXTURES = REPO / "DuelAcademyIsland" / "SourceAssets" / "Textures"

try:
    import scipy  # noqa: F401
    HAVE_SCIPY = True
except ImportError:
    HAVE_SCIPY = False


class WaveModelTests(unittest.TestCase):
    def test_sets_fit_the_material_and_the_meshes(self):
        for waves, cell in ((W.OCEAN_WAVES, W.OCEAN_CELL), (W.LAKE_WAVES, W.LAKE_CELL)):
            self.assertLessEqual(len(waves), W.MAX_WAVES)
            for w in waves:
                self.assertAlmostEqual(math.hypot(*w["dir"]), 1.0, places=9)
                self.assertGreaterEqual(w["wavelength"], 4.0 * cell)       # a mesh must be able to carry it
                self.assertTrue(0.0 <= w["steepness"] <= 1.0)
            self.assertLess(W.max_fold(waves), 0.6)                         # no loops in the crests

    def test_height_at_inverts_the_horizontal_displacement(self):
        rng = np.random.default_rng(3)
        x, y = rng.uniform(-900, 900, 200), rng.uniform(-900, 900, 200)
        for waves in (W.OCEAN_WAVES, W.LAKE_WAVES):
            for t in (0.0, 7.3, 123.4):
                dx, dy, dz = W.offset(waves, x, y, t)
                # the surface point that rests at (x, y) is now at (x + dx, y + dy, dz)
                h = W.height_at(waves, x + dx, y + dy, t)
                self.assertLess(float(np.abs(h - dz).max()), 2e-3)

    def test_mask_scales_every_term(self):
        x, y = np.array([10.0, -40.0]), np.array([5.0, 77.0])
        full = W.offset(W.OCEAN_WAVES, x, y, 3.0)
        half = W.offset(W.OCEAN_WAVES, x, y, 3.0, m=0.5)
        for a, b in zip(full, half):
            np.testing.assert_allclose(b, 0.5 * a, atol=1e-12)
        nx, ny, nz = W.normal(W.OCEAN_WAVES, x, y, 3.0, m=0.0)
        np.testing.assert_allclose([nx, ny, nz], [[0, 0], [0, 0], [1, 1]], atol=1e-12)

    def test_mask_lookup_is_bilinear_and_clamped(self):
        n = 8
        mask = (np.arange(n * n, dtype=np.float64).reshape(n, n) * 3).astype(np.uint8)
        cell = C.WORLD_SIZE / n
        # texel centres return the texel
        x = -C.HALF + (np.arange(n) + 0.5) * cell
        y = C.HALF - (np.arange(n) + 0.5) * cell
        got = W.sample_mask(mask, x[None, :], y[:, None])
        np.testing.assert_allclose(got, mask / 255.0, atol=1e-12)
        # half way between two texels: their mean; outside the map: the edge texel
        self.assertAlmostEqual(float(W.sample_mask(mask, x[2] + cell / 2, y[3])), (mask[3, 2] + mask[3, 3]) / 510.0)
        self.assertAlmostEqual(float(W.sample_mask(mask, -9e9, 9e9)), mask[0, 0] / 255.0)


class WaterJsonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((DATA / "water.json").read_text(encoding="utf-8"))

    def test_wave_sets_are_the_pipeline_sets_in_unreal_units(self):
        self.assertEqual(self.doc["ocean"]["waves"], W.ue_waves(W.OCEAN_WAVES))
        self.assertEqual(self.doc["lake"]["waves"], W.ue_waves(W.LAKE_WAVES))
        for src, ue in zip(W.OCEAN_WAVES, self.doc["ocean"]["waves"]):
            self.assertAlmostEqual(ue["dir"][1], -src["dir"][1], places=5)      # Unreal's Y points south
            self.assertAlmostEqual(ue["wavelength"], src["wavelength"] * 100.0, places=1)
        self.assertEqual(self.doc["lake"]["level"], C.LAKE_LEVEL * 100.0)

    def test_wave_mask_bytes_are_the_texture(self):
        from PIL import Image
        m = self.doc["wave_mask"]
        raw = np.frombuffer(base64.b64decode(m["data"]), np.uint8)
        self.assertEqual(raw.size, m["size"] * m["size"])
        with Image.open(TEXTURES / (m["texture"] + ".png")) as img:
            red = np.asarray(img.convert("RGB"))[..., 0]
        np.testing.assert_array_equal(raw.reshape(m["size"], m["size"]), red)
        grid = raw.reshape(m["size"], m["size"])
        self.assertEqual(int(grid[0].max()), 0)                 # flat at the edge of the domain ...
        self.assertEqual(int(grid[:, -1].max()), 0)
        self.assertGreater(int(grid.max()), 200)                # ... a real sea in between
        self.assertEqual(int(grid[m["size"] // 2, m["size"] // 2]), 0)      # and no waves on the academy lawn

    def test_rivers_run_downhill_to_the_sea(self):
        self.assertGreaterEqual(len(self.doc["rivers"]), 2)
        for r in self.doc["rivers"]:
            p = np.asarray(r["points"], np.float64)
            self.assertEqual(p.shape[1], 4)
            self.assertTrue((np.diff(p[:, 2]) <= 1e-6).all(), r["id"])          # water never runs uphill
            self.assertLess(p[-1, 2], 150.0, r["id"])                           # it ends at sea level
            self.assertTrue((p[:, 3] > 100.0).all(), r["id"])
            step = np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1]))
            self.assertLess(float(step.max()), 800.0, r["id"])


class LayoutWaterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((DATA / "layout.json").read_text(encoding="utf-8"))
        cls.manifest = {e["name"]: e for e in json.loads((DATA / "assets.json").read_text(encoding="utf-8"))}
        cls.palette = json.loads((DATA / "materials.json").read_text(encoding="utf-8"))

    def test_every_water_and_bridge_mesh_is_exported_and_listed(self):
        names = [s["mesh"] for s in self.layout["static"] if s.get("group") in ("water", "bridges", "waterside")]
        self.assertIn("SM_Ocean", names)
        self.assertTrue(any(n.startswith("SM_River_") for n in names))
        self.assertGreaterEqual(sum(n.startswith("SM_Bridge_") and not n.endswith("_NoCol") for n in names), 4)
        for s in self.layout["static"]:
            if s.get("group") in ("water", "bridges", "waterside"):
                self.assertIn(s["mesh"], self.manifest, s["mesh"])
                self.assertTrue((MESHES / s["folder"] / (s["mesh"] + ".fbx")).is_file(), s["mesh"])

    def test_bridges_are_walkable_and_the_water_is_not_solid(self):
        for s in self.layout["static"]:
            if s.get("group") == "water":
                self.assertEqual(s["collision"], "none", s["mesh"])
            if s.get("group") == "bridges" and not s["mesh"].endswith("_NoCol"):
                self.assertEqual(s["collision"], "complex", s["mesh"])

    def test_fountain_jets_carry_a_trajectory(self):
        jets = [e for e in self.layout["emitters"] if e["kind"] == "jet"]
        self.assertGreaterEqual(len(jets), 20)
        for e in jets:
            self.assertEqual(len(e["vel"]), 3)
            self.assertGreater(e["vel"][2], 100.0)              # thrown upwards, cm/s
            self.assertLess(e["floor"], e["loc"][2] + 1.0)      # and lands at or below the nozzle

    def test_spinners_turn_a_mesh_that_is_not_also_a_static(self):
        statics = {s["mesh"] for s in self.layout["static"]}
        spinners = [s for s in self.layout["specials"] if s["kind"] == "spinner"]
        self.assertGreaterEqual(len(spinners), 1)
        for s in spinners:
            self.assertIn(s["props"]["mesh"], self.manifest)
            self.assertNotIn(s["props"]["mesh"], statics)
            self.assertIn(s["props"]["axis"], ("x", "y", "z"))

    def test_villages_are_places_on_the_map(self):
        zones = {z["id"]: z for z in self.layout["zones"]}
        for key in C.VILLAGES:
            self.assertIn(key, zones)
            self.assertTrue(any(s.get("group") == key for s in self.layout["static"]), key)
            self.assertTrue(any(n.get("group") == key for n in self.layout["npcs"]), key)

    def test_water_palette_kinds(self):
        self.assertEqual(self.palette["M_Ocean"]["kind"], "water")
        self.assertEqual(self.palette["M_Ocean"]["waves"], "ocean")
        self.assertEqual(self.palette["M_LakeWater"]["waves"], "lake")
        self.assertEqual(self.palette["M_River"]["kind"], "river")
        self.assertEqual(self.palette["M_FountainWater"]["kind"], "pool")


@unittest.skipUnless(HAVE_SCIPY, "terrain helpers need scipy")
class RoadProfileTests(unittest.TestCase):
    def setUp(self):
        from dai import terrain
        self.T = terrain

    def test_fixed_ends_and_the_grade_limit_hold(self):
        rng = np.random.default_rng(11)
        for trial in range(20):
            n = int(rng.integers(40, 400))
            raw = np.cumsum(rng.normal(0.0, 0.5, n)) + 30.0          # rough ground, pitches far over the limit
            z0, z1 = raw[0] + rng.uniform(-3, 3), raw[-1] + rng.uniform(-3, 3)
            prof, used = self.T.solve_profile(raw, 2.0, 0.09, z0=z0, z1=z1, floor=-1e9)
            self.assertAlmostEqual(prof[0], z0, places=9)
            self.assertAlmostEqual(prof[-1], z1, places=9)
            self.assertLessEqual(float(np.abs(np.diff(prof)).max()) / 2.0, used + 1e-9)
            if abs(z1 - z0) / (2.0 * (n - 1)) < 0.085:
                self.assertAlmostEqual(used, 0.09)                    # the limit is only raised when it must be

    def test_a_road_arriving_below_its_pad_ramps_up_instead_of_hitting_a_wall(self):
        raw = np.full(200, 20.0)
        raw[-1] = 34.0                                               # the plaza, 14 m above the approach
        prof, used = self.T.solve_profile(raw, 2.0, 0.09, z0=20.0, z1=34.0)
        self.assertAlmostEqual(used, 0.09)
        self.assertLessEqual(float(np.abs(np.diff(prof)).max()) / 2.0, 0.09 + 1e-9)
        self.assertGreater(float(prof[-40]), 24.0)                   # the climb starts well before the end

    def test_bridge_clearance_wins_over_the_ground(self):
        raw = np.full(120, 10.0)
        lower = np.full(120, -1e9)
        lower[55:66] = 13.0
        prof, _used = self.T.solve_profile(raw, 2.0, 0.09, z0=10.0, z1=10.0, lower=lower)
        self.assertTrue((prof[55:66] >= 13.0 - 1e-9).all())
        self.assertLessEqual(float(np.abs(np.diff(prof)).max()) / 2.0, 0.09 + 1e-9)

    def test_crossings(self):
        a = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
        b = [(15.0, -5.0), (15.0, 5.0)]
        hits = self.T.segment_crossings(a, b)
        self.assertEqual(len(hits), 1)
        i, t, j, u, x, y = hits[0]
        self.assertEqual((i, j), (1, 0))
        self.assertAlmostEqual(x, 15.0)
        self.assertAlmostEqual(y, 0.0)
        self.assertEqual(self.T.segment_crossings(a, [(30.0, -5.0), (30.0, 5.0)]), [])


if __name__ == "__main__":
    unittest.main()
