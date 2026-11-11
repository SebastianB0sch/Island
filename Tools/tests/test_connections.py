"""Every house is joined to the road.

  * the island's paths are carried on across the grounds of the buildings they lead to
    (config.PATH_EXTENSIONS), to the entrance paving or the walk the building brings with it;
  * every cottage, the mill and the stilt huts of the villages get a footpath from their door to the lane,
    the road or the square (assets/village.py Village.footpaths), and the square has a paved link to its lane;
  * strips.py lays such a strip on the ground with a rim that disappears into it.

The full check - a walk on made ground from all 224 doors of the island to a road - is the ENTRANCES section
of Tools/alignment_check.py (it needs Blender's bpy).

    python -m unittest Tools.tests.test_connections -v
"""

import json
import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Tools"))

from dai import config as C  # noqa: E402
from dai import strips  # noqa: E402

DATA = REPO / "DuelAcademyIsland" / "SourceAssets" / "Data"
CACHE = REPO / "Tools" / ".cache" / "terrain_info.json"


class WaypointTests(unittest.TestCase):
    def test_a_local_waypoint_turns_with_its_location(self):
        for key, loc in C.LOCATIONS.items():
            ox, oy = loc["pos"]
            self.assertEqual(C.world_point((key, 0.0, 0.0)), (ox, oy))
            x, y = C.world_point((key, 3.0, -4.0))
            self.assertAlmostEqual(math.hypot(x - ox, y - oy), 5.0, places=9)
            a = math.radians(loc.get("yaw", 0.0))
            fx, fy = C.world_point((key, 0.0, -1.0))                  # a building's front is its local -Y
            self.assertAlmostEqual(fx - ox, math.sin(a), places=9)
            self.assertAlmostEqual(fy - oy, -math.cos(a), places=9)
        self.assertEqual(C.world_point((12.5, -3.0)), (12.5, -3.0))

    def test_extensions_name_real_paths_and_stay_on_the_grounds(self):
        ids = {p["id"]: p for p in C.PATHS}
        for pid in C.PATH_EXTENSIONS:
            self.assertIn(pid, ids)
            ext = C.path_extension(pid)
            self.assertTrue(ext["start"] or ext["end"], pid)
            pts = ids[pid]["pts"]
            for side, anchor in (("start", pts[0]), ("end", pts[-1])):
                way = ext[side] if side == "end" else ext[side][::-1]
                prev = anchor
                for q in way:                                          # short hops: the last stretch, no new road
                    self.assertLess(math.hypot(q[0] - prev[0], q[1] - prev[1]), 70.0, f"{pid} {side}")
                    prev = q
                edge = ext.get(side + "_edge")
                if edge:
                    # the slab's edge is centred on the last waypoint and square to the way in
                    last = ext[side][-1] if side == "end" else ext[side][0]
                    mid = ((edge[0][0] + edge[1][0]) / 2, (edge[0][1] + edge[1][1]) / 2)
                    self.assertLess(math.hypot(mid[0] - last[0], mid[1] - last[1]), 0.05, pid)
        self.assertEqual(C.path_extension("main_road"), dict(start=[], end=[]))


