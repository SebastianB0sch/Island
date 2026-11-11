"""The Unreal side of the water upgrade, checked outside the engine.

Three implementations must agree on the wave surface: the C++ gameplay maths
(Source/DuelAcademyIsland/Public/DAWaterWaves.h - buoyancy, swimming, wading), the node graph of the
M_DA_Water master material (Content/Python/duel_academy/materials.py) and the reference in this file, written
straight from the formulas of the water contract:

    k = 2 pi / L, omega = k c, theta = k dot(D, p) - omega t + phi
    offset.xy = sum(D s A m cos theta), offset.z = sum(A m sin theta)
    normal = normalize(-sum(D.x k A m cos), -sum(D.y k A m cos), 1 - sum(k s A m sin))
    m = wave mask (bilinear, clamped) * far fade; height at a fixed XY = 3 fixed-point inversions

* WaterWavesCppTests compiles the real header against a stand-in CoreMinimal.h (Tools/tests/water) and compares
  its numbers with the reference. Skipped when no C++ compiler is installed.
* WaterMaterialTests builds the water masters and their instances against a strict fake ``unreal`` module
  (Tools/tests/water/fake_unreal.py: unknown expression classes, pins, properties and instance parameters are
  errors), then evaluates the recorded M_DA_Water graph numerically against the reference.
* WaterDataTests covers the level-side packing of water.json and the numbers both sides must share.

    python -m unittest Tools.tests.test_water_engine -v
"""

import base64
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent / "water"
SOURCE = REPO / "DuelAcademyIsland" / "Source" / "DuelAcademyIsland"
EDITOR_PY = REPO / "DuelAcademyIsland" / "Content" / "Python"
REAL_WATER_JSON = REPO / "DuelAcademyIsland" / "SourceAssets" / "Data" / "water.json"
REAL_PALETTE_JSON = REPO / "DuelAcademyIsland" / "SourceAssets" / "Data" / "materials.json"
REAL_TEXTURES = REPO / "DuelAcademyIsland" / "SourceAssets" / "Textures"

TWO_PI = 2.0 * math.pi
ISLAND_MIN, ISLAND_MAX = -153600.0, 153600.0

# A sea and a lake wave set in water.json form (UE units: cm, cm/s, radians).
OCEAN_WAVES = [
    {"dir": [-0.173648, -0.984808], "wavelength": 7800.0, "amplitude": 30.0, "steepness": 0.7, "speed": 1103.55, "phase": 0.0},
    {"dir": [0.34202, -0.939693], "wavelength": 5200.0, "amplitude": 21.0, "steepness": 0.65, "speed": 901.0, "phase": 1.3},
    {"dir": [-0.5, -0.866025], "wavelength": 4100.0, "amplitude": 16.0, "steepness": 0.6, "speed": 800.1, "phase": 2.1},
    {"dir": [0.642788, -0.766044], "wavelength": 3300.0, "amplitude": 13.0, "steepness": 0.55, "speed": 717.8, "phase": 4.4},
    {"dir": [-0.766044, -0.642788], "wavelength": 2800.0, "amplitude": 11.0, "steepness": 0.5, "speed": 661.2, "phase": 0.7},
    {"dir": [0.087156, -0.996195], "wavelength": 2400.0, "amplitude": 10.0, "steepness": 0.5, "speed": 0.0, "phase": 5.5},
]
LAKE_WAVES = [
    {"dir": [-0.906308, 0.422618], "wavelength": 1100.0, "amplitude": 4.0, "steepness": 0.6, "speed": 414.42, "phase": 0.0},
    {"dir": [-0.642788, 0.766044], "wavelength": 780.0, "amplitude": 3.0, "steepness": 0.5, "speed": 349.0, "phase": 2.0},
    {"dir": [-0.984808, -0.173648], "wavelength": 620.0, "amplitude": 2.0, "steepness": 0.5, "speed": 311.1, "phase": 4.0},
]


# --------------------------------------------------------------------------- reference implementation
def deep_water_speed(wavelength):
    return math.sqrt(981.0 * wavelength / TWO_PI)


def ref_mask(mask, x, y):
    """Bilinear, clamped lookup of mask = (size, min_x, min_y, max_x, max_y, values 0..255 row-major) -> 0..1."""
    if mask is None:
        return 1.0
    size, x0, y0, x1, y1, data = mask
    fx = min(max((x - x0) / (x1 - x0) * size - 0.5, 0.0), size - 1.0)
    fy = min(max((y - y0) / (y1 - y0) * size - 0.5, 0.0), size - 1.0)
    ix, iy = min(int(fx), size - 1), min(int(fy), size - 1)
    jx, jy = min(ix + 1, size - 1), min(iy + 1, size - 1)
    tx, ty = fx - ix, fy - iy
    top = data[iy * size + ix] * (1 - tx) + data[iy * size + jx] * tx
    bottom = data[jy * size + ix] * (1 - tx) + data[jy * size + jx] * tx
    return (top * (1 - ty) + bottom * ty) / 255.0


def ref_scale(mask, fade, x, y):
    m = ref_mask(mask, x, y)
    if fade and fade[1] > 0.0:
        t = min(max((max(abs(x), abs(y)) - fade[0]) / max(fade[1] - fade[0], 1e-9), 0.0), 1.0)
        m *= 1.0 - t * t * (3.0 - 2.0 * t)
    return m


def ref_eval(waves, x, y, t, m):
    """(offset x, y, z, unnormalised normal x, y, z, fold) of the wave set at the undisplaced position."""
    ox = oy = oz = sx = sy = fold = 0.0
    for w in waves[:6]:
        dx, dy = w["dir"]
        norm = math.hypot(dx, dy)
        dx, dy = dx / norm, dy / norm
        length, amp, steep = w["wavelength"], w["amplitude"] * m, w["steepness"]
        speed = w["speed"] if w["speed"] > 0.0 else deep_water_speed(length)
        k = TWO_PI / length
        theta = k * (dx * x + dy * y) - k * speed * t + w["phase"]
        s, c = math.sin(theta), math.cos(theta)
        ox += dx * steep * amp * c
        oy += dy * steep * amp * c
        oz += amp * s
        sx += dx * k * amp * c
        sy += dy * k * amp * c
        fold += k * steep * amp * s
    return ox, oy, oz, -sx, -sy, 1.0 - fold, fold


