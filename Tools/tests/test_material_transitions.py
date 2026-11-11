"""Seamless material transitions.

  * the terrain layers of M_DA_Terrain are blended by height: a layer is exactly absent at weight 0 and
    exactly complete at weight 1 whatever the relief and the break-up noise say, and in between the relief
    decides where it shows first;
  * M_DA_Road (road ribbons, paved bridge decks) is the terrain's own surface function: at paving coverage 0
    it returns what M_DA_Terrain returns at that spot of the island - colour, roughness and normal - and at
    coverage 1 what a fully paved piece of ground returns, in a mirrored level too;
  * the relief maps come out of the layers' normal maps (textures.height_from_normal);
  * the pipeline's ribbons carry that coverage: a rim of 0 round every edge that meets the ground.

The material graphs are built against the recording stand-in for the `unreal` module (see
test_water_engine.py); nothing here has run in the engine.

    python -m unittest Tools.tests.test_material_transitions -v
"""

import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Tools"))
sys.path.insert(0, str(REPO / "Tools" / "tests"))

from test_water_engine import _EDITOR_MODULES, load_editor_module  # noqa: E402

LAYERS = ("Grass", "ForestFloor", "Sand", "WetSand", "Ash", "Rock", "Dirt", "Paving")
# layer -> (splat texture, channel index), as the terrain stage writes them
SPLAT = {"ForestFloor": ("B", 1), "Sand": ("A", 0), "WetSand": ("B", 2), "Ash": ("B", 0), "Rock": ("A", 1),
         "Dirt": ("A", 2), "Paving": ("A", 3)}
TEXTURES = (["T_Noise", "T_TerrainSplatA", "T_TerrainSplatB", "T_TerrainColor", "T_WaterShore", "T_Caustics"]
            + [f"T_Terrain_{layer}_{suffix}" for layer in LAYERS for suffix in ("BC", "N", "R", "H")])
ISLAND_MIN, ISLAND_SIZE = -153600.0, 307200.0


def wavy(name):
    """A smooth, repeatable texture: every channel its own sine pattern, values in 0.1 .. 0.9."""
    seed = np.frombuffer(hashlib.sha256(name.encode()).digest()[:24], np.uint8).astype(np.float64) / 255.0

    def sample(u, v):
        return tuple(0.5 + 0.4 * math.sin((3.0 + 9.0 * seed[c]) * u + (2.0 + 11.0 * seed[4 + c]) * v
                                           + 6.283 * seed[8 + c]) for c in range(4))
    return sample


def constant(*rgba):
    return lambda u, v: tuple(float(c) for c in rgba)


def splat_textures(**weights):
    """Splat maps holding the given layer weights everywhere."""
    a, b = [0.0] * 4, [0.0] * 4
    for layer, w in weights.items():
        tex, ch = SPLAT[layer]
        (a if tex == "A" else b)[ch] = float(w)
    return {"T_TerrainSplatA": constant(*a), "T_TerrainSplatB": constant(*b)}


class MaterialCase(unittest.TestCase):
    def setUp(self):
        self.materials = load_editor_module("materials")
        self.importer = load_editor_module("importer")
        self.unreal = _EDITOR_MODULES["unreal"]
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.unreal.reset(self.tmp.name)
        (Path(self.tmp.name) / "SourceAssets" / "Data").mkdir(parents=True, exist_ok=True)
        for name in TEXTURES:
            self.unreal.register_texture(name, self.importer.texture_kind(name))
        self.terrain = self.materials.build_terrain()
        self.road = self.materials.build_road()
        self.assertEqual(self.unreal.LOG["warning"] + self.unreal.LOG["error"] + self.unreal.PROBLEMS, [])
        self.textures = {name: wavy(name) for name in TEXTURES}

    def value(self, asset, prop, textures=None, **kw):
        tex = dict(self.textures)
        tex.update(textures or {})
        return self.unreal.evaluate(asset, getattr(self.unreal.MaterialProperty, prop), textures=tex, **kw)

    def assertClose(self, a, b, places=9, msg=None):
        self.assertEqual(len(a), len(b), msg)
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, places=places, msg=msg)


