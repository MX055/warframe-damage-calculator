from __future__ import annotations

import unittest

from warframe_damage_calculator import Build, Primary, Upgrade, arsenal
from warframe_damage_calculator.calculators import UpgradeResolver
from warframe_damage_calculator.models.dist import dist


class UpgradeResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.weapon = arsenal.get("Braton")
        self.assertIsInstance(self.weapon, Primary)

    def test_resolve_returns_build_and_merges_damage_types(self) -> None:
        build = Build(Upgrade(stats={"impact": 0.5}), Upgrade(stats={"heat": 0.25}))
        resolved = UpgradeResolver().resolve(self.weapon.stats.base, build)
        self.assertIsInstance(resolved, Build)
        self.assertEqual(resolved.get("damage"), dist(impact=0.5, heat=0.25))

    def test_rank_defaults_to_max_and_scales_from_context(self) -> None:
        maximum = arsenal.get("Critical Delay")
        rank_zero = arsenal.get("Critical Delay", context={"rank": 0})
        self.assertIsInstance(maximum, Upgrade)
        self.assertIsInstance(rank_zero, Upgrade)
        self.weapon.configure(maximum)
        maximum_value = self.weapon.stats.resolved_build.get("crit_chance")
        self.weapon.configure(rank_zero)
        self.assertAlmostEqual(self.weapon.stats.resolved_build.get("crit_chance"), maximum_value / (maximum.max_rank + 1))

    def test_conditions_and_stacks_default_to_active_and_max(self) -> None:
        upgrade = Upgrade(max_stacks=3, conditional_stats={"base_damage": (1, "active")}, stacking_stats={"crit_chance": (0.2, "stacks")})
        self.weapon.configure(upgrade)
        self.assertEqual(self.weapon.stats.resolved_build.get("base_damage"), 1)
        self.assertAlmostEqual(self.weapon.stats.resolved_build.get("crit_chance"), 0.6)

    def test_explicit_context_disables_omitted_conditions(self) -> None:
        upgrade = Upgrade(max_stacks=3, context={"active": False, "stacks": 1}, conditional_stats={"base_damage": (1, "active")}, stacking_stats={"crit_chance": (0.2, "stacks")})
        self.weapon.configure(upgrade)
        self.assertEqual(self.weapon.stats.resolved_build.get("base_damage"), 0)
        self.assertEqual(self.weapon.stats.resolved_build.get("crit_chance"), 0.2)

    def test_stack_count_is_capped(self) -> None:
        upgrade = Upgrade(max_stacks=3, context={"stacks": 10}, stacking_stats={"base_damage": (0.5, "stacks")})
        self.weapon.configure(upgrade)
        self.assertEqual(self.weapon.stats.resolved_build.get("base_damage"), 1.5)


if __name__ == "__main__":
    unittest.main()
