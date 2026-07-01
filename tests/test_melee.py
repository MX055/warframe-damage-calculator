from __future__ import annotations

import unittest

from warframe_damage_calculator.mechanics import dist
from warframe_damage_calculator.models import Melee, Upgrade


class MeleeTests(unittest.TestCase):
    def test_melee_specific_methods(self) -> None:
        weapon = Melee(damage_dist=dist(slash=100), crit_chance=0.5, crit_damage=2.0, status_chance=0.3, attack_speed=1.0)
        weapon.configure(Upgrade(attack_speed=0.5, melee_duplicate=0.2, base_damage=0.5, crit_damage=0.5, status_damage=0.25))

        self.assertAlmostEqual(weapon.effective.attack_speed, 1.5)
        self.assertAlmostEqual(weapon.average_melee_duplicate_multiplier(), 1.1)

    def test_melee_raw_damage_formulas(self) -> None:
        weapon = Melee(damage_dist=dist(slash=80, impact=20), crit_chance=0.75, crit_damage=2.2, status_chance=0.0, attack_speed=1.4)
        weapon.configure(Upgrade(base_damage=0.25, faction_damage=0.55, melee_duplicate=0.1))

        self.assertAlmostEqual(weapon.flat_dph(), 395.734375)
        self.assertAlmostEqual(weapon.flat_dps(), 554.028125)

    def test_melee_dot_damage_formulas(self) -> None:
        weapon = Melee(damage_dist=dist(slash=100), crit_chance=0.5, crit_damage=2.0, status_chance=0.5, attack_speed=1.2)
        weapon.configure(Upgrade(status_damage=0.2))

        self.assertAlmostEqual(weapon.flat_dotph(), 189.0)
        self.assertAlmostEqual(weapon.flat_dotps(), 226.8)

if __name__ == "__main__":
    unittest.main()