class HeightBlendTests(MaterialCase):
    """A layer's own weight still decides whether it is there; its relief only decides where it starts."""

    def flat_colours(self):
        tex = {f"T_Terrain_{layer}_BC": constant(0.1 + 0.1 * i, 0.9 - 0.1 * i, 0.3 + 0.05 * i, 1.0)
               for i, layer in enumerate(LAYERS)}
        return tex

    def surface(self, weights, heights=None, noise=0.5):
        tex = self.flat_colours()
        tex.update(splat_textures(**weights))
        tex["T_Noise"] = constant(noise, noise, noise, 1.0)
        for layer, h in (heights or {}).items():
            tex[f"T_Terrain_{layer}_H"] = constant(h, h, h, 1.0)
        return self.value(self.terrain, "MP_BASE_COLOR", tex, uvs={0: (0.31, 0.62)})

    def test_a_layer_at_weight_one_is_complete_and_at_zero_absent_whatever_the_relief(self):
        for layer in LAYERS[1:]:
            others = [name for name in LAYERS if name != layer]
            for noise in (0.0, 0.5, 1.0):
                # the same brightness noise on both sides: compare against the reference at this noise
                base = self.surface({}, noise=noise)
                full = self.surface({layer: 1.0}, noise=noise)
                # its relief at the bottom, everything else at the top (and the other way round)
                low = dict({name: 1.0 for name in others}, **{layer: 0.0})
                high = dict({name: 0.0 for name in others}, **{layer: 1.0})
                self.assertClose(self.surface({layer: 1.0}, low, noise), full, msg=f"{layer} complete, noise {noise}")
                self.assertClose(self.surface({layer: 0.0}, high, noise), base, msg=f"{layer} absent, noise {noise}")
            # and "complete" is that layer's own colour: the ratio to plain grass is the ratio of the albedos
            grass, own = self.flat_colours()["T_Terrain_Grass_BC"](0, 0), self.flat_colours()[f"T_Terrain_{layer}_BC"](0, 0)
            base, full = self.surface({}), self.surface({layer: 1.0})
            for c in range(3):
                self.assertAlmostEqual(full[c] / base[c], own[c] / grass[c], places=9, msg=layer)

    def test_between_zero_and_one_the_relief_decides(self):
        base, full = self.surface({}), self.surface({"Dirt": 1.0})

        def share(colour):          # how much of the dirt shows (0 grass .. 1 dirt)
            return (colour[0] - base[0]) / (full[0] - base[0])

        level = share(self.surface({"Dirt": 0.5}, {"Dirt": 0.5, "Grass": 0.5}))
        proud = share(self.surface({"Dirt": 0.5}, {"Dirt": 0.9, "Grass": 0.1}))
        sunk = share(self.surface({"Dirt": 0.5}, {"Dirt": 0.1, "Grass": 0.9}))
        self.assertAlmostEqual(level, 0.5, places=9)
        self.assertGreater(proud, 0.9)
        self.assertLess(sunk, 0.1)
        # steeper than a cross-fade: a quarter of the weight shows far less than a quarter of the layer
        self.assertLess(share(self.surface({"Dirt": 0.25}, {"Dirt": 0.5, "Grass": 0.5})), 0.1)
        # monotonic in the weight
        shares = [share(self.surface({"Dirt": w}, {"Dirt": 0.6, "Grass": 0.4})) for w in np.linspace(0.0, 1.0, 21)]
        self.assertEqual(shares, sorted(shares))
        self.assertEqual((shares[0], shares[-1]), (0.0, 1.0))

    def test_the_noise_moves_an_edge_but_never_a_pure_area(self):
        mid = {"Sand": 0.5}
        self.assertNotEqual(self.surface(mid, noise=0.1), self.surface(mid, noise=0.9))
        blend = self.materials.LAYER_BLEND
        self.assertEqual(set(blend), set(LAYERS[1:]))
        for layer, (k, soft) in blend.items():
            self.assertTrue(0.0 < k < 1.0 and soft > 0.0, layer)

    def test_every_layer_samples_its_relief_map(self):
        names = {e.props["texture"].name for e in self.terrain.expressions if e.props.get("texture")}
        self.assertLessEqual({f"T_Terrain_{layer}_H" for layer in LAYERS}, names)
        self.assertEqual(self.importer.texture_kind("T_Terrain_Grass_H"), "masks")

    def test_builds_without_the_relief_maps(self):
        # source assets from before this change: flat relief, the layers still blend
        self.unreal.reset(self.tmp.name)
        for name in TEXTURES:
            if not name.endswith("_H"):
                self.unreal.register_texture(name, self.importer.texture_kind(name))
        terrain = self.materials.build_terrain()
        self.materials.build_road()
        self.assertEqual(self.unreal.LOG["warning"] + self.unreal.LOG["error"] + self.unreal.PROBLEMS, [])
        tex = dict(self.flat_colours(), T_Noise=constant(0.5, 0.5, 0.5, 1.0))
        out = {w: self.value(terrain, "MP_BASE_COLOR", dict(tex, **splat_textures(Rock=w)), uvs={0: (0.2, 0.2)})
               for w in (0.0, 0.5, 1.0)}
        self.assertAlmostEqual(out[0.5][0], (out[0.0][0] + out[1.0][0]) / 2.0, places=9)