class StripTests(unittest.TestCase):
    @staticmethod
    def slope(x, y):
        return 10.0 + 0.08 * x - 0.03 * y

    @staticmethod
    def crease(x, y):
        return 5.0 + (0.25 * (x - 6.0) if x > 6.0 else 0.0)

    def test_resample_and_smooth_keep_the_ends(self):
        pts = [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0)]
        line = strips.resample(pts, 0.75)
        self.assertEqual((line[0], line[-1]), (pts[0], pts[-1]))
        self.assertTrue(all(math.hypot(b[0] - a[0], b[1] - a[1]) <= 0.75 + 1e-9 for a, b in zip(line, line[1:])))
        round_ = strips.smooth(pts, 2)
        self.assertEqual((round_[0], round_[-1]), (pts[0], pts[-1]))
        self.assertNotIn((4.0, 0.0), round_)                           # the corner is cut
        self.assertEqual(strips.smooth(pts[:2], 2), pts[:2])

    def test_a_strip_lies_on_the_ground_with_its_edges_in_it(self):
        rows = strips.drape(self.slope, [(0.0, 0.0), (9.0, 2.0), (14.0, 8.0)], 1.3)
        self.assertGreater(len(rows), 15)
        # the end comes down into the ground: the last section is all rim, one rim width after the last full one
        self.assertEqual([q[3] for q in rows[-1]], [0.0] * 5)
        self.assertAlmostEqual(math.hypot(rows[-1][2][0] - rows[-2][2][0], rows[-1][2][1] - rows[-2][2][1]), 0.36, places=6)
        self.assertEqual([q[3] for q in strips.drape(self.slope, [(0.0, 0.0), (5.0, 0.0)], 1.3, close_end=False)[-1]],
                         [0.0, 1.0, 1.0, 1.0, 0.0])
        for row in rows[:-1]:
            self.assertEqual([q[3] for q in row], [0.0, 1.0, 1.0, 1.0, 0.0])
        for row in rows:
            for x, y, z, cover in row:
                over = z - self.slope(x, y)
                if cover:
                    self.assertGreaterEqual(over, strips.LIFT - 1e-9)
                    self.assertLess(over, strips.LIFT + 0.03)
                else:
                    self.assertAlmostEqual(over, strips.RIM_LIFT, places=9)
            self.assertAlmostEqual(math.hypot(row[0][0] - row[4][0], row[0][1] - row[4][1]), 1.3, places=6)

    def test_more_sections_where_the_ground_bends(self):
        # an edge that crosses a crease at an angle must not bridge it
        line = [(0.0, 0.0), (12.0, 5.0)]
        plain = strips.drape(self.slope, line, 1.3)
        bent = strips.drape(self.crease, line, 1.3)
        self.assertGreater(len(bent), len(plain))
        for ra, rb in zip(bent, bent[1:]):
            for c in (0, 4):
                for t in (0.25, 0.5, 0.75):
                    x, y, z = (ra[c][k] + (rb[c][k] - ra[c][k]) * t for k in range(3))
                    self.assertLess(abs(z - self.crease(x, y) - strips.RIM_LIFT), 0.012)

    def test_build_writes_the_cover_as_vertex_colour(self):
        class Recorder:
            def __init__(self):
                self.quads = []

            def cquad(self, pts, colors, mat, smooth=False):
                self.quads.append((pts, colors, mat))
        rows = strips.drape(self.slope, [(0.0, 0.0), (3.0, 0.0)], 1.3, close_end=False)
        rec = Recorder()
        strips.build(rec, rows, "M_FootPath", lambda cover: (0.0, cover, 0.0, 1.0))
        self.assertEqual(len(rec.quads), (len(rows) - 1) * 4)
        for pts, colors, mat in rec.quads:
            self.assertEqual(mat, "M_FootPath")
            # counter-clockwise seen from above: the strip faces up
            area = sum(pts[i][0] * pts[(i + 1) % 4][1] - pts[(i + 1) % 4][0] * pts[i][1] for i in range(4))
            self.assertGreater(area, 0.0)
            self.assertTrue(all(c[0] == 0.0 and c[2] == 0.0 and c[1] in (0.0, 1.0) for c in colors))


class CommittedLayoutTests(unittest.TestCase):
    def test_every_village_has_its_paths_mesh(self):
        lay = json.loads((DATA / "layout.json").read_text(encoding="utf-8"))
        meshes = {s["mesh"]: s for s in lay["static"]}
        for name in ("SM_Millbrook_Paths_NoCol", "SM_WillowPond_Paths_NoCol", "SM_FishersCove_Paths_NoCol"):
            self.assertIn(name, meshes)
            self.assertEqual(meshes[name]["collision"], "none")
            folder = REPO / "DuelAcademyIsland" / "SourceAssets" / "Meshes" / meshes[name]["folder"]
            self.assertTrue((folder / (name + ".fbx")).exists(), name)
        palette = json.loads((DATA / "materials.json").read_text(encoding="utf-8"))
        self.assertEqual(palette["M_FootPath"]["kind"], "road")


try:
    import bpy  # noqa: F401
    import scipy  # noqa: F401
    HAVE_PIPELINE = CACHE.exists()
except ImportError:
    HAVE_PIPELINE = False


