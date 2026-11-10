"""Water: the ocean clipmap, the baked water field, caustics and the wave HLSL (Tools/dai/water.py,
DuelAcademyIsland/Content/Python/duel_academy/water_hlsl.py). Run with:

    python -m unittest discover -s Tools/tests -v
"""

from __future__ import annotations

import math
import re
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Tools"))
sys.path.insert(0, str(REPO / "DuelAcademyIsland" / "Content" / "Python"))

from dai import water  # noqa: E402
from duel_academy import water_hlsl  # noqa: E402

try:
    import scipy  # noqa: F401
    HAVE_SCIPY = True
except ImportError:          # CI installs numpy + Pillow only
    HAVE_SCIPY = False


class ClipmapTest(unittest.TestCase):
    def test_small_clipmap_is_watertight_and_upward(self):
        v, t = water.clipmap(core_cells=8, spacing=2.0, levels=3)
        rim = v[:, 0].max()
        self.assertEqual(rim, 8 / 2 * 2.0 * 2 ** 3)
        edges = water.boundary_edges(t)
        on_rim = np.isclose(np.abs(v[edges][:, :, :2]).max(axis=2), rim).all(axis=1)
        self.assertTrue(on_rim.all(), "open edges inside the sheet = cracks between rings")
        a = v[t]
        cross = (a[:, 1, 0] - a[:, 0, 0]) * (a[:, 2, 1] - a[:, 0, 1]) - (a[:, 1, 1] - a[:, 0, 1]) * (a[:, 2, 0] - a[:, 0, 0])
        self.assertTrue((cross > 0).all(), "every triangle faces up (CCW seen from above)")
        self.assertAlmostEqual(cross.sum() / 2.0, (2 * rim) ** 2)
        self.assertEqual(len(np.unique(v[:, :2], axis=0)), len(v), "shared ring borders are merged")

    def test_shipped_clipmap_snaps_on_its_ring_grid(self):
        v, t = water.clipmap()
        # ADAOcean moves the mesh in OCEAN_SNAP steps: every ring up to the one at the snap spacing keeps its
        # vertices on the world grid (the coarser rings carry no displacement by then)
        self.assertEqual(water.OCEAN_SNAP % water.OCEAN_CORE_SPACING, 0.0)
        self.assertLess(len(t), 80000)
        self.assertGreater(v[:, 0].max(), 20000.0)

    def test_png16_roundtrip_header(self):
        a = np.zeros((3, 5, 4), np.float32)
        a[1, 2] = (1.0, 0.5, 0.25, 1.0)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.png"
            water.save_png16(p, a)
            data = p.read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        w, h, depth, ctype = struct.unpack(">IIBB", data[16:26])
        self.assertEqual((w, h, depth, ctype), (5, 3, 16, 6))
        idat = data[data.index(b"IDAT") + 4:data.index(b"IEND") - 8]
        raw = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(3, 1 + 5 * 8)
        px = raw[1, 1 + 2 * 8:1 + 3 * 8].view(">u2")
        self.assertEqual(list(px), [65535, 32768, 16384, 65535])


@unittest.skipUnless(HAVE_SCIPY, "scipy not installed")
class FieldTest(unittest.TestCase):
    def test_field_encodes_depth_shore_and_lake(self):
        n = 129
        world = 1280.0
        y, x = np.mgrid[0:n, 0:n]
        r = np.hypot(x - 64, y - 64) * world / (n - 1)
        h = 40.0 - r * 0.2                          # a cone: island top 40 m, shore at r = 200 m
        lake = (np.hypot(x - 64, y - 54) * world / (n - 1)) < 30.0
        h[lake] = 25.0                               # a basin up the slope, filled to 30 m
        f = water.water_field(h, world, 30.0, (0.0, 100.0), (40.0, 40.0), 0.0, n=128)
        self.assertEqual(f.shape, (128, 128, 4))
        depth = f[..., 0] * water.FIELD_DEPTH
        shore = f[..., 1] * (water.SHORE_MAX - water.SHORE_MIN) + water.SHORE_MIN
        self.assertEqual(depth[64, 64], 0.0)                       # dry island top
        self.assertGreater(depth[2, 2], 20.0)                       # open sea in the corner
        self.assertLess(shore[64, 64], 0.0)                         # on land: negative distance
        self.assertGreater(shore[2, 2], 100.0)
        self.assertEqual(f[54, 64, 3], 1.0)                         # lake mask
        self.assertAlmostEqual(float(depth[54, 64]), 5.0, places=3)  # lake level 30 - bed 25
        self.assertEqual(f[54, 64, 2], 1.0)                         # lake counts as exposed
        self.assertTrue(((f >= 0) & (f <= 1)).all())

    def test_caustics_tile(self):
        c = water.caustics(n=64, photons=2)
        self.assertEqual(c.shape, (64, 64))
        self.assertGreater(c.max(), 0.9)                            # focal lines saturate
        self.assertLess(np.abs(c[0] - c[-1]).mean(), 0.25)          # wraps (periodic ripples)


