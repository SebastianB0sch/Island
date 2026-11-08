"""Tests for the optional Fab nature swapper (Tools/dai/fab_nature.py).

The module is pure Python so it runs without Unreal or Blender.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from dai import fab_nature  # noqa: E402


NATIVE_VEGETATION = {
    "SM_PalmTree_A", "SM_PalmTree_B",
    "SM_BroadTree_A", "SM_BroadTree_B", "SM_BroadTree_C",
    "SM_PineTree_A", "SM_DeadTree_A",
    "SM_Bush_A", "SM_Bush_B",
    "SM_FlowerBush_Red", "SM_FlowerBush_Yellow", "SM_FlowerBush_Blue", "SM_FlowerBush_White",
    "SM_Fern_A", "SM_GrassClump_A",
}


class FabNatureTests(unittest.TestCase):
    def test_all_native_vegetation_is_covered(self) -> None:
        self.assertEqual(set(fab_nature.REPLACE), NATIVE_VEGETATION)

    def test_every_variant_has_a_measured_asset(self) -> None:
        for native, spec in fab_nature.REPLACE.items():
            self.assertTrue(spec["variants"], native)
            for variant in spec["variants"]:
                self.assertIn(variant, fab_nature.ASSETS, f"{native} -> {variant}")
                asset = fab_nature.ASSETS[variant]
                self.assertTrue(asset["path"].startswith("/Game/"), variant)
                self.assertGreater(asset["height"], 0.0, variant)

    def test_translate_scales_from_native_target_height(self) -> None:
        groups, stats = fab_nature.translate({
            "SM_BroadTree_A": [[100.0, 200.0, 300.0, 45.0, 1.0]],
        })
        self.assertEqual(stats["SM_BroadTree_A"]["count"], 1)
        first = fab_nature.REPLACE["SM_BroadTree_A"]["variants"][0]
        group = groups[first]
        self.assertEqual(group["mesh"], fab_nature.ASSETS[first]["path"])
        expected = 12.0 / fab_nature.ASSETS[first]["height"]
        self.assertAlmostEqual(group["items"][0][4], round(expected, 3), places=3)
        self.assertTrue(group["collision"])
        self.assertEqual(group["cull"], [0, 0])
        self.assertTrue(group["shadow"])

    def test_translate_aligns_mesh_bottom_to_the_native_ground_line(self) -> None:
        groups, _ = fab_nature.translate({
            "SM_GrassClump_A": [[0.0, 0.0, 0.0, 0.0, 1.0]],
        })
        first = fab_nature.REPLACE["SM_GrassClump_A"]["variants"][0]
        asset = fab_nature.ASSETS[first]
        scale = 0.6 / asset["height"]
        item = groups[first]["items"][0]
        self.assertAlmostEqual(item[2], round(-asset["bottom"] * scale * 100.0, 1), places=1)
        self.assertFalse(groups[first]["collision"])
        self.assertFalse(groups[first]["shadow"])
        self.assertEqual(groups[first]["cull"], [3000, 6000])

    def test_variants_are_round_robin_and_groups_merge(self) -> None:
        variants = fab_nature.REPLACE["SM_BroadTree_B"]["variants"]
        self.assertEqual(len(variants), 2)
        groups, stats = fab_nature.translate({
            "SM_BroadTree_B": [
                [0.0, 0.0, 0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0, 0.0, 1.0],
                [2.0, 0.0, 0.0, 0.0, 1.0],
            ],
        })
        self.assertEqual(stats["SM_BroadTree_B"]["count"], 3)
        self.assertEqual(len(groups[variants[0]]["items"]), 2)
        self.assertEqual(len(groups[variants[1]]["items"]), 1)

    def test_available_requires_all_three_install_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(fab_nature.available(tmp))
            markers = fab_nature._INSTALL_MARKERS
            for marker in markers[:-1]:
                path = Path(tmp) / marker
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
            self.assertFalse(fab_nature.available(tmp))
            path = Path(tmp) / markers[-1]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x")
            self.assertTrue(fab_nature.available(tmp))

    def test_unknown_assets_are_left_alone(self) -> None:
        groups, stats = fab_nature.translate({
            "SM_Rock_A": [[0.0, 0.0, 0.0, 0.0, 1.0]],
        })
        self.assertEqual(groups, {})
        self.assertEqual(stats, {})

    def test_bush_and_flower_flags(self) -> None:
        groups, _ = fab_nature.translate({
            "SM_Bush_A": [[0.0, 0.0, 0.0, 0.0, 1.0]],
            "SM_FlowerBush_Red": [[0.0, 0.0, 0.0, 0.0, 1.0]],
            "SM_Fern_A": [[0.0, 0.0, 0.0, 0.0, 1.0]],
        })
        for group in groups.values():
            self.assertFalse(group["collision"])
        self.assertTrue(groups["SM_Fol_Bush_1"]["shadow"])
        self.assertTrue(groups["SM_Fol_Flower_Clump_1"]["shadow"])
        self.assertFalse(groups["SM_Fern"]["shadow"])


if __name__ == "__main__":
    unittest.main()