@unittest.skipUnless(HAVE_PIPELINE, "needs Blender's bpy, scipy and a built terrain (Tools/.cache)")
class VillageFootpathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from dai.assets import village
        cls.village = village
        cls.sets = {key: fn() for key, fn in village.PLACEMENTS.items()}

    def test_every_door_has_a_footpath_that_arrives_somewhere(self):
        V = self.village
        total = 0
        for key, aset in self.sets.items():
            paths = {f["name"]: f for f in aset.footpaths}
            self.assertGreaterEqual(len(aset.entrances), 6, key)
            for e in aset.entrances:
                self.assertIn(e["name"], paths, f"{key}: {e['name']} has no footpath")
                f = paths[e["name"]]
                total += 1
                self.assertIn(f["meets"], ("path", "square", "footpath"))
                self.assertLess(f["length"], 60.0, f"{e['name']}: a path to the door, not a detour")
                # it starts at the door ...
                self.assertLess(math.hypot(f["pts"][0][0] - e["pos"][0], f["pts"][0][1] - e["pos"][1]), 2.0)
                end = f["pts"][-1]
                if f["meets"] == "path":                              # ... and ends on the lane or the road
                    self.assertLess(V.path_gap(*end), 0.0, e["name"])
                elif f["meets"] == "footpath":                        # ... or on a path laid before it
                    others = [q for g in aset.footpaths if g is not f for q in strips.resample(g["pts"], 0.25)]
                    self.assertLess(min(math.hypot(q[0] - end[0], q[1] - end[1]) for q in others), 0.6, e["name"])
        self.assertGreaterEqual(total, 20)

    def test_the_square_is_paved_through_to_its_lane(self):
        aset = self.sets["willow_pond"]
        link = [f for f in aset.footpaths if f.get("paved")]
        self.assertEqual(len(link), 1)
        self.assertEqual(link[0]["meets"], "path")
        self.assertLess(self.village.path_gap(*link[0]["pts"][-1]), -0.4)     # in under the road's own paving
        self.assertTrue(any(f["meets"] == "square" for f in aset.footpaths))

    def test_footpaths_keep_clear_of_houses_and_water(self):
        V = self.village
        from dai import waterways as WW
        for key, aset in self.sets.items():
            mesh = next(mb for name, mb in aset.meshes.items() if name.endswith("_Paths_NoCol"))
            self.assertEqual(len(mesh.colors), len(mesh.verts))
            mats = set(mesh.face_mats)
            self.assertLessEqual(mats, {"M_FootPath", "M_RoadPaving"})
            for f in aset.footpaths:
                for (x, y) in strips.resample(f["pts"], 0.5)[6:]:          # (beyond the doorstep)
                    self.assertGreater(WW.clearance(x, y), 0.8, f"{f['name']} in the water")
                    self.assertGreater(V.H(x, y), 0.6, f"{f['name']} in the sea")


@unittest.skipUnless(HAVE_PIPELINE, "needs Blender's bpy, scipy and a built terrain (Tools/.cache)")
class ExtendedRoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from dai import layout, terrain
        cls.terrain = terrain
        cls.lay = layout.Layout(lambda *a, **k: None)
        cls.paths = {p["id"]: p for p in cls.lay.meta["paths"]}

    def test_the_built_terrain_knows_the_extensions(self):
        for pid in C.PATH_EXTENSIONS:
            want = C.path_extension(pid)
            got = self.paths[pid].get("extend") or {}
            for k, v in want.items():
                self.assertEqual([tuple(round(c, 6) for c in q) for q in got.get(k, [])],
                                 [tuple(round(c, 6) for c in q) for q in v], f"{pid} {k}: rebuild the terrain stage")

    def test_ribbons_run_to_the_last_waypoint_and_meet_the_walks_square(self):
        lay = self.lay
        slabs = 0
        for pid in C.PATH_EXTENSIONS:
            p = self.paths[pid]
            if not self.terrain.road_has_ribbon(p):
                continue
            ext = C.path_extension(pid)
            xs, ys, arc = lay.ribbon_line(p)
            if ext["start"]:
                self.assertAlmostEqual(math.hypot(xs[0] - ext["start"][0][0], ys[0] - ext["start"][0][1]), 0.0, places=6)
                self.assertLess(arc[0], -1.0)                           # arc length 0 stays at the path's own start
            if ext["end"]:
                self.assertAlmostEqual(math.hypot(xs[-1] - ext["end"][-1][0], ys[-1] - ext["end"][-1][1]), 0.0, places=6)
            _arc, runs = lay.road_runs(p)
            sections = lay.ribbon_sections(p)
            if ext.get("end_edge"):
                slabs += 1
                self.assertEqual(runs[-1][5], "slab")
                row = sections[-1][-1][1]
                (ax, ay), (bx, by) = ext["end_edge"]
                d = math.hypot(bx - ax, by - ay)
                for x, y, z, cover in row:                             # on the slab's edge line, paved across
                    off = abs((x - ax) * (by - ay) - (y - ay) * (bx - ax)) / d
                    self.assertLess(off, 1e-6)
                    self.assertEqual(cover, 1.0)
                    self.assertAlmostEqual(z - lay.ground(x, y), lay.RIBBON_LIFT, delta=0.03)
                self.assertAlmostEqual(math.hypot(row[0][0] - row[-1][0], row[0][1] - row[-1][1]), p["width"], places=6)
        self.assertGreaterEqual(slabs, 2)


if __name__ == "__main__":
    unittest.main()