def ref_height(waves, mask, fade, x, y, t, iterations=3):
    qx, qy = x, y
    for _ in range(iterations):
        ox, oy = ref_eval(waves, qx, qy, t, ref_scale(mask, fade, qx, qy))[:2]
        qx, qy = x - ox, y - oy
    return ref_eval(waves, qx, qy, t, ref_scale(mask, fade, qx, qy))[2]


def ref_river(points, x, y):
    """(inside, surface z, edge distance, flow x, flow y) of the closest point of a river centre line."""
    best = None
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        len2 = dx * dx + dy * dy
        t = min(max(((x - a[0]) * dx + (y - a[1]) * dy) / len2, 0.0), 1.0) if len2 > 1e-9 else 0.0
        px, py = a[0] + dx * t, a[1] + dy * t
        edge = math.hypot(x - px, y - py) - (a[3] + (b[3] - a[3]) * t)
        if best is None or edge < best[2]:
            length = math.sqrt(len2)
            best = (edge <= 0.0, a[2] + (b[2] - a[2]) * t, edge, dx / length, dy / length)
    return best


def synthetic_mask(size):
    """A wave mask with structure: calm in the south-west, open towards the north-east, zero on the rim."""
    data = []
    for row in range(size):
        for col in range(size):
            v = int(255 * (0.15 + 0.85 * (col + row) / (2.0 * (size - 1))))
            data.append(0 if row in (0, size - 1) or col in (0, size - 1) else v)
    return data


def _compiler():
    for c in ("clang++", "g++"):
        if shutil.which(c):
            return c
    return None


