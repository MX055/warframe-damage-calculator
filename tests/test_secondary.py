from __future__ import annotations

import unittest

from warframe_damage_calculator.mechanics import dist
from warframe_damage_calculator.upgrade_models import Upgrade
from warframe_damage_calculator.weapon_models import Secondary
from warframe_damage_calculator.calculators import SecondaryCalculator


class SecondaryTests(unittest.TestCase):
    def test_secondary_specific_methods(self) -> None:
        disabled = Secondary(crit_chance=0.95)
        disabled.configure(Upgrade(secondary_enervate=0, weakpoint_crit_chance=0.5))
        disabled_calc = SecondaryCalculator(disabled)

        self.assertAlmostEqual(disabled_calc.average_secondary_enervate_bonus(), 0.0)
        self.assertAlmostEqual(disabled_calc.average_weakpoint_secondary_enervate_bonus(), 0.0)

        enabled = Secondary(crit_chance=0.40)
        enabled.configure(Upgrade(secondary_enervate=4, weakpoint_crit_chance=1.2))
        enabled_calc = SecondaryCalculator(enabled)

        self.assertAlmostEqual(enabled_calc.average_secondary_enervate_bonus(), 0.7242222499496438)
        self.assertAlmostEqual(enabled_calc.average_weakpoint_secondary_enervate_bonus(), 0.48690152992395375)

    def test_secondary_raw_damage_formulas(self) -> None:
        weapon = Secondary(damage_dist=dist(impact=30, slash=70), explosion_damage_dist=dist(heat=20), crit_chance=0.6, crit_damage=2.0, status_chance=0.4, fire_rate=2.5, reload_speed=1.2, magazine_capacity=12, multishot=1.8)
        weapon.configure(Upgrade(base_damage=0.2, crit_damage=0.25))
        calc = SecondaryCalculator(weapon)

        self.assertAlmostEqual(calc.flat_dph(), 456.0)
        self.assertAlmostEqual(calc.flat_dps(), 912.0)

    def test_secondary_dot_damage_formulas(self) -> None:
        weapon = Secondary(damage_dist=dist(impact=30, slash=70), forced_procs=dist(impact=0.1, slash=0.1), crit_chance=0.5, crit_damage=2.0, status_chance=0.7, fire_rate=2.5, reload_speed=1.2, magazine_capacity=12, multishot=2.0, is_beam=True)
        weapon.configure(Upgrade(internal_bleeding=0.8))
        calc = SecondaryCalculator(weapon)

        self.assertAlmostEqual(calc.flat_dotph(), 802.62)
        self.assertAlmostEqual(calc.flat_dotps(), 1605.24)


if __name__ == "__main__":
    unittest.main()
