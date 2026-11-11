"""Alignment invariants that can be checked without Blender (the full audit is Tools/alignment_check.py).

  * terrain.MeshField is the surface of the exported terrain triangles: exact at the mesh vertices, planar
    inside each triangle, split along the diagonal terrain.mesh_diagonals picks;
  * the committed layout: every road / bridge / terrain-built mesh carries the geometry signature of its
    last export, bridges come in pairs with their roads cut around them.

    python -m unittest Tools.tests.test_alignment -v
"""

import json
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Tools"))

from dai import config as C  # noqa: E402

DATA = REPO / "DuelAcademyIsland" / "SourceAssets" / "Data"

try:
    import scipy  # noqa: F401
    from dai import terrain
    HAVE_TERRAIN = True
except ImportError:
    HAVE_TERRAIN = False


@unittest.skipUnless(HAVE_TERRAIN, "terrain helpers need scipy")
class MeshFieldTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(5)
        self.h = rng.normal(0.0, 3.0, (C.FIELD_RES, C.FIELD_RES)).astype(np.float32)
        self.mf = terrain.MeshField(self.h)
        self.sp = C.WORLD_SIZE / C.MESH_QUADS

    def test_exact_at_the_mesh_vertices(self):
        st = terrain.mesh_step()
        for r, c in ((0, 0), (17, 400), (503, 9), (C.MESH_QUADS - 1, C.MESH_QUADS - 1)):
            x, y = -C.HALF + c * self.sp, C.HALF - r * self.sp
            self.assertAlmostEqual(float(self.mf(x, y)), float(self.h[r * st, c * st]), places=4)

    def test_planar_inside_each_triangle_and_split_on_the_chosen_diagonal(self):
        st = terrain.mesh_step()
        hs = self.h[::st, ::st].astype(np.float64)
        diag = terrain.mesh_diagonals(hs)
        self.assertTrue(diag.any() and (~diag).any())          # both splits occur on rough ground
        for r, c in ((10, 10), (200, 731), (640, 77), (901, 500)):
            nw, ne, sw, se = hs[r, c], hs[r, c + 1], hs[r + 1, c], hs[r + 1, c + 1]
            x0, y0 = -C.HALF + c * self.sp, C.HALF - r * self.sp
            mid = float(self.mf(x0 + self.sp / 2, y0 - self.sp / 2))
            # the centre of the quad lies on the diagonal: the mean of the two corners it joins
            want = (nw + se) / 2 if diag[r, c] else (ne + sw) / 2
            self.assertAlmostEqual(mid, want, places=6)
            # the diagonal joins the pair of corners closer in height
            self.assertLessEqual(abs((nw - se) if diag[r, c] else (ne - sw)),
                                 abs((ne - sw) if diag[r, c] else (nw - se)) + 1e-12)
            # centroid of each triangle = mean of its three corners (planarity)
            if diag[r, c]:
                tris = ((nw, sw, se, (1 / 3, 2 / 3)), (nw, se, ne, (2 / 3, 1 / 3)))
            else:
                tris = ((nw, sw, ne, (1 / 3, 1 / 3)), (sw, se, ne, (2 / 3, 2 / 3)))
            for a, b, d, (u, v) in tris:
                got = float(self.mf(x0 + u * self.sp, y0 - v * self.sp))
                self.assertAlmostEqual(got, (a + b + d) / 3.0, places=6)

    def test_road_bed_is_wider_than_the_ribbon_by_a_mesh_cell(self):
        cell_diagonal = self.sp * 2 ** 0.5
        self.assertGreater(terrain.ROAD_FLAT_EXTRA["paved"], cell_diagonal)
        self.assertGreater(terrain.BRIDGE_ABUTMENT, cell_diagonal)


class CommittedLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((DATA / "layout.json").read_text(encoding="utf-8"))
        cls.manifest = {e["name"]: e for e in json.loads((DATA / "assets.json").read_text(encoding="utf-8"))}

    def test_location_meshes_carry_their_export_signature(self):
        missing = [n for n, e in self.manifest.items() if e.get("category") == "location" and not e.get("sig")]
        self.assertEqual(missing, [])

    def test_every_bridge_has_its_collision_mesh_and_its_road(self):
        statics = {s["mesh"]: s for s in self.layout["static"]}
        bridges = [n for n, s in statics.items() if s.get("group") == "bridges" and not n.endswith("_NoCol")]
        self.assertGreaterEqual(len(bridges), 4)
        for n in bridges:
            self.assertEqual(statics[n]["collision"], "complex")
            self.assertIn(n, self.manifest)
        # a paved road with a bridge keeps its ribbon mesh (cut around the deck, not dropped)
        self.assertIn("SM_Road_to_gym", statics)
        self.assertIn("SM_Bridge_ToGym", statics)


if __name__ == "__main__":
    unittest.main()