# --------------------------------------------------------------------------- C++ wave maths
@unittest.skipIf(_compiler() is None, "no C++ compiler")
class WaterWavesCppTests(unittest.TestCase):
    """DAWaterWaves.h compiled as-is against Tools/tests/water/CoreMinimal.h."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.exe = os.path.join(cls.tmp.name, "test_waves")
        build = subprocess.run([_compiler(), "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-I", str(HERE),
                                "-I", str(SOURCE / "Public"), str(HERE / "test_waves.cpp"), "-o", cls.exe],
                               capture_output=True, text=True)
        cls.build = build

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_cases(self, lines):
        self.assertEqual(self.build.returncode, 0, self.build.stderr)
        path = os.path.join(self.tmp.name, "cases.txt")
        with open(path, "w", encoding="utf-8") as fp:
            fp.write("\n".join(lines) + "\n")
        run = subprocess.run([self.exe, path], capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        out = run.stdout.strip().splitlines()
        self.assertEqual(out[-1], "WAVES OK")
        return [[float(v) for v in line.split()] for line in out[:-1]]

    @staticmethod
    def wave_lines(waves):
        """The plain FDAWave the header works on: unit direction and an explicit speed, which is what
        ADAIslandManager's ConvertWave hands it."""
        lines = [f"waves {len(waves)}"]
        for w in waves:
            speed = w["speed"] if w["speed"] > 0.0 else deep_water_speed(w["wavelength"])
            norm = math.hypot(*w["dir"])
            lines.append(" ".join(repr(float(v)) for v in (w["dir"][0] / norm, w["dir"][1] / norm, w["wavelength"],
                                                           w["amplitude"], w["steepness"], speed, w["phase"])))
        return lines

    def assertClose(self, got, want, tol=1e-9, msg=""):
        self.assertEqual(len(got), len(want), msg)
        for g, w in zip(got, want):
            self.assertLessEqual(abs(g - w), tol * max(1.0, abs(w)), f"{msg}: {got} != {want}")

    def test_constants_match_the_material_and_the_manager(self):
        consts = self.run_cases([])[0]
        materials = load_editor_module("materials")
        self.assertEqual(int(consts[0]), materials.WAVE_SLOTS)
        self.assertEqual(consts[1], materials.WAVE_FADE_START)
        self.assertEqual(consts[2], materials.WAVE_FADE_END)
        self.assertEqual(int(consts[4]), 3, "the contract fixes 3 inverse-displacement iterations")
        header = (SOURCE / "Public" / "DAIslandManager.h").read_text(encoding="utf-8")
        self.assertIn(f"WaveFadeStart = {consts[1]:.0f}.f", header)
        self.assertIn(f"WaveFadeEnd = {consts[2]:.0f}.f", header)
        self.assertIn("WaveMaskMin = FVector2D(-153600.0, -153600.0)", header)
        self.assertIn("WaveMaskMax = FVector2D(153600.0, 153600.0)", header)
        self.assertEqual((materials.ISLAND_MIN_CM, materials.ISLAND_MIN_CM + materials.ISLAND_SIZE_CM),
                         (ISLAND_MIN, ISLAND_MAX))

    def test_wave_sum_and_surface_height_match_the_reference(self):
        size = 8
        data = synthetic_mask(size)
        mask = (size, -90000.0, -70000.0, 110000.0, 120000.0, data)
        fade = (100000.0, 140000.0)
        points = [(0.0, 0.0, 0.0), (1234.5, -987.6, 3.25), (-45000.0, 30000.0, 17.5), (88000.0, 101000.0, 40.0),
                  (-200000.0, 5000.0, 12.0), (109999.0, 119999.0, 9.0), (120000.0, -3000.0, 77.7),
                  (300.0, 139000.0, 1.0), (15000.0, -150000.0, 2.0)]
        lines = self.wave_lines(OCEAN_WAVES)
        lines += [f"mask {size} {mask[1]!r} {mask[2]!r} {mask[3]!r} {mask[4]!r}", " ".join(str(v) for v in data)]
        lines += [f"fade {fade[0]!r} {fade[1]!r}"]
        for x, y, t in points:
            lines += [f"scale {x!r} {y!r}", f"eval {x!r} {y!r} {t!r}", f"height {x!r} {y!r} {t!r}"]
        out = self.run_cases(lines)
        max_fold = sum(TWO_PI / w["wavelength"] * w["steepness"] * w["amplitude"] for w in OCEAN_WAVES)
        self.assertClose(out[1], [max_fold], msg="MaxFold")
        rows = iter(out[2:])
        moved = 0
        for x, y, t in points:
            m = ref_scale(mask, fade, x, y)
            self.assertClose(next(rows), [m], msg=f"scale at {x}, {y}")
            self.assertClose(next(rows), list(ref_eval(OCEAN_WAVES, x, y, t, m)), msg=f"eval at {x}, {y}")
            height = next(rows)
            self.assertClose(height, [ref_height(OCEAN_WAVES, mask, fade, x, y, t)], msg=f"height at {x}, {y}")
            moved += abs(height[0]) > 1.0
        self.assertGreaterEqual(moved, 4, "the test points should sit in moving water")

    def test_no_mask_no_fade_and_wave_cap(self):
        # 7 waves: only the first 6 count (the material has 6 slots)
        seven = LAKE_WAVES + OCEAN_WAVES[:4]
        lines = self.wave_lines(seven) + ["mask 0 0 0 0 0", "fade 0 0", "scale 5.0 -7.0", "eval 5.0 -7.0 3.5",
                                          "height 5.0 -7.0 3.5"]
        out = self.run_cases(lines)
        self.assertClose(out[2], [1.0])
        self.assertClose(out[3], list(ref_eval(seven[:6], 5.0, -7.0, 3.5, 1.0)))
        self.assertClose(out[4], [ref_height(seven[:6], None, None, 5.0, -7.0, 3.5)])

    def test_inverse_displacement_lands_on_the_displaced_sheet(self):
        # The height at a fixed XY is the height of the sheet point that was moved there: q + offset(q) = (x, y).
        x, y, t = 4321.0, -2500.0, 11.0
        out = self.run_cases(self.wave_lines(OCEAN_WAVES) + [f"height {x!r} {y!r} {t!r}"])
        qx, qy = x, y
        for _ in range(60):
            ox, oy = ref_eval(OCEAN_WAVES, qx, qy, t, 1.0)[:2]
            qx, qy = x - ox, y - oy
        exact = ref_eval(OCEAN_WAVES, qx, qy, t, 1.0)[2]
        self.assertLessEqual(abs(out[2][0] - exact), 0.05, "3 iterations are within half a millimetre of the limit")

    def test_river_queries_match_the_reference(self):
        river = [(0.0, 0.0, 3000.0, 400.0), (400.0, 50.0, 2990.0, 420.0), (800.0, 300.0, 2975.0, 900.0),
                 (1000.0, 700.0, 2960.0, 500.0), (1000.0, 700.0, 2960.0, 500.0), (1300.0, 1500.0, 2900.0, 300.0)]
        queries = [(0.0, 0.0), (-500.0, 0.0), (420.0, 480.0), (900.0, 1900.0), (1300.0, 1500.0), (5000.0, 5000.0),
                   (850.0, -700.0), (1100.0, 950.0)]
        lines = [f"river {len(river)}"] + [" ".join(repr(v) for v in p) for p in river] + ["bounds"]
        lines += [f"query {x!r} {y!r}" for x, y in queries]
        out = self.run_cases(lines)
        self.assertClose(out[1], [1.0, min(p[0] - p[3] for p in river), min(p[1] - p[3] for p in river),
                                  max(p[0] + p[3] for p in river), max(p[1] + p[3] for p in river)])
        inside = 0
        for (x, y), got in zip(queries, out[2:]):
            want = ref_river(river, x, y)
            self.assertClose(got, [1.0 if want[0] else 0.0, *want[1:]], msg=f"river at {x}, {y}")
            inside += want[0]
        self.assertTrue(0 < inside < len(queries), "queries should cover both banks")

    def test_empty_inputs_are_flat_water(self):
        out = self.run_cases(["waves 0", "eval 1.0 2.0 3.0", "height 1.0 2.0 3.0", "river 0", "query 1.0 2.0", "bounds"])
        self.assertClose(out[2], [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0])
        self.assertClose(out[3], [0.0])
        self.assertEqual(out[4][0], 0.0, "no river: never inside")
        self.assertEqual(out[5][0], 0.0)


# --------------------------------------------------------------------------- editor scripts against a fake unreal
_EDITOR_MODULES = {}


def load_editor_module(name):
    """duel_academy.<name> imported against Tools/tests/water/fake_unreal.py (kept out of sys.modules afterwards,
    so no other test ever sees a module called ``unreal``)."""
    if name in _EDITOR_MODULES:
        return _EDITOR_MODULES[name]
    saved = {k: sys.modules.get(k) for k in list(sys.modules) if k == "unreal" or k.startswith("duel_academy")}
    for k in saved:
        sys.modules.pop(k, None)
    sys.path[:0] = [str(HERE), str(EDITOR_PY)]
    try:
        fake = _EDITOR_MODULES.get("unreal") or importlib.import_module("fake_unreal")
        sys.modules["unreal"] = fake
        _EDITOR_MODULES["unreal"] = fake
        for mod in ("common", "materials", "importer", "level"):
            _EDITOR_MODULES[mod] = importlib.import_module(f"duel_academy.{mod}")
    finally:
        del sys.path[:2]
        for k in [k for k in sys.modules if k == "unreal" or k == "fake_unreal" or k.startswith("duel_academy")]:
            sys.modules.pop(k, None)
        sys.modules.update({k: v for k, v in saved.items() if v is not None})
    return _EDITOR_MODULES[name]


