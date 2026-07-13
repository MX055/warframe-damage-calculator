from __future__ import annotations

import unittest

from warframe_damage_calculator import Build, Upgrade


class BuildTests(unittest.TestCase):
    def test_add_and_remove_upgrades(self) -> None:
        first = Upgrade(name="First")
        second = Upgrade(name="Second")
        self.assertEqual((Build(first) + second).upgrades, [first, second])
        self.assertEqual((Build(first, second) - first).upgrades, [second])

    def test_get_aggregates_numeric_stats(self) -> None:
        build = Build(Upgrade(stats={"base_damage": 1}), Upgrade(stats={"base_damage": 2}))
        self.assertEqual(build.get("base_damage"), 3)
        self.assertEqual(build.get("crit_chance"), 0)

    def test_boolean_stats_merge_with_or(self) -> None:
        build = Build(Upgrade(stats={"fire_rate_lock": False}), Upgrade(stats={"fire_rate_lock": True}))
        self.assertIs(build.get("fire_rate_lock"), True)

    def test_booleans_cannot_mix_with_numbers(self) -> None:
        build = Build(Upgrade(stats={"fire_rate_lock": False}), Upgrade(stats={"fire_rate_lock": 1}))
        with self.assertRaisesRegex(TypeError, "Cannot combine values"):
            build.aggregate()

    def test_only_upgrades_are_accepted(self) -> None:
        with self.assertRaisesRegex(TypeError, "Build only accepts Upgrade objects"):
            Build(object())


if __name__ == "__main__":
    unittest.main()
