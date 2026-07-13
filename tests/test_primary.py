from __future__ import annotations

import unittest

from warframe_damage_calculator import Primary, Upgrade, arsenal


class PrimaryTests(unittest.TestCase):
    def test_all_primary_weapons_construct_and_calculate(self) -> None:
        for name in arsenal.weapons["primary"]:
            with self.subTest(name=name):
                weapon = arsenal.get(name)
                self.assertIsInstance(weapon, Primary)
                weapon.stats.total_dps

    def test_primary_blight_uses_toxin_stacks(self) -> None:
        weapon = arsenal.get("Braton")
        blight = arsenal.get("Primary Blight", context={"toxin proc": 5})
        self.assertIsInstance(weapon, Primary)
        self.assertIsInstance(blight, Upgrade)
        weapon.configure(blight)
        self.assertAlmostEqual(weapon.stats.resolved_build.get("crit_damage"), 0.18)
        self.assertAlmostEqual(weapon.stats.resolved_build.get("multishot"), 0.09)


if __name__ == "__main__":
    unittest.main()
