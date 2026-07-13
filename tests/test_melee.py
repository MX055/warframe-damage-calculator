from __future__ import annotations

import unittest

from warframe_damage_calculator import Melee, Upgrade, arsenal


class MeleeTests(unittest.TestCase):
    def test_all_melee_weapons_construct_and_calculate(self) -> None:
        for name in arsenal.weapons["melee"]:
            with self.subTest(name=name):
                weapon = arsenal.get(name)
                self.assertIsInstance(weapon, Melee)
                weapon.stats.total_dps

    def test_sacrificial_set_condition_is_automatic(self) -> None:
        weapon = arsenal.get("Skana")
        pressure = arsenal.get("Sacrificial Pressure")
        steel = arsenal.get("Sacrificial Steel")
        self.assertIsInstance(weapon, Melee)
        self.assertIsInstance(pressure, Upgrade)
        self.assertIsInstance(steel, Upgrade)
        weapon.configure(pressure, steel)
        self.assertAlmostEqual(weapon.stats.resolved_build.get("base_damage"), 1.375)
        self.assertAlmostEqual(weapon.stats.resolved_build.get("crit_chance"), 2.75)


if __name__ == "__main__":
    unittest.main()
