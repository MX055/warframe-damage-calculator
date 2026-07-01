from __future__ import annotations

import unittest

from warframe_damage_calculator.mechanics import dist
from warframe_damage_calculator.upgrade_models import Upgrade
from warframe_damage_calculator.weapon_models import Primary
from warframe_damage_calculator.calculators import PrimaryCalculator


class PrimaryTests(unittest.TestCase):
    def test_primary_specific_methods(self) -> None:
        weapon = Primary(damage_dist=dist(impact=20, slash=80), forced_procs=dist(impact=1, slash=1), explosion_damage_dist=dist(heat=20), crit_chance=0.8, crit_damage=2.4, status_chance=1.2, fire_rate=2.0, reload_speed=1.5, magazine_capacity=5, multishot=2.0)
        weapon.configure(Upgrade(primed_chamber=1.0, hunter_munitions=0.3, vigilante_bonus=0.05, internal_bleeding=0.7))
        calc = PrimaryCalculator(weapon)

        self.assertAlmostEqual(weapon.effective.primed_chamber, 1.0)
        self.assertAlmostEqual(weapon.effective.hunter_munitions, 0.3)
        self.assertAlmostEqual(weapon.effective.vigilante_bonus, 0.05)
        self.assertAlmostEqual(weapon.effective.internal_bleeding, 1.4)
        self.assertAlmostEqual(calc.average_primed_chamber_multiplier(), 1.2)

    def test_primary_raw_damage_formulas(self) -> None:
        weapon = Primary(damage_dist=dist(impact=40, slash=60), explosion_damage_dist=dist(heat=30), crit_chance=0.6, crit_damage=2.0, status_chance=0.2, fire_rate=3.0, reload_speed=1.0, magazine_capacity=10, multishot=1.5)
        weapon.configure(Upgrade(primed_chamber=0.5, base_damage=0.2, crit_damage=0.25))
        calc = PrimaryCalculator(weapon)

        self.assertAlmostEqual(calc.flat_dph(), 430.92)
        self.assertAlmostEqual(calc.flat_dps(), 994.4307692307693)

    def test_primary_dot_damage_formulas(self) -> None:
        weapon = Primary(damage_dist=dist(impact=25, slash=75), forced_procs=dist(impact=1, slash=1), explosion_damage_dist=dist(heat=30), explosion_forced_procs=dist(cold=1), crit_chance=0.9, crit_damage=2.4, status_chance=1.0, fire_rate=2.0, reload_speed=5.0, magazine_capacity=2, multishot=2.0, is_beam=True)
        weapon.configure(Upgrade(hunter_munitions=0.3, internal_bleeding=0.5, primed_chamber=0.4))
        calc = PrimaryCalculator(weapon)

        self.assertAlmostEqual(calc.flat_dotph(), 6014.9808)
        self.assertAlmostEqual(calc.flat_dotps(), 2004.9936)


if __name__ == "__main__":
    unittest.main()