class RoadIsTheTerrainTests(MaterialCase):
    """M_DA_Road on a ribbon or a deck against M_DA_Terrain on the ground at the same spot of the island."""

    SPOTS = ((0.0, 0.0, 2400.0), (52310.0, -91247.0, 880.0), (-120033.0, 14870.0, 3125.0), (8800.0, 133000.0, 15.0))

    @staticmethod
    def island_uv(position, mirror=False):
        u = (position[0] - ISLAND_MIN) / ISLAND_SIZE
        v = (position[1] - ISLAND_MIN) / ISLAND_SIZE
        return (u, 1.0 - v) if mirror else (u, v)

    @staticmethod
    def unit(v):
        length = math.sqrt(sum(c * c for c in v))
        return tuple(c / length for c in v)

    def test_without_paving_it_is_the_ground_under_it(self):
        for p in self.SPOTS:
            uv = self.island_uv(p)
            for prop in ("MP_BASE_COLOR", "MP_ROUGHNESS"):
                ground = self.value(self.terrain, prop, uvs={0: uv}, world_position=p)
                ribbon = self.value(self.road, prop, world_position=p, vertex_color=(0.0, 0.0, 0.0, 1.0))
                self.assertClose(ribbon, ground, msg=f"{prop} at {p}")
            # the terrain's normal is in its tangent space (tangent = +X, bitangent = +Y on level ground)
            ground = self.unit(self.value(self.terrain, "MP_NORMAL", uvs={0: uv}, world_position=p))
            ribbon = self.value(self.road, "MP_NORMAL", world_position=p, vertex_color=(0.0, 0.0, 0.0, 1.0))
            self.assertClose(ribbon, ground, msg=f"normal at {p}")

    def test_fully_paved_it_is_paved_ground(self):
        paved = splat_textures(Paving=1.0)
        for p in self.SPOTS:
            uv = self.island_uv(p)
            for prop in ("MP_BASE_COLOR", "MP_ROUGHNESS"):
                ground = self.value(self.terrain, prop, paved, uvs={0: uv}, world_position=p)
                deck = self.value(self.road, prop, world_position=p)        # no vertex colours: white
                self.assertClose(deck, ground, msg=f"{prop} at {p}")
            ground = self.unit(self.value(self.terrain, "MP_NORMAL", paved, uvs={0: uv}, world_position=p))
            self.assertClose(self.value(self.road, "MP_NORMAL", world_position=p), ground, msg=f"normal at {p}")

    def test_the_rim_runs_from_one_to_the_other(self):
        p = self.SPOTS[1]
        verge = splat_textures(Dirt=0.7, ForestFloor=0.2)        # what the terrain stage paints beside a road
        ground = self.value(self.road, "MP_BASE_COLOR", verge, world_position=p, vertex_color=(0, 0, 0, 1))
        stone = self.value(self.road, "MP_BASE_COLOR", verge, world_position=p, vertex_color=(1, 1, 1, 1))
        self.assertNotEqual(ground, stone)
        last = None
        for cover in np.linspace(0.0, 1.0, 33):
            c = self.value(self.road, "MP_BASE_COLOR", verge, world_position=p, vertex_color=(cover, 0, 0, 1))
            t = [(c[k] - ground[k]) / (stone[k] - ground[k]) for k in range(3) if abs(stone[k] - ground[k]) > 1e-6]
            self.assertTrue(all(-1e-9 <= x <= 1.0 + 1e-9 for x in t))
            self.assertLess(max(t) - min(t), 1e-9, "one blend factor for the whole surface")
            if last is not None:
                self.assertGreaterEqual(t[0], last - 1e-12)
            last = t[0]

    def test_the_normal_follows_the_mesh_it_is_drawn_on(self):
        self.assertIs(self.road.props["tangent_space_normal"], False)
        self.assertIsNot(self.terrain.props.get("tangent_space_normal"), False)
        p = self.SPOTS[2]
        # (a normal-map sampler hands the graph the decoded vector: flat = +Z)
        flat = {name: constant(0.0, 0.0, 1.0, 1.0) for name in TEXTURES if name.endswith("_N")}
        for vn in ((0.0, 0.0, 1.0), self.unit((0.2, -0.1, 1.0)), self.unit((-0.35, 0.3, 0.8))):
            # a flat layer normal: the surface's own normal comes back
            self.assertClose(self.value(self.road, "MP_NORMAL", flat, world_position=p, vertex_normal=vn), vn)
            n = self.value(self.road, "MP_NORMAL", world_position=p, vertex_normal=vn)
            self.assertAlmostEqual(sum(c * c for c in n), 1.0, places=9)
            # the detail is laid into the surface: tangent along +X, bitangent = normal x tangent
            t = self.unit(tuple(a - b * vn[0] for a, b in zip((1.0, 0.0, 0.0), vn)))
            b = (vn[1] * t[2] - vn[2] * t[1], vn[2] * t[0] - vn[0] * t[2], vn[0] * t[1] - vn[1] * t[0])
            ts = self.value(self.terrain, "MP_NORMAL", uvs={0: self.island_uv(p)}, world_position=p)
            want = self.unit(tuple(t[i] * ts[0] + b[i] * ts[1] + vn[i] * ts[2] for i in range(3)))
            self.assertClose(n, want)

    def test_instances_and_a_mirrored_level(self):
        m = self.materials
        palette = {"M_RoadPaving": {"kind": "road", "color_linear": [0.3, 0.3, 0.3], "paving": 1.0},
                   "M_Terrain": {"kind": "terrain", "color_linear": [0.3, 0.5, 0.2]}}
        instances = m.build_instances(palette, {"M_DA_Road": self.road, "M_DA_Terrain": self.terrain})
        mi = instances["M_RoadPaving"]
        self.assertIs(mi.parent, self.road)
        self.assertEqual((mi.scalars["Paving"], mi.scalars["MirrorY"]), (1.0, 0.0))
        p = self.SPOTS[1]
        self.assertClose(self.value(mi, "MP_BASE_COLOR", world_position=p, vertex_color=(0, 0, 0, 1)),
                         self.value(self.terrain, "MP_BASE_COLOR", uvs={0: self.island_uv(p)}, world_position=p))
        # a level built with a mirrored Y axis: the terrain mesh's UVs run the other way in the world
        m.mirror_water_instances(palette, instances)
        self.assertEqual(mi.scalars["MirrorY"], 1.0)
        uv = self.island_uv(p, mirror=True)
        for prop in ("MP_BASE_COLOR", "MP_ROUGHNESS"):
            self.assertClose(self.value(mi, prop, world_position=p, vertex_color=(0, 0, 0, 1)),
                             self.value(self.terrain, prop, uvs={0: uv}, world_position=p), msg=prop)
        ts = self.value(self.terrain, "MP_NORMAL", uvs={0: uv}, world_position=p)
        self.assertClose(self.value(mi, "MP_NORMAL", world_position=p, vertex_color=(0, 0, 0, 1)),
                         self.unit((ts[0], -ts[1], ts[2])))
        self.assertEqual(self.unreal.LOG["warning"] + self.unreal.LOG["error"] + self.unreal.PROBLEMS, [])

    def test_the_far_tint_and_the_wet_band_are_shared(self):
        # beyond the macro-blend distance and on a wet bank the two still agree (one finishing function)
        p = self.SPOTS[3]
        wet = {"T_WaterShore": constant(0.4, 0.2, 0.0, 0.9)}
        ground = self.value(self.terrain, "MP_BASE_COLOR", wet, uvs={0: self.island_uv(p)}, world_position=p,
                            pixel_depth=45000.0)
        ribbon = self.value(self.road, "MP_BASE_COLOR", wet, world_position=p, pixel_depth=45000.0,
                            vertex_color=(0, 0, 0, 1))
        self.assertClose(ribbon, ground)
        near = self.value(self.road, "MP_BASE_COLOR", wet, world_position=p, vertex_color=(0, 0, 0, 1))
        self.assertNotEqual(near, ribbon)


