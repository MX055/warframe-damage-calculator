from __future__ import annotations

import unittest

from warframe_damage_calculator import Secondary, Upgrade, arsenal


class SecondaryTests(unittest.TestCase):
    def test_all_secondary_weapons_construct_and_calculate(self) -> None:
        for name in arsenal.weapons["secondary"]:
            with self.subTest(name=name):
                weapon = arsenal.get(name)
                self.assertIsInstance(weapon, Secondary)
                weapon.stats.total_dps

    def test_conjunction_voltage_uses_electricity_stacks(self) -> None:
        weapon = arsenal.get("Lato")
        voltage = arsenal.get("Conjunction Voltage", context={"electricity proc": 5})
        self.assertIsInstance(weapon, Secondary)
        self.assertIsInstance(voltage, Upgrade)
        weapon.configure(voltage)
        self.assertAlmostEqual(weapon.stats.resolved_build.get("multishot"), 0.15)
        self.assertAlmostEqual(weapon.stats.resolved_build.get("reload_speed"), 0.075)

    def test_secondary_shiver_uses_cold_stacks(self) -> None:
        weapon = arsenal.get("Lato")
        shiver = arsenal.get("Secondary Shiver", context={"cold proc": 10})
        self.assertIsInstance(weapon, Secondary)
        self.assertIsInstance(shiver, Upgrade)
        weapon.configure(shiver)
        self.assertAlmostEqual(weapon.stats.resolved_build.get("base_damage"), 4.5)


if __name__ == "__main__":
    unittest.main()