OLD_TEXTURES = ["T_WaterNormal", "T_WaterStreaks", "T_Noise", "T_TerrainSplatA", "T_TerrainSplatB", "T_TerrainColor"] + [
    f"T_Terrain_{layer}_{suffix}" for layer in ("Grass", "ForestFloor", "Sand", "WetSand", "Ash", "Rock", "Dirt", "Paving")
    for suffix in ("BC", "N", "R")]
NEW_TEXTURES = ["T_WaterDetailN", "T_WaterFoam", "T_Caustics", "T_Ripples", "T_WaveMask", "T_WaterShore"]

SAMPLE_PALETTE = {
    "M_Ocean": {"kind": "water", "color_linear": [0.004, 0.1, 0.21], "waves": "ocean", "mask": True, "shore": True,
                "foam": 0.9, "crest": 0.7},
    "M_LakeWater": {"kind": "water", "color_linear": [0.01, 0.17, 0.17], "waves": "lake", "shore": True, "foam": 0.3},
    "M_LegacyWater": {"kind": "water", "color_linear": [0.1, 0.2, 0.2], "wave_scale": 0.004, "wave_speed": 6.0,
                      "wave_strength": 0.6},
    "M_FountainWater": {"kind": "pool", "color_linear": [0.02, 0.32, 0.42], "ripple": 0.7, "ripple_scale": 0.6,
                        "ripple_speed": 1.2, "wave_scale": 0.0045, "wave_speed": 6.0, "wave_strength": 0.6,
                        "some_future_key": 1},
    "M_HotWater": {"kind": "pool", "color_linear": [0.17, 0.52, 0.48]},
    "M_River": {"kind": "river", "color_linear": [0.02, 0.2, 0.2], "flow": 1.4, "foam": 0.8, "wave_strength": 0.5},
    "M_Waterfall": {"kind": "waterfall", "color_linear": [0.69, 0.89, 1.0], "opacity": 0.8},
    "M_FountainFall": {"kind": "flow", "color_linear": [0.7, 0.89, 1.0], "opacity": 0.55, "flow": 2.4, "streak": 1.6,
                       "stretch": 4.0, "base": 0.22, "contrast": 1.8, "sparkle": 0.5, "wobble": 1.0},
    "M_Terrain": {"kind": "terrain", "color_linear": [0.3, 0.5, 0.2]},
}

WATER_MASTERS = ("M_DA_Water", "M_DA_PoolWater", "M_DA_River", "M_DA_Waterfall", "M_DA_WaterFlow", "M_DA_Spray",
                 "M_DA_Terrain")