class ReliefMapTests(unittest.TestCase):
    def test_height_from_normal_recovers_a_periodic_relief(self):
        from dai import textures
        n = 256
        y, x = np.mgrid[0:n, 0:n].astype(np.float64)
        w = 2.0 * math.pi / n
        height = 2.0 * np.sin(9 * w * x) * np.cos(7 * w * y) + 1.2 * np.sin(13 * w * (x + y)) + np.cos(21 * w * x)
        gx = np.gradient(height, axis=1)
        gy = np.gradient(height, axis=0)
        nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        out = textures.height_from_normal((nrm * 0.5 + 0.5).astype(np.float32), size=n)
        self.assertEqual(out.shape, (n, n))
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)
        self.assertGreater(float(np.corrcoef(out.ravel(), height.ravel())[0, 1]), 0.97)

    def test_the_committed_relief_maps_use_their_range(self):
        from PIL import Image
        folder = REPO / "DuelAcademyIsland" / "SourceAssets" / "Textures"
        for layer in LAYERS:
            path = folder / f"T_Terrain_{layer}_H.png"
            self.assertTrue(path.exists(), path.name)
            with Image.open(path) as img:
                a = np.asarray(img.convert("L")).astype(np.float64) / 255.0
            self.assertEqual(a.shape, (512, 512), layer)
            self.assertGreater(float(a.std()), 0.08, f"{layer}: relief has contrast")
            self.assertTrue(0.3 < float(a.mean()) < 0.7, f"{layer}: relief is centred")


