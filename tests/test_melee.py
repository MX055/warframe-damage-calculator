from __future__ import annotations

import unittest

from warframe_damage_calculator.models import Build, Melee, Upgrade, dist


class MeleeTests(unittest.TestCase):
    def test_melee_regression_snapshot_values(self) -> None:
        weapon = Melee(damage_dist=dist(slash=120, impact=30), forced_procs=dist(slash=0.25), crit_chance=0.55, crit_damage=2.1, status_chance=0.45, attack_speed=1.15)
        weapon.configure(Build(Upgrade(base_damage=1.2, multiplicative_base_damage=0.5, faction_damage=0.4, crit_chance=0.6, crit_damage=0.9, flat_crit_damage=0.4, status_chance=0.35, status_damage=0.25, attack_speed=0.3, melee_duplicate=0.35)))
        calc = weapon.stats

        self.assertAlmostEqual(calc.effective.attack_speed, 1.49500000)
        self.assertAlmostEqual(calc.effective.melee_duplicate, 0.35000000)
        self.assertAlmostEqual(calc.effective.melee_doughty, 0.00000000)
        self.assertAlmostEqual(calc.effective.crit_chance, 0.88000000)
        self.assertAlmostEqual(calc.effective.crit_damage, 4.39000000)
        self.assertAlmostEqual(calc.effective.status_chance, 0.60750000)
        self.assertAlmostEqual(calc.effective.total_damage, 495.00000000)
        self.assertAlmostEqual(calc.average_melee_duplicate_multiplier, 1.30800000)
        self.assertAlmostEqual(calc.flat_dph, 3610.54774080)
        self.assertAlmostEqual(calc.flat_dotph, 5158.89503396)
        self.assertAlmostEqual(calc.total_dps, 13110.31694827)

    def test_melee_raw_damage_formulas(self) -> None:
        weapon = Melee(damage_dist=dist(slash=80, impact=20), forced_procs=dist(slash=0.15), crit_chance=0.75, crit_damage=2.2, status_chance=0.0, attack_speed=1.4)
        weapon.configure(Build(Upgrade(base_damage=0.25, multiplicative_base_damage=0.4, faction_damage=0.55, melee_duplicate=0.1, flat_crit_damage=0.25)))
        calc = weapon.stats

        self.assertAlmostEqual(calc.flat_dph, 608.701953125)
        self.assertAlmostEqual(calc.flat_dps, 852.182734375)

        weapon = Melee(damage_dist=dist(impact=50, slash=50), forced_procs=dist(impact=0.1, slash=0.05), crit_chance=0.35, crit_damage=1.9, status_chance=0.25, attack_speed=0.95)
        weapon.configure(Build(Upgrade(base_damage=0.4, multiplicative_base_damage=0.2, faction_damage=0.3, melee_duplicate=0.25, crit_chance=0.5, crit_damage=0.6, flat_crit_damage=0.15)))
        calc = weapon.stats

        self.assertAlmostEqual(calc.flat_dph, 531.12798375)
        self.assertAlmostEqual(calc.flat_dps, 504.57158456)

    def test_melee_dot_damage_formulas(self) -> None:
        weapon = Melee(damage_dist=dist(slash=100), forced_procs=dist(slash=0.2), crit_chance=0.5, crit_damage=2.0, status_chance=0.5, attack_speed=1.2)
        weapon.configure(Build(Upgrade(status_damage=0.2, melee_duplicate=0.15, crit_chance=0.25, crit_damage=0.4)))
        calc = weapon.stats

        self.assertAlmostEqual(calc.flat_dotph, 292.8515625)
        self.assertAlmostEqual(calc.flat_dotps, 351.4218750)

        weapon = Melee(damage_dist=dist(slash=65, toxin=35), forced_procs=dist(slash=0.3, toxin=0.2), crit_chance=0.4, crit_damage=2.3, status_chance=0.85, attack_speed=1.05)
        weapon.configure(Build(Upgrade(status_damage=0.35, melee_duplicate=0.1, melee_doughty=0.2, crit_damage=0.45, faction_damage=0.2)))
        calc = weapon.stats

        self.assertAlmostEqual(calc.flat_dotph, 417.02510435)
        self.assertAlmostEqual(calc.flat_dotps, 437.87635957)

if __name__ == "__main__":
    unittest.main()
