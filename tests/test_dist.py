from __future__ import annotations

import unittest

from warframe_damage_calculator import Dist
from warframe_damage_calculator.constants import ELEMENTAL


class DistTestCase(unittest.TestCase):
    def test_dist_operations(self) -> None:
        damage = Dist(cold=1, impact=2, heat=3, toxin=-1)
        self.assertEqual(list(damage), [("cold", 1), ("impact", 2), ("heat", 3), ("toxin", -1)])
        self.assertEqual(str(damage), "COLD: 1, IMPACT: 2, HEAT: 3, TOXIN: -1")
        self.assertEqual(repr(damage), "dist(cold=1, impact=2, heat=3, toxin=-1)")
        self.assertEqual(damage.total_damage, 5)
        self.assertEqual(damage.get("missing"), 0)
        self.assertEqual(hash(damage), hash(Dist(impact=2, cold=1, heat=3, toxin=-1)))
        self.assertEqual(damage.include(ELEMENTAL), Dist(cold=1, heat=3, toxin=-1))
        self.assertEqual(damage.exclude(ELEMENTAL), Dist(impact=2))
        self.assertEqual(damage.positive(), Dist(impact=2, cold=1, heat=3))
        self.assertEqual(damage.combine(), Dist(impact=2, blast=4))
        self.assertAlmostEqual(damage.weight("impact"), 0.4)
        self.assertAlmostEqual(damage.weight("missing"), 0.0)

        self.assertEqual(damage + Dist(impact=1, electricity=2), Dist(impact=3, cold=1, heat=3, toxin=-1, electricity=2))
        self.assertEqual(sum([Dist(impact=1), Dist(cold=2)]), Dist(impact=1, cold=2))
        self.assertEqual(damage * 2, Dist(impact=4, cold=2, heat=6, toxin=-2))
        self.assertEqual(2 * Dist(impact=1, cold=2), Dist(impact=2, cold=4))
        self.assertEqual(damage.apply(Dist(impact=0.5, cold=0.2)), Dist(cold=2, impact=3, heat=3, toxin=-1))

    def test_empty_dist_edge_cases(self) -> None:
        empty = Dist()

        self.assertEqual(list(empty), [])
        self.assertEqual(str(empty), "")
        self.assertEqual(repr(empty), "dist()")
        self.assertEqual(empty.total_damage, 0)
        self.assertEqual(empty.weight("impact"), 0.0)
        self.assertEqual(empty.get("cold"), 0)
        self.assertEqual(empty.combine(), Dist())
        self.assertEqual(empty.positive(), Dist())
        self.assertEqual(empty.apply(Dist(impact=1, cold=1)), Dist(impact=0, cold=0))
        self.assertEqual(0 + empty, empty)

    def test_single_element_combine_and_zero_scaling(self) -> None:
        single_elemental = Dist(cold=5)
        mixed_damage = Dist(impact=2, toxin=3)

        self.assertEqual(single_elemental.combine(), Dist(cold=5))
        self.assertEqual(mixed_damage.combine(), Dist(impact=2, toxin=3))
        self.assertEqual(mixed_damage * 0, Dist(impact=0, toxin=0))
        self.assertEqual(0 * mixed_damage, Dist(impact=0, toxin=0))
        self.assertEqual(mixed_damage.apply(Dist(impact=0.5, toxin=0.2)), Dist(impact=3, toxin=4))
        self.assertEqual(mixed_damage.positive(), mixed_damage)


if __name__ == "__main__":
    unittest.main()