try:
    import bpy  # noqa: F401
    import scipy  # noqa: F401
    HAVE_PIPELINE = (REPO / "Tools" / ".cache" / "terrain_info.json").exists()
except ImportError:
    HAVE_PIPELINE = False


@unittest.skipUnless(HAVE_PIPELINE, "needs Blender's bpy, scipy and a built terrain (Tools/.cache)")
class RibbonRimTests(unittest.TestCase):
    """The paving coverage the road ribbons hand to M_DA_Road."""

    @classmethod
    def setUpClass(cls):
        from dai import layout, terrain
        cls.terrain = terrain
        cls.lay = layout.Layout(lambda *a, **k: None)
        cls.roads = [p for p in cls.lay.meta["paths"] if terrain.road_has_ribbon(p)]

    def test_every_edge_on_the_ground_is_rim(self):
        lay = self.lay
        self.assertTrue(self.roads)
        kinds = set()
        for p in self.roads:
            _arc, runs = lay.road_runs(p)
            sections = lay.ribbon_sections(p)
            self.assertEqual(len(runs), len(sections))
            for (s0, s1, _e0, _e1, k0, k1), run in zip(runs, sections):
                kinds.update((k0, k1))
                rows = [row for _s, row in run]
                for row in rows:
                    self.assertEqual(len(row), 7)
                for row in rows[1:-1]:
                    self.assertEqual([q[3] for q in row], [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0])
                    # the paved part starts RIBBON_RIM inside the edge
                    rim = math.hypot(row[1][0] - row[0][0], row[1][1] - row[0][1])
                    self.assertAlmostEqual(rim, min(lay.RIBBON_RIM, 0.4 * p["width"] / 2.0), places=6)
                for row, kind in ((rows[0], k0), (rows[-1], k1)):
                    cover = [q[3] for q in row]
                    if kind == "ground":
                        self.assertEqual(cover, [0.0] * 7, f"{p['id']}: an end on the ground is all rim")
                    elif kind == "bridge":
                        self.assertEqual(cover, [1.0] * 7, f"{p['id']}: paved across where it meets the deck")
                    else:
                        self.assertEqual(cover, [0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0])
                    for q in row:
                        lift = lay.RIBBON_LIFT if q[3] else lay.RIBBON_RIM_LIFT
                        self.assertGreaterEqual(q[2] - lay.ground(q[0], q[1]), lift - 1e-6)
        self.assertEqual(kinds, {"ground", "bridge", "road"})

    def test_the_mesh_carries_the_coverage_as_vertex_colour(self):
        lay = self.lay
        p = self.roads[0]
        mb = lay.road_ribbon(p)
        self.assertEqual(set(mb.face_mats), {"M_RoadPaving"})
        self.assertEqual(len(mb.colors), len(mb.verts))
        values = {c[0] for c in mb.colors.values()}
        self.assertEqual(values, {0.0, 1.0})
        # skirts (anything below a top vertex) are drawn as ground
        tops = np.array([q[:3] for run in lay.ribbons[p["id"]] for _s, row in run for q in row])
        skirt = 0
        for i, v in enumerate(mb.verts):
            near = tops[np.argmin(np.hypot(tops[:, 0] - v[0], tops[:, 1] - v[1]))]
            if v[2] < near[2] - 0.5:
                self.assertEqual(mb.colors[i][0], 0.0)
                skirt += 1
        self.assertGreater(skirt, 100)
        # and the signature notices a change of colour alone
        sig = lay.mesh_signature(mb)
        mb.colors[next(iter(mb.colors))] = (0.5, 0.5, 0.5, 1.0)
        self.assertNotEqual(lay.mesh_signature(mb), sig)

    def test_the_ground_under_a_ribbon_is_road_bed_not_paving(self):
        from PIL import Image
        folder = REPO / "DuelAcademyIsland" / "SourceAssets" / "Textures"
        with Image.open(folder / "T_TerrainSplatA.png") as img:
            splat = np.asarray(img.convert("RGBA")).astype(np.float64) / 255.0
        from dai import config as C
        res = splat.shape[0]
        lay = self.lay
        p = next(q for q in self.roads if q["id"] == "to_gym")
        dirt, paving, n = 0.0, 0.0, 0
        for x, y, *_ in p["samples"][40:-40:4]:
            if lay.in_any_pad(x, y, 40.0) is not None or any(          # (a pad's apron is paved ground)
                    b["path"] == p["id"] and math.hypot(x - b["center"][0], y - b["center"][1]) < 40.0
                    for b in lay.meta["bridges"]):
                continue
            c = int((x + C.HALF) / C.WORLD_SIZE * res)
            r = int((C.HALF - y) / C.WORLD_SIZE * res)
            dirt += splat[r, c, 2]
            paving += splat[r, c, 3]
            n += 1
        self.assertGreater(n, 20)
        self.assertGreater(dirt / n, 0.7)
        self.assertLess(paving / n, 0.02)


if __name__ == "__main__":
    unittest.main()
