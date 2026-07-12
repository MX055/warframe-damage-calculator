from __future__ import annotations
import unittest
from warframe_damage_calculator.models import Build, Secondary, Upgrade, dist

class SecondaryTests(unittest.TestCase):

    def test_secondary_regression_snapshot_values(self) -> None:
        weapon = Secondary(damage_dist=dist(impact=42, slash=58), forced_procs=dist(impact=0.2), explosion_damage_dist=dist(heat=15), crit_chance=0.42, crit_damage=2.4, status_chance=0.65, fire_rate=3.2, reload_speed=1.8, magazine_capacity=16, multishot=2.2, is_beam=True)
        weapon.configure(Build(Upgrade(stats={'base_damage': 0.85, 'multiplicative_base_damage': 0.6, 'crit_chance': 1.1, 'crit_damage': 0.75, 'flat_crit_damage': 0.35, 'status_chance': 0.45, 'status_damage': 0.5, 'fire_rate': 0.4, 'multishot': 0.95, 'reload_speed': 0.25, 'weakpoint_damage': 0.9, 'internal_bleeding': 0.7, 'secondary_enervate': 5, 'secondary_encumber': 0.2})))
        calc = weapon.stats
        self.assertAlmostEqual(calc.effective.fire_rate, 4.48)
        self.assertAlmostEqual(calc.effective.reload_speed, 1.44)
        self.assertAlmostEqual(calc.effective.multishot, 4.29)
        self.assertAlmostEqual(calc.effective.crit_chance, 0.882)
        self.assertAlmostEqual(calc.effective.weakpoint_crit_chance, 0.882)
        self.assertAlmostEqual(calc.effective.secondary_enervate, 5.0)
        self.assertAlmostEqual(calc.effective.secondary_encumber, 0.2)
        self.assertAlmostEqual(calc.effective.internal_bleeding, 0.7)
        self.assertAlmostEqual(calc.average_secondary_enervate_bonus, 0.53945684)
        self.assertAlmostEqual(calc.average_weakpoint_secondary_enervate_bonus, 0.53945684)
        self.assertAlmostEqual(calc.flat_dph, 7845.45206385)
        self.assertAlmostEqual(calc.flat_dotph, 81254.17600222)
        self.assertAlmostEqual(calc.total_weakpoint_dps, 292552.47445696)

    def test_secondary_raw_damage_formulas(self) -> None:
        weapon = Secondary(damage_dist=dist(impact=30, slash=70), forced_procs=dist(impact=0.2), explosion_damage_dist=dist(heat=20), explosion_forced_procs=dist(heat=0.3), crit_chance=0.6, crit_damage=2.0, status_chance=0.4, fire_rate=2.5, burst_count=2, burst_delay=0.06, charge_time=0.08, reload_speed=1.2, magazine_capacity=12, multishot=1.8, weakpoint_damage=2.7)
        weapon.configure(Build(Upgrade(stats={'base_damage': 0.2, 'crit_damage': 0.25, 'multishot': 0.4, 'fire_rate': 0.2, 'secondary_enervate': 3})))
        calc = weapon.stats
        self.assertAlmostEqual(calc.flat_dph, 896.88516961)
        self.assertAlmostEqual(calc.flat_dps, 3017.55758001)
        weapon = Secondary(damage_dist=dist(impact=20, puncture=30, slash=50), forced_procs=dist(impact=0.1, puncture=0.1), explosion_damage_dist=dist(heat=12), explosion_forced_procs=dist(heat=0.15), crit_chance=0.48, crit_damage=2.1, status_chance=0.55, fire_rate=3.8, burst_count=2, burst_delay=0.03, charge_time=0.06, reload_speed=1.4, magazine_capacity=20, multishot=2.4, weakpoint_damage=2.6)
        weapon.configure(Build(Upgrade(stats={'base_damage': 0.45, 'crit_damage': 0.35, 'multishot': 0.55, 'fire_rate': 0.3, 'secondary_enervate': 4, 'faction_damage': 0.15})))
        calc = weapon.stats
        self.assertAlmostEqual(calc.flat_dph, 2008.27986626)
        self.assertAlmostEqual(calc.flat_dps, 10261.58723555)

    def test_ranged_fire_rate_lock_blocks_fire_rate_mods(self) -> None:
        weapon = Secondary(damage_dist=dist(impact=100), fire_rate=4.0, burst_delay=0.2, charge_time=0.5, magazine_capacity=10)
        weapon.configure(Build(Upgrade(stats={'fire_rate': 0.5, 'multiplicative_fire_rate': 0.5, 'fire_rate_lock': True})))
        calc = weapon.stats
        self.assertAlmostEqual(calc.effective.fire_rate, 4.0)
        self.assertAlmostEqual(calc.effective.burst_delay, 0.2)
        self.assertAlmostEqual(calc.effective.charge_time, 0.5)

    def test_ranged_multishot_lock_blocks_multishot_mods(self) -> None:
        weapon = Secondary(damage_dist=dist(impact=100), multishot=2.0, magazine_capacity=10)
        weapon.configure(Build(Upgrade(stats={'multishot': 1.5, 'multishot_lock': True})))
        self.assertAlmostEqual(weapon.stats.effective.multishot, 2.0)

    def test_secondary_dot_damage_formulas(self) -> None:
        weapon = Secondary(damage_dist=dist(impact=30, slash=70), forced_procs=dist(impact=0.1, slash=0.1), explosion_damage_dist=dist(heat=18), explosion_forced_procs=dist(cold=0.25), crit_chance=0.5, crit_damage=2.0, status_chance=0.7, fire_rate=2.5, burst_count=3, burst_delay=0.04, charge_time=0.09, reload_speed=1.2, magazine_capacity=12, multishot=2.0, weakpoint_damage=2.5, is_beam=True)
        weapon.configure(Build(Upgrade(stats={'internal_bleeding': 0.8, 'secondary_encumber': 0.12, 'status_damage': 0.25, 'multishot': 0.2, 'crit_damage': 0.3, 'faction_damage': 0.15, 'secondary_enervate': 2})))
        calc = weapon.stats
        self.assertAlmostEqual(calc.flat_dotph, 3737.70116301)
        self.assertAlmostEqual(calc.flat_dotps, 16735.97535677)
        weapon = Secondary(damage_dist=dist(impact=22, slash=78), forced_procs=dist(impact=0.2, slash=0.2), explosion_damage_dist=dist(heat=20), explosion_forced_procs=dist(cold=0.4), crit_chance=0.62, crit_damage=2.6, status_chance=0.82, fire_rate=3.1, burst_count=4, burst_delay=0.02, charge_time=0.08, reload_speed=1.6, magazine_capacity=14, multishot=2.8, weakpoint_damage=3.0, is_beam=True)
        weapon.configure(Build(Upgrade(stats={'internal_bleeding': 0.9, 'secondary_encumber': 0.18, 'status_damage': 0.4, 'multishot': 0.35, 'crit_damage': 0.55, 'faction_damage': 0.25, 'secondary_enervate': 5})))
        calc = weapon.stats
        self.assertAlmostEqual(calc.flat_dotph, 33254.14130568)
        self.assertAlmostEqual(calc.flat_dotps, 206205.13397149)
if __name__ == '__main__':
    unittest.main()
