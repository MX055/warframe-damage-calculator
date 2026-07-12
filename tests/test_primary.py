from __future__ import annotations
import unittest
from warframe_damage_calculator.models import Build, Primary, Upgrade, dist

class PrimaryTests(unittest.TestCase):

    def test_primary_regression_snapshot_values(self) -> None:
        weapon = Primary(damage_dist=dist(impact=25.2, puncture=37.8, slash=27), fire_rate=1.42, reload_speed=3.0, magazine_capacity=20, multishot=6.0, crit_chance=0.3, crit_damage=2.8, status_chance=0.09, is_beam=True)
        weapon.configure(Build(Upgrade(stats={'impact': -0.886, 'crit_damage': 0.855, 'multishot': 1.126, 'crit_chance': 0.887}), Upgrade(stats={'multishot': 1.1 + 0.3 * 4}), Upgrade(stats={'base_damage': 2.4}), Upgrade(stats={'hunter_munitions': 0.3}), Upgrade(stats={'cold': 1.65}), Upgrade(stats={'crit_damage': 1.1}), Upgrade(stats={'crit_chance': 2.0}), Upgrade(stats={'toxin': 0.6, 'status_chance': 0.6}), Upgrade(stats={'vigilante_bonus': 0.05}), Upgrade(stats={'base_damage': 0.3 * 12, 'reload_speed': 0.3}), Upgrade(stats={'flat_crit_damage': 1.2})))
        calc = weapon.stats
        self.assertAlmostEqual(calc.effective.fire_rate, 1.42)
        self.assertAlmostEqual(calc.effective.reload_speed, 2.30769231)
        self.assertAlmostEqual(calc.effective.multishot, 26.556)
        self.assertAlmostEqual(calc.effective.crit_chance, 1.2161)
        self.assertAlmostEqual(calc.effective.weakpoint_crit_chance, 1.2161)
        self.assertAlmostEqual(calc.effective.status_chance, 0.144)
        self.assertAlmostEqual(calc.effective.hunter_munitions, 0.3)
        self.assertAlmostEqual(calc.effective.primed_chamber, 0.0)
        self.assertAlmostEqual(calc.effective.vigilante_bonus, 0.05)
        self.assertAlmostEqual(calc.effective.total_damage, 1891.2096)
        self.assertAlmostEqual(calc.average_primed_chamber_multiplier, 1.0)
        self.assertAlmostEqual(calc.flat_dph, 567782.20855901)
        self.assertAlmostEqual(calc.flat_dotph, 9544692.96695618)
        self.assertAlmostEqual(calc.total_dps, 13586338.5545859)

    def test_primary_raw_damage_formulas(self) -> None:
        weapon = Primary(damage_dist=dist(impact=40, slash=60), forced_procs=dist(impact=0.2), explosion_damage_dist=dist(heat=30), explosion_forced_procs=dist(heat=0.25), crit_chance=0.6, crit_damage=2.0, status_chance=0.2, fire_rate=3.0, burst_count=2, burst_delay=0.08, charge_time=0.12, reload_speed=1.0, magazine_capacity=10, multishot=1.5, weakpoint_damage=2.4)
        weapon.configure(Build(Upgrade(stats={'primed_chamber': 0.5, 'base_damage': 0.2, 'crit_damage': 0.25, 'multishot': 0.3, 'fire_rate': 0.2, 'weakpoint_crit_chance': 0.4})))
        calc = weapon.stats
        self.assertAlmostEqual(calc.flat_dph, 538.65)
        self.assertAlmostEqual(calc.flat_dps, 1829.37735849)
        weapon = Primary(damage_dist=dist(puncture=55, slash=45), forced_procs=dist(puncture=0.3), explosion_damage_dist=dist(heat=22), explosion_forced_procs=dist(heat=0.2), crit_chance=0.52, crit_damage=2.3, status_chance=0.28, fire_rate=2.3, burst_count=3, burst_delay=0.05, charge_time=0.07, reload_speed=2.1, magazine_capacity=18, multishot=2.2, weakpoint_damage=2.8)
        weapon.configure(Build(Upgrade(stats={'base_damage': 0.6, 'crit_damage': 0.4, 'multishot': 0.5, 'fire_rate': 0.15, 'weakpoint_crit_chance': 0.35, 'primed_chamber': 0.8, 'faction_damage': 0.25})))
        calc = weapon.stats
        self.assertAlmostEqual(calc.flat_dph, 1584.10638222)
        self.assertAlmostEqual(calc.flat_dps, 5846.23114279)

    def test_primary_dot_damage_formulas(self) -> None:
        weapon = Primary(damage_dist=dist(impact=25, slash=75), forced_procs=dist(impact=1, slash=1), explosion_damage_dist=dist(heat=30), explosion_forced_procs=dist(cold=1), crit_chance=0.9, crit_damage=2.4, status_chance=1.0, fire_rate=2.0, burst_count=3, burst_delay=0.05, charge_time=0.1, reload_speed=5.0, magazine_capacity=2, recharge_rate=2.5, is_battery=True, multishot=2.0, weakpoint_damage=2.6, is_beam=True)
        weapon.configure(Build(Upgrade(stats={'hunter_munitions': 0.3, 'internal_bleeding': 0.5, 'primed_chamber': 0.4, 'status_damage': 0.3, 'multishot': 0.5, 'faction_damage': 0.2})))
        calc = weapon.stats
        self.assertAlmostEqual(calc.flat_dotph, 24649.3181376)
        self.assertAlmostEqual(calc.flat_dotps, 15817.74425942)
        weapon = Primary(damage_dist=dist(impact=15, slash=85), forced_procs=dist(impact=0.6, slash=0.4), explosion_damage_dist=dist(heat=26), explosion_forced_procs=dist(cold=0.8), crit_chance=0.72, crit_damage=2.7, status_chance=0.95, fire_rate=1.8, burst_count=2, burst_delay=0.09, charge_time=0.14, reload_speed=3.7, magazine_capacity=6, multishot=2.6, weakpoint_damage=2.9, is_beam=True)
        weapon.configure(Build(Upgrade(stats={'hunter_munitions': 0.3, 'internal_bleeding': 0.6, 'primed_chamber': 0.9, 'status_damage': 0.4, 'multishot': 0.45, 'faction_damage': 0.35, 'crit_damage': 0.5})))
        calc = weapon.stats
        self.assertAlmostEqual(calc.flat_dotph, 55986.78887357)
        self.assertAlmostEqual(calc.flat_dotps, 85500.18662819)
if __name__ == '__main__':
    unittest.main()
