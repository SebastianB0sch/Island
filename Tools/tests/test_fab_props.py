"""Tests for the optional Fab prop/rock swapper (Tools/dai/fab_props.py).

The module is pure Python so it runs without Unreal or Blender.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from dai import fab_props  # noqa: E402


NATIVE_GROUPS = {
    "SM_Rock_A", "SM_Rock_B", "SM_Rock_C", "SM_Rock_D",
    "SM_CliffRock_A", "SM_VolcanicRock_A", "SM_Pebbles_A",
    "SM_Bollard", "SM_Planter", "SM_VendingMachine",
    "SM_LampPost", "SM_TrashBin", "SM_BeachUmbrella", "SM_BeachChair",
}


class FabPropsTests(unittest.TestCase):
    def test_all_target_groups_are_covered(self) -> None:
        self.assertEqual(set(fab_props.REPLACE), NATIVE_GROUPS)

    def test_every_variant_has_a_measured_asset(self) -> None:
        for native, spec in fab_props.REPLACE.items():
            self.assertTrue(spec["variants"], native)
            for variant in spec["variants"]:
                self.assertIn(variant, fab_props.ASSETS, f"{native} -> {variant}")
                asset = fab_props.ASSETS[variant]
                self.assertTrue(asset["path"].startswith("/Game/"), variant)
                self.assertGreater(asset["height"], 0.0, variant)
                self.assertGreater(asset["width"], 0.0, variant)
                self.assertGreater(asset["depth"], 0.0, variant)

    def test_translate_preserves_native_flags(self) -> None:
        groups, stats = fab_props.translate({
            "SM_Bollard": dict(
                collision=False, cull=[6000, 9000], shadow=False, folder="Island/test",
                items=[[100.0, 200.0, 300.0, 45.0, 1.0]],
            ),
        })
        self.assertEqual(stats["SM_Bollard"]["count"], 1)
        group = groups["SM_ao336_lv1"]
        self.assertFalse(group["collision"])
        self.assertEqual(group["cull"], [6000, 9000])
        self.assertFalse(group["shadow"])
        self.assertEqual(group["folder"], "Island/test")

    def test_translate_aligns_mesh_bottom_to_the_native_ground_line(self) -> None:
        groups, _ = fab_props.translate({
            "SM_VendingMachine": dict(items=[[0.0, 0.0, 0.0, 0.0, 1.0]]),
        })
        asset = fab_props.ASSETS["SM_ao127_01"]
        scale = 1.9 / asset["height"]
        item = groups["SM_ao127_01"]["items"][0]
        self.assertAlmostEqual(item[2], round(-asset["bottom"] * scale * 100.0, 1), places=1)
        self.assertAlmostEqual(item[4], round(scale, 3), places=3)

    def test_translate_keeps_a_boulders_lean(self) -> None:
        groups, _ = fab_props.translate({
            "SM_Rock_A": dict(items=[[0.0, 0.0, 0.0, 30.0, 1.0, 12.5, -4.0], [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]]),
        })
        items = [it for g in groups.values() for it in g["items"]]
        self.assertEqual(sorted(tuple(it[5:]) for it in items), [(0.0, 0.0), (12.5, -4.0)])

    def test_rotation_offset_is_carried(self) -> None:
        groups, _ = fab_props.translate({
            "SM_LampPost": dict(items=[[0.0, 0.0, 0.0, 0.0, 1.0]]),
        })
        self.assertEqual(groups["SM_ao017_polelight_1_lv1"]["rot"], [0.0, 0.0, -90.0])

    def test_rocks_use_the_rock_category_flags(self) -> None:
        groups, _ = fab_props.translate({
            "SM_Rock_A": dict(items=[[0.0, 0.0, 0.0, 0.0, 1.0]]),
        })
        for group in groups.values():
            self.assertTrue(group["collision"])
            self.assertEqual(group["cull"], [0, 0])
            self.assertTrue(group["shadow"])

    def test_variants_are_round_robin_and_groups_merge(self) -> None:
        variants = fab_props.REPLACE["SM_Planter"]["variants"]
        self.assertEqual(len(variants), 2)
        groups, stats = fab_props.translate({
            "SM_Planter": dict(items=[
                [0.0, 0.0, 0.0, 0.0, 1.0],
                [1.0, 0.0, 0.0, 0.0, 1.0],
                [2.0, 0.0, 0.0, 0.0, 1.0],
            ]),
        })
        self.assertEqual(stats["SM_Planter"]["count"], 3)
        self.assertEqual(len(groups[variants[0]]["items"]), 2)
        self.assertEqual(len(groups[variants[1]]["items"]), 1)

    def test_available_requires_all_install_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(fab_props.available(tmp))
            markers = fab_props._INSTALL_MARKERS
            for marker in markers[:-1]:
                path = Path(tmp) / marker
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x")
            self.assertFalse(fab_props.available(tmp))
            path = Path(tmp) / markers[-1]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"x")
            self.assertTrue(fab_props.available(tmp))

    def test_remaining_procedural_groups_are_left_alone(self) -> None:
        groups, stats = fab_props.translate({
            "SM_Flagpole_Red": dict(items=[[0.0, 0.0, 0.0, 0.0, 1.0]]),
            "SM_DuelDummy": dict(items=[[0.0, 0.0, 0.0, 0.0, 1.0]]),
        })
        self.assertEqual(groups, {})
        self.assertEqual(stats, {})


if __name__ == "__main__":
    unittest.main()