class WaterMaterialTests(unittest.TestCase):
    """The water masters and instances built against the strict fake editor."""

    MASK_SIZE = 16

    def setUp(self):
        self.materials = load_editor_module("materials")
        self.importer = load_editor_module("importer")
        self.unreal = _EDITOR_MODULES["unreal"]
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mask = synthetic_mask(self.MASK_SIZE)

    def project(self, with_water=True, textures=OLD_TEXTURES + NEW_TEXTURES):
        """A fresh fake project: textures registered the way importer.texture_kind would import them."""
        self.unreal.reset(self.tmp.name)
        data_dir = Path(self.tmp.name) / "SourceAssets" / "Data"
        data_dir.mkdir(parents=True, exist_ok=True)
        water = data_dir / "water.json"
        if with_water:
            water.write_text(json.dumps({
                "version": 1, "sea_level": 0.0, "ocean": {"waves": OCEAN_WAVES}, "lake": {"level": 3000.0, "waves": LAKE_WAVES},
                "wave_mask": {"texture": "T_WaveMask", "size": self.MASK_SIZE, "min": [ISLAND_MIN, ISLAND_MIN],
                              "max": [ISLAND_MAX, ISLAND_MAX], "data": base64.b64encode(bytes(self.mask)).decode("ascii")},
                "rivers": []}), encoding="utf-8")
        elif water.exists():
            water.unlink()
        for name in textures:
            self.unreal.register_texture(name, self.importer.texture_kind(name))

    def build(self):
        m = self.materials
        mpc = m.build_mpc()
        masters = {"M_DA_Water": m.build_water(), "M_DA_PoolWater": m.build_pool_water(), "M_DA_River": m.build_river(),
                   "M_DA_Waterfall": m.build_waterfall(), "M_DA_WaterFlow": m.build_water_flow(),
                   "M_DA_Spray": m.build_spray(), "M_DA_Terrain": m.build_terrain(mpc)}
        instances = m.build_instances(SAMPLE_PALETTE, masters)
        return masters, instances

    def assertCleanBuild(self):
        self.assertEqual(self.unreal.LOG["warning"], [])
        self.assertEqual(self.unreal.LOG["error"], [])
        self.assertEqual(self.unreal.PROBLEMS, [])

    def mask_texture(self, u, v):
        size = self.MASK_SIZE
        value = ref_mask((size, 0.0, 0.0, 1.0, 1.0, self.mask), u, v)
        return (value, value, value, 1.0)

    def evaluate(self, asset, prop, position, time, **overrides):
        flat = lambda u, v: (0.5, 0.5, 1.0, 1.0)     # noqa: E731 - a flat normal / mid-grey data texture
        textures = {name: flat for name in OLD_TEXTURES + NEW_TEXTURES}
        textures["T_WaveMask"] = self.mask_texture
        textures.update(overrides.pop("textures", {}))
        return self.unreal.evaluate(asset, getattr(self.unreal.MaterialProperty, prop), world_position=position,
                                    time=time, textures=textures, **overrides)

    # ------------------------------------------------------------------ builds
    def test_every_water_master_and_instance_builds_without_warnings(self):
        self.project()
        masters, instances = self.build()
        self.assertCleanBuild()
        self.assertEqual(set(masters), set(WATER_MASTERS))
        self.assertEqual(set(instances), set(SAMPLE_PALETTE))
        mp = self.unreal.MaterialProperty
        slw = self.unreal.MaterialShadingModel.MSM_SINGLE_LAYER_WATER
        for name in ("M_DA_Water", "M_DA_PoolWater", "M_DA_River"):
            mat = masters[name]
            self.assertEqual(mat.props["shading_model"], slw, name)
            for prop in (mp.MP_NORMAL, mp.MP_ROUGHNESS, mp.MP_BASE_COLOR, mp.MP_OPACITY):
                self.assertIn(prop, mat.outputs, f"{name}: {prop}")
            outputs = [e for e in mat.expressions if type(e).__name__.endswith("SingleLayerWaterMaterialOutput")]
            self.assertEqual(len(outputs), 1, name)
            self.assertEqual(set(outputs[0].inputs), {"Scattering Coefficients", "Absorption Coefficients", "Phase G"})
        ocean = masters["M_DA_Water"]
        self.assertIn(mp.MP_WORLD_POSITION_OFFSET, ocean.outputs)
        self.assertIs(ocean.props["tangent_space_normal"], False, "the wave normal is a world-space normal")
        self.assertIs(masters["M_DA_PoolWater"].props["tangent_space_normal"], True)
        # kinds resolve to the right masters
        self.assertIs(instances["M_FountainWater"].parent, masters["M_DA_PoolWater"])
        self.assertIs(instances["M_River"].parent, masters["M_DA_River"])
        self.assertIs(instances["M_Waterfall"].parent, masters["M_DA_Waterfall"])
        self.assertIs(instances["M_Ocean"].parent, ocean)
        self.assertIs(instances["M_LakeWater"].parent, ocean)
        # plain still water of the old "water" kind (no waves, no shoreline) rides the pool master, rings off
        legacy = instances["M_LegacyWater"]
        self.assertIs(legacy.parent, masters["M_DA_PoolWater"])
        self.assertEqual((legacy.scalars["Ripple"], legacy.scalars["WaveScale"]), (0.0, 0.004))
        self.assertEqual(instances["M_FountainWater"].scalars["Ripple"], 0.7)
        self.assertEqual(instances["M_River"].scalars["Flow"], 1.4)
        self.assertEqual(instances["M_Waterfall"].scalars, {"Opacity": 0.8})

    @unittest.skipUnless(REAL_PALETTE_JSON.exists(), "generated materials.json not present")
    def test_the_generated_palette_and_textures_build_cleanly(self):
        # The real hand-over: Data/materials.json + Data/water.json + whatever textures are on disk right now.
        palette = json.loads(REAL_PALETTE_JSON.read_text(encoding="utf-8"))
        kinds = ("water", "pool", "river", "waterfall", "flow", "terrain")
        palette = {name: spec for name, spec in palette.items() if spec.get("kind") in kinds}
        self.assertTrue(palette, "the palette has water materials")
        on_disk = sorted(p.stem for p in REAL_TEXTURES.glob("T_*.*") if p.suffix.lower() in (".png", ".jpg"))
        self.project(with_water=False, textures=on_disk)
        if REAL_WATER_JSON.exists():
            shutil.copy(REAL_WATER_JSON, Path(self.tmp.name) / "SourceAssets" / "Data" / "water.json")
        m = self.materials
        mpc = m.build_mpc()
        masters = {"M_DA_Water": m.build_water(), "M_DA_PoolWater": m.build_pool_water(), "M_DA_River": m.build_river(),
                   "M_DA_Waterfall": m.build_waterfall(), "M_DA_WaterFlow": m.build_water_flow(),
                   "M_DA_Terrain": m.build_terrain(mpc)}
        instances = m.build_instances(palette, masters)
        self.assertCleanBuild()
        self.assertEqual(set(instances), set(palette))
        for name, spec in palette.items():
            if spec.get("kind") == "water" and spec.get("waves") and REAL_WATER_JSON.exists():
                self.assertGreater(instances[name].scalars["FoldMax"], 1e-4, f"{name}: its wave set was found")

    def test_island_wide_maps_use_a_clamping_sampler(self):
        # outside the island the lookups must hold the edge value, not repeat the island's shoreline at sea
        self.project()
        masters, _ = self.build()
        clamp = self.unreal.SamplerSourceMode.SSM_CLAMP_WORLD_GROUP_SETTINGS
        seen = set()
        for mat in masters.values():
            for e in mat.expressions:
                tex = e.props.get("texture") if hasattr(e, "props") else None
                if tex is not None and tex.name in ("T_WaveMask", "T_WaterShore"):
                    self.assertEqual(e.props.get("sampler_source"), clamp, f"{mat.name}: {tex.name}")
                    seen.add((mat.name, tex.name))
        self.assertEqual(seen, {("M_DA_Water", "T_WaveMask"), ("M_DA_Water", "T_WaterShore"),
                                ("M_DA_Terrain", "T_WaterShore")})

    def test_builds_against_source_assets_from_before_the_upgrade(self):
        # no water.json, none of the new textures: everything still builds, the sea is simply flat
        self.project(with_water=False, textures=OLD_TEXTURES)
        masters, instances = self.build()
        self.assertCleanBuild()
        for position in ((0.0, 0.0, 0.0), (52000.0, -91000.0, 0.0)):
            self.assertEqual(self.evaluate(instances["M_Ocean"], "MP_WORLD_POSITION_OFFSET", position, 12.5),
                             (0.0, 0.0, 0.0))
        self.assertEqual(instances["M_Ocean"].scalars["Crest"], 0.0, "no waves: no whitecaps")
        self.assertIs(instances["M_LegacyWater"].parent, masters["M_DA_PoolWater"])
        # the optional graph parts are simply absent
        names = {e.props["texture"].name for e in masters["M_DA_Terrain"].expressions if e.props.get("texture")}
        self.assertNotIn("T_WaterShore", names)

    def test_pool_and_river_fall_back_to_still_water_without_their_masters(self):
        self.project()
        m = self.materials
        instances = m.build_instances({k: SAMPLE_PALETTE[k] for k in ("M_FountainWater", "M_River")},
                                      {"M_DA_Water": m.build_water()})
        self.assertCleanBuild()
        self.assertEqual({i.parent.name for i in instances.values()}, {"M_DA_Water"})

    # ------------------------------------------------------------------ the graph computes the contract
    def test_ocean_displacement_and_normal_match_the_reference(self):
        self.project()
        _, instances = self.build()
        ocean = instances["M_Ocean"]
        ocean.scalars["WaveStrength"] = 0.0          # detail normal layers off: the pure wave normal remains
        mask = (self.MASK_SIZE, ISLAND_MIN, ISLAND_MIN, ISLAND_MAX, ISLAND_MAX, self.mask)
        fade = (self.materials.WAVE_FADE_START, self.materials.WAVE_FADE_END)
        moved = 0
        for x, y, t in ((0.0, 0.0, 0.0), (31234.5, -48987.6, 3.25), (-95000.0, 30000.0, 17.5), (120000.0, 101000.0, 40.0),
                        (-150000.0, 5000.0, 12.0), (165000.0, 1000.0, 9.0), (-400000.0, 250000.0, 5.0)):
            m = ref_scale(mask, fade, x, y)
            want = ref_eval(OCEAN_WAVES, x, y, t, m)
            got = self.evaluate(ocean, "MP_WORLD_POSITION_OFFSET", (x, y, 0.0), t)
            for g, w in zip(got, want[:3]):
                self.assertAlmostEqual(g, w, delta=1e-6 * max(1.0, abs(w)) + 1e-7, msg=f"offset at {x}, {y}")
            length = math.sqrt(sum(c * c for c in want[3:6]))
            normal = self.evaluate(ocean, "MP_NORMAL", (x, y, 0.0), t)
            for g, w in zip(normal, want[3:6]):
                self.assertAlmostEqual(g, w / length, delta=1e-6, msg=f"normal at {x}, {y}")
            moved += abs(want[2]) > 1.0
        self.assertGreaterEqual(moved, 3)

    def test_lake_ignores_the_wave_mask_and_pads_unused_slots(self):
        self.project()
        _, instances = self.build()
        lake = instances["M_LakeWater"]
        self.assertEqual(lake.scalars["MaskAmount"], 0.0)
        x, y, t = 13000.0, -78000.0, 6.0
        want = ref_eval(LAKE_WAVES, x, y, t, 1.0)
        got = self.evaluate(lake, "MP_WORLD_POSITION_OFFSET", (x, y, 3000.0), t)
        for g, w in zip(got, want[:3]):
            self.assertAlmostEqual(g, w, delta=1e-6)
        for slot in range(len(LAKE_WAVES) + 1, self.materials.WAVE_SLOTS + 1):
            self.assertEqual(lake.vectors[f"Wave{slot}B"].rgba(), (0.0, 0.0, 0.0, 0.0), f"slot {slot} must not move")

    def test_fold_is_normalised_by_the_wave_set(self):
        slots, fold_max = self.materials.wave_slots(OCEAN_WAVES)
        self.assertEqual(len(slots), self.materials.WAVE_SLOTS)
        want = sum(TWO_PI / w["wavelength"] * w["steepness"] * w["amplitude"] for w in OCEAN_WAVES)
        self.assertAlmostEqual(fold_max, want, places=12)
        self.project()
        _, instances = self.build()
        self.assertAlmostEqual(instances["M_Ocean"].scalars["FoldMax"], want, places=12)
        self.assertEqual(instances["M_Ocean"].scalars["Crest"], 0.7)
        # a missing speed is the deep-water speed (same rule as ADAIslandManager's ConvertWave)
        a = slots[5][0]
        self.assertAlmostEqual(a[2], deep_water_speed(2400.0) / 2400.0, places=12)
        if REAL_WATER_JSON.exists():        # the pipeline's own bound, when the generated data is present
            real = json.loads(REAL_WATER_JSON.read_text(encoding="utf-8"))
            for body in ("ocean", "lake"):
                if "max_fold" in real.get(body, {}):
                    self.assertAlmostEqual(self.materials.wave_slots(real[body]["waves"])[1], real[body]["max_fold"],
                                           delta=2e-4, msg=body)

    def test_mirrored_level_mirrors_the_waves_and_the_mask_lookup(self):
        self.project()
        _, instances = self.build()
        self.assertEqual(self.materials.mirror_water_instances(SAMPLE_PALETTE, instances), 2)   # sea + lake
        self.assertCleanBuild()
        ocean = instances["M_Ocean"]
        self.assertEqual(ocean.scalars["MirrorY"], 1.0)
        mask = (self.MASK_SIZE, ISLAND_MIN, ISLAND_MIN, ISLAND_MAX, ISLAND_MAX, self.mask)
        x, y, t = 31234.5, -48987.6, 3.25
        # the mirrored level shows at (x, -y) what the unmirrored one shows at (x, y), with offset.y negated
        want = ref_eval(OCEAN_WAVES, x, y, t, ref_scale(mask, None, x, y))
        got = self.evaluate(ocean, "MP_WORLD_POSITION_OFFSET", (x, -y, 0.0), t)
        for g, w in zip(got, (want[0], -want[1], want[2])):
            self.assertAlmostEqual(g, w, delta=1e-6 * max(1.0, abs(w)))

    def test_crest_foam_only_on_the_peaks_and_shore_foam_only_near_the_shore(self):
        self.project()
        _, instances = self.build()
        ocean = instances["M_Ocean"]
        open_sea = lambda u, v: (1.0, 1.0, 1.0, 0.0)       # noqa: E731 - T_WaterShore far from any shore
        at_shore = lambda u, v: (0.0, 0.0, 1.0, 0.0)       # noqa: E731 - at the waterline
        full = lambda u, v: (1.0, 1.0, 1.0, 1.0)           # noqa: E731
        open_mask = lambda u, v: (1.0, 1.0, 1.0, 1.0)      # noqa: E731 - unsheltered water everywhere
        # rank many points of open water by the reference fold, then ask the graph about both ends of the range
        ranked = []
        for i in range(6000):
            x, y, t = 20000.0 + 137.0 * i, 30000.0 - 211.0 * i, 0.37 * i
            if max(abs(x), abs(y)) < self.materials.WAVE_FADE_START:
                ranked.append((ref_eval(OCEAN_WAVES, x, y, t, 1.0)[6] / ocean.scalars["FoldMax"], x, y, t))
        ranked.sort()
        self.assertGreater(ranked[-1][0], 0.7, "the sample should contain steep crests")
        folds = []
        for fold, x, y, t in ranked[:40] + ranked[len(ranked) // 2 - 20:len(ranked) // 2 + 20] + ranked[-40:]:
            foam = self.evaluate(ocean, "MP_OPACITY", (x, y, 0.0), t,
                                 textures={"T_WaterShore": open_sea, "T_WaterFoam": full, "T_WaveMask": open_mask})[0]
            folds.append((fold, foam))
        self.assertTrue(all(foam == 0.0 for f, foam in folds if f < 0.5), "no whitecaps below the top of the range")
        self.assertTrue(all(foam > 0.0 for f, foam in folds if f > 0.7), "the highest crests carry foam")
        self.assertTrue(all(0.0 <= foam <= 1.0 for _, foam in folds))
        # sheltered water (wave mask 0) never whitecaps
        calm = lambda u, v: (0.0, 0.0, 0.0, 1.0)           # noqa: E731
        _, x, y, t = ranked[-1]
        self.assertEqual(self.evaluate(ocean, "MP_OPACITY", (x, y, 0.0), t,
                                       textures={"T_WaterShore": open_sea, "T_WaterFoam": full, "T_WaveMask": calm})[0], 0.0)
        shore = self.evaluate(ocean, "MP_OPACITY", (-150000.0, 5000.0, 0.0), 1.0,
                              textures={"T_WaterShore": at_shore, "T_WaterFoam": full})[0]
        self.assertGreater(shore, 0.5, "a solid rim of foam at the waterline")

    def test_river_foam_follows_uv1_and_the_flow_moves_downstream(self):
        self.project()
        _, instances = self.build()
        river = instances["M_River"]
        full = {"T_WaterFoam": lambda u, v: (1.0, 1.0, 1.0, 1.0)}
        # UV1 after the FBX import: (foam, 1 - bank)
        calm = self.evaluate(river, "MP_OPACITY", (0.0, 0.0, 0.0), 2.0, uvs={0: (2.0, 30.0), 1: (0.0, 1.0)}, textures=full)[0]
        rapids = self.evaluate(river, "MP_OPACITY", (0.0, 0.0, 0.0), 2.0, uvs={0: (2.0, 30.0), 1: (1.0, 1.0)}, textures=full)[0]
        bank = self.evaluate(river, "MP_OPACITY", (0.0, 0.0, 0.0), 2.0, uvs={0: (0.0, 30.0), 1: (0.0, 0.0)}, textures=full)[0]
        self.assertEqual(calm, 0.0)
        self.assertGreater(rapids, 0.5)
        self.assertGreater(bank, 0.3)
        # The pattern seen at V now is the one that was at V + Flow * dt (the import flipped V: downstream = -V).
        ramp = {"T_WaterNormal": lambda u, v: (0.5, v % 1.0, 1.0, 1.0), "T_WaterDetailN": lambda u, v: (0.5, 0.5, 1.0, 1.0)}
        river.scalars["WaveStrength"] = 1.0
        now = self.evaluate(river, "MP_NORMAL", (0.0, 0.0, 0.0), 1.0, uvs={0: (1.0, 10.0), 1: (0.0, 1.0)}, textures=ramp)
        later = self.evaluate(river, "MP_NORMAL", (0.0, 0.0, 0.0), 1.5, uvs={0: (1.0, 10.0 - 1.4 * 0.5), 1: (0.0, 1.0)},
                              textures=ramp)
        for a, b in zip(now, later):
            self.assertAlmostEqual(a, b, places=9)

    def test_pool_rings_are_finite_and_switch_off(self):
        self.project()
        _, instances = self.build()
        pool = instances["M_FountainWater"]
        ring = {"T_Ripples": lambda u, v: (0.8, 0.9, 0.2, 0.35)}
        with_rings = self.evaluate(pool, "MP_NORMAL", (120.0, 340.0, 3400.0), 2.2, textures=ring)
        self.assertAlmostEqual(math.sqrt(sum(c * c for c in with_rings)), 1.0, places=9)
        self.assertNotEqual(with_rings[:2], (0.0, 0.0))
        pool.scalars["Ripple"] = 0.0
        pool.scalars["WaveStrength"] = 0.0
        self.assertEqual(self.evaluate(pool, "MP_NORMAL", (120.0, 340.0, 3400.0), 2.2, textures=ring), (0.0, 0.0, 1.0))

    def test_waterfall_shares_the_flow_graph_with_its_own_defaults(self):
        self.project()
        masters, _ = self.build()
        flow = masters["M_DA_WaterFlow"].parameters(self.unreal.MaterialExpressionScalarParameter)
        fall = masters["M_DA_Waterfall"].parameters(self.unreal.MaterialExpressionScalarParameter)
        self.assertEqual(set(flow), set(fall))
        self.assertEqual(set(flow), {param for _, param, _ in self.materials.FLOW_PARAMS})
        for key, param, default in self.materials.FLOW_PARAMS:      # the fountain defaults did not move
            self.assertEqual(flow[param].props["default_value"], default, param)
        self.assertGreater(fall["FlowSpeed"].props["default_value"], flow["FlowSpeed"].props["default_value"])
        self.assertGreater(fall["Opacity"].props["default_value"], flow["Opacity"].props["default_value"])


class WaterDataTests(unittest.TestCase):
    """water.json -> ADAIslandManager (level.py) and the texture import rules."""

    def setUp(self):
        self.level = load_editor_module("level")
        self.importer = load_editor_module("importer")

    def test_new_textures_import_with_the_contract_settings(self):
        kinds = {name: self.importer.texture_kind(name) for name in NEW_TEXTURES + ["T_WaterNormal", "T_WaterStreaks"]}
        self.assertEqual(kinds, {"T_WaterDetailN": "normal", "T_WaterFoam": "linear", "T_Caustics": "linear",
                                 "T_Ripples": "linear", "T_WaveMask": "masks", "T_WaterShore": "masks",
                                 "T_WaterNormal": "normal", "T_WaterStreaks": "linear"})
        # the island-wide maps are clamped (the MASKS set drives the address mode in import_textures)
        self.assertLessEqual({"T_WaveMask", "T_WaterShore"}, self.importer.MASKS)

    def test_wave_packing_matches_the_manager(self):
        packed = self.level.Placer.pack_waves(OCEAN_WAVES + [{"dir": [1, 0]}, {"oops": 1}])
        self.assertEqual(len(packed), 6 * 7, "6 waves at most, 7 floats each")
        w = OCEAN_WAVES[1]
        self.assertEqual(packed[7:14], [w["dir"][0], w["dir"][1], w["wavelength"], w["amplitude"], w["steepness"],
                                        w["speed"], w["phase"]])
        mirrored = self.level.Placer.pack_waves(OCEAN_WAVES, -1.0)
        self.assertEqual(mirrored[8], -w["dir"][1])
        self.assertEqual(mirrored[7], w["dir"][0])
        cpp = (SOURCE / "Private" / "DAIslandManager.cpp").read_text(encoding="utf-8")
        self.assertIn("constexpr int32 Stride = 7;", cpp)
        order = re.search(r"W\.Direction = FVector2D\(Packed\[i\], Packed\[i \+ 1\]\);\s*W\.Wavelength = Packed\[i \+ 2\];"
                          r"\s*W\.Amplitude = Packed\[i \+ 3\];\s*W\.Steepness = Packed\[i \+ 4\];"
                          r"\s*W\.Speed = Packed\[i \+ 5\];\s*W\.Phase = Packed\[i \+ 6\];", cpp)
        self.assertIsNotNone(order, "SetWaveSet must unpack dir, wavelength, amplitude, steepness, speed, phase")
        self.assertEqual(self.level.Placer.pack_waves(None), [])

    def test_mask_mirroring_reverses_the_rows(self):
        size = 4
        raw = bytes(range(size * size))
        flipped = base64.b64decode(self.level.Placer.mirror_mask(base64.b64encode(raw).decode("ascii"), size))
        self.assertEqual(flipped, bytes([12, 13, 14, 15, 8, 9, 10, 11, 4, 5, 6, 7, 0, 1, 2, 3]))
        self.assertIsNone(self.level.Placer.mirror_mask(base64.b64encode(raw).decode("ascii"), 5))

    @unittest.skipUnless(REAL_WATER_JSON.exists(), "generated water.json not present")
    def test_generated_water_json_has_the_shape_the_engine_reads(self):
        data = json.loads(REAL_WATER_JSON.read_text(encoding="utf-8"))
        for body in ("ocean", "lake"):
            waves = data[body]["waves"]
            self.assertTrue(1 <= len(waves) <= 6, body)
            self.assertEqual(len(self.level.Placer.pack_waves(waves)), 7 * len(waves), body)
            for w in waves:
                self.assertAlmostEqual(math.hypot(*w["dir"]), 1.0, places=3)
        mask = data["wave_mask"]
        self.assertEqual(len(base64.b64decode(mask["data"])), mask["size"] ** 2)
        self.assertEqual((mask["min"], mask["max"]), ([ISLAND_MIN, ISLAND_MIN], [ISLAND_MAX, ISLAND_MAX]),
                         "M_DA_Water looks T_WaveMask up over the island domain")
        for river in data.get("rivers", []):
            self.assertTrue(all(len(p) == 4 and p[3] > 0.0 for p in river["points"]), river.get("id"))

    def test_engine_names_the_level_script_relies_on_exist_in_the_headers(self):
        manager = (SOURCE / "Public" / "DAIslandManager.h").read_text(encoding="utf-8")
        for fn in ("void ClearWaterData();", "void SetWaveSet(bool bLake, const TArray<float>& Packed);",
                   "bool SetWaveMaskBase64(const FString& Data, int32 Size, FVector2D Min, FVector2D Max);",
                   "void AddRiver(FName Id, const TArray<float>& PackedPoints);", "float WaveFadeStart", "float WaveFadeEnd"):
            self.assertIn(fn, manager)
        actors = (SOURCE / "Public" / "DAWorldActors.h").read_text(encoding="utf-8")
        for name in ("FVector JetVelocity", "float FloorZ", "float JetSpread", "\tJet,", "\tFireflies"):
            self.assertIn(name, actors)
        life = (SOURCE / "Public" / "DALifeActors.h").read_text(encoding="utf-8")
        for name in ("class DUELACADEMYISLAND_API ADASpinner", "FVector Axis", "float Rpm",
                     "class DUELACADEMYISLAND_API ADABirdFlock", "EDABirdKind Kind", "int32 Count", "float Radius",
                     "float Height", "\tGull,", "\tSongbird"):
            self.assertIn(name, life)
        level = (EDITOR_PY / "duel_academy" / "level.py").read_text(encoding="utf-8")
        for name in ("set_wave_set", "set_wave_mask_base64", "add_river", "clear_water_data", "jet_velocity=",
                     "floor_z=", "jet_spread=", 'native_class("DASpinner")', 'native_class("DABirdFlock")'):
            self.assertIn(name, level)


if __name__ == "__main__":
    unittest.main()
