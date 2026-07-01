from __future__ import annotations

import unittest

from warframe_damage_calculator.mechanics import dist


class DistTests(unittest.TestCase):
    def test_dist_basic_properties_and_accessors(self) -> None:
        damage = dist(slash=30, impact=10)

        self.assertEqual(set(damage.dist.keys()), {"impact", "slash"})
        self.assertEqual(damage.total_damage, 40)
        self.assertEqual(damage.get("impact"), 10)
        self.assertEqual(damage.get("heat"), 0)

    def test_dist_addition_and_radd(self) -> None:
        first = dist(impact=10, slash=20)
        second = dist(impact=5, puncture=15)
        total = first + second
        summed = sum([first, second])

        self.assertEqual(total.get("impact"), 15)
        self.assertEqual(total.get("slash"), 20)
        self.assertEqual(total.get("puncture"), 15)
        self.assertEqual(total, summed)

    def test_dist_multiplication_and_iteration(self) -> None:
        damage = dist(impact=10, slash=20)
        left = damage * 2
        right = 3 * damage

        self.assertEqual(left.get("impact"), 20)
        self.assertEqual(right.get("slash"), 60)
        self.assertEqual(list(iter(damage)), [("impact", 10), ("slash", 20)])

    def test_dist_hash_str_and_repr(self) -> None:
        damage = dist(impact=10, slash=20)

        self.assertEqual(hash(damage), hash(dist(slash=20, impact=10)))
        self.assertIn("IMPACT: 10", str(damage))
        self.assertIn("dist(impact=10, slash=20)", repr(damage))

    def test_dist_combine_include_exclude_positive(self) -> None:
        damage = dist(impact=10, cold=15, heat=25, toxin=-5)
        combined = damage.combine()

        self.assertEqual(combined.get("impact"), 10)
        self.assertEqual(combined.get("blast"), 40)
        self.assertEqual(combined.get("toxin"), 0)

        elemental = damage.include({"cold", "heat", "toxin"})
        physical = damage.exclude({"cold", "heat", "toxin"})
        positive = damage.positive()

        self.assertEqual(elemental.total_damage, 35)
        self.assertEqual(physical.total_damage, 10)
        self.assertEqual(positive.get("toxin"), 0)

    def test_dist_weight_and_apply(self) -> None:
        base = dist(impact=40, heat=60)
        mod = dist(impact=0.5, heat=0.2, toxin=0.1)
        applied = base.apply(mod)

        self.assertAlmostEqual(base.weight("impact"), 0.4)
        self.assertAlmostEqual(applied.get("impact"), 60)
        self.assertAlmostEqual(applied.get("heat"), 80)
        self.assertAlmostEqual(applied.get("toxin"), 10)

    def test_dist_weight_returns_zero_for_empty_distribution(self) -> None:
        damage = dist()

        self.assertEqual(damage.total_damage, 0)
        self.assertEqual(damage.weight("impact"), 0.0)

    def test_dist_combine_with_odd_element_count_keeps_unpaired_element(self) -> None:
        damage = dist(cold=10, heat=20, toxin=30)
        combined = damage.combine()

        self.assertEqual(combined.get("blast"), 30)
        self.assertEqual(combined.get("toxin"), 30)


if __name__ == "__main__":
    unittest.main()
