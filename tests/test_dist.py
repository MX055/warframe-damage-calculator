from __future__ import annotations

import unittest

from warframe_damage_calculator.models.dist import dist


class DistributionTests(unittest.TestCase):
    def test_add_and_scale(self) -> None:
        damage = dist(impact=10) + dist(heat=5)
        self.assertEqual(damage, dist(impact=10, heat=5))
        self.assertEqual(damage * 2, dist(impact=20, heat=10))

    def test_total_weight_and_get(self) -> None:
        damage = dist(impact=30, slash=70)
        self.assertEqual(damage.total_damage(), 100)
        self.assertEqual(damage.get("puncture"), 0)
        self.assertAlmostEqual(damage.weight("slash"), 0.7)

    def test_include_exclude_and_positive(self) -> None:
        damage = dist(impact=10, slash=-5, heat=3)
        self.assertEqual(damage.include({"impact", "slash"}), dist(impact=10, slash=-5))
        self.assertEqual(damage.exclude({"heat"}), dist(impact=10, slash=-5))
        self.assertEqual(damage.positive(), dist(impact=10, heat=3))

    def test_apply_physical_and_elemental_upgrades(self) -> None:
        damage = dist(impact=60, slash=40)
        self.assertEqual(damage.apply(dist(impact=0.5, heat=0.9)), dist(impact=90, slash=40, heat=90))

    def test_combine_elements_in_order(self) -> None:
        self.assertEqual(dist(heat=10, cold=20).combine(), dist(blast=30))

    def test_invalid_constructor_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown damage types"):
            dist(unknown=1)
        with self.assertRaisesRegex(TypeError, "Damage values must be numeric"):
            dist(impact=True)


if __name__ == "__main__":
    unittest.main()