class WaveHlslTest(unittest.TestCase):
    def _check(self, code, inputs, outputs=()):
        self.assertEqual(code.count("{"), code.count("}"))
        self.assertTrue(code.rstrip().endswith(";"))
        self.assertIn("return", code)
        used = set(re.findall(r"\b[A-Z][A-Za-z0-9]*\b", code))
        for name in inputs:
            self.assertIn(name, used, f"input {name} unused")
        for name in outputs:
            self.assertRegex(code, rf"\b{name}\s*=")
        for line in code.splitlines():
            s = line.split("//")[0].strip()
            if s and not s.endswith(("{", "}")):
                self.assertTrue(s.endswith(";"), line)

    def test_codes_are_well_formed(self):
        common = [n for n in water_hlsl._COMMON_IN]
        self._check(water_hlsl.wpo_code(), common)
        self._check(water_hlsl.normal_code(), [n for n in common if n not in ("Spacing", "Clip")], ("Crest",))
        self._check(water_hlsl.foam_code(), water_hlsl.FOAM_IN)
        self._check(water_hlsl.detail_uv_code(), water_hlsl.DETAIL_IN, ("UV2", "UV3"))
        self.assertEqual(water_hlsl.wpo_code().count("float th ="), len(water_hlsl.WAVES))

    def test_field_encoding_matches_the_baker(self):
        self.assertEqual(water_hlsl.FIELD_DEPTH, water.FIELD_DEPTH)
        self.assertEqual((water_hlsl.SHORE_MIN, water_hlsl.SHORE_MAX), (water.SHORE_MIN, water.SHORE_MAX))

    def test_sea_never_folds_and_has_a_few_whitecaps(self):
        x, y = np.meshgrid(np.linspace(0, 300, 301), np.linspace(0, 300, 301))
        o, n, crest = water_hlsl.gerstner(x, y, 4.0)
        self.assertGreater(crest.min(), 0.0, "Jacobian <= 0 means the surface loops over itself")
        for d in (0.5, 1.6, 4.0):     # shoaling sharpens the waves, but never past folding
            self.assertGreater(water_hlsl.gerstner(x, y, 4.0, depth=d, height=1.6)[2].min(), 0.0, d)
        caps = (crest < 0.75).mean()
        self.assertTrue(0.002 < caps < 0.08, caps)
        self.assertTrue(0.4 < o[..., 2].max() < 1.2)
        self.assertGreater(n[..., 2].min(), math.cos(math.radians(25)))

    def test_shallows_and_lake_scale_the_waves(self):
        x, y = np.meshgrid(np.linspace(0, 100, 51), np.linspace(0, 100, 51))
        deep = water_hlsl.gerstner(x, y, 2.0)[0][..., 2].std()
        shallow = water_hlsl.gerstner(x, y, 2.0, depth=0.25)[0][..., 2].std()
        shoaling = water_hlsl.gerstner(x, y, 2.0, depth=3.0)[0][..., 2].std()
        self.assertAlmostEqual(shoaling, deep, delta=deep * 0.05)   # the swell keeps its height to ~1.6 m
        lake = water_hlsl.gerstner(x, y, 2.0, height=0.2, length=0.22)[0][..., 2].std()
        self.assertLess(shallow, deep * 0.2)
        self.assertLess(lake, deep * 0.1)

    def test_gerstner_normal_matches_the_displaced_surface(self):
        # the analytic normal must agree with the finite-difference normal of the displaced sheet
        s = np.linspace(0.0, 4.0, 201)
        x, y = np.meshgrid(s, s)
        for wind in (0.0, 35.0):
            o, n, _ = water_hlsl.gerstner(x, y, 1.3, wind=wind, height=1.6)
            P = np.stack([x + o[..., 0], y + o[..., 1], o[..., 2]], -1)
            du = P[1:-1, 2:] - P[1:-1, :-2]
            dv = P[2:, 1:-1] - P[:-2, 1:-1]
            fd = np.cross(du, dv)
            fd /= np.linalg.norm(fd, axis=-1, keepdims=True)
            dot = (fd * n[1:-1, 1:-1]).sum(-1)
            self.assertGreater(dot.min(), 0.9995, f"wind {wind}")


if __name__ == "__main__":
    unittest.main()
