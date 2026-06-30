from __future__ import annotations

import unittest

from warframe_damage_calculator import Dist, Primary, Upgrade


class PrimaryTestCase(unittest.TestCase):
    def test_primary_pipeline(self) -> None:
        primary = Primary(damage_dist=Dist(impact=10, slash=5), crit_chance=0.5, crit_damage=2.0, status_chance=0.25, fire_rate=2.0, reload_speed=4.0, magazine_capacity=5, multishot=2.0)
        configured = primary.configure(Upgrade(primed_chamber=1.0, vigilante_bonus=0.05))

        self.assertIs(configured, primary)
        self.assertAlmostEqual(primary.average_primed_chamber_multiplier(), 1.2)
        self.assertAlmostEqual(primary.effective.crit_chance, 0.55)
        self.assertAlmostEqual(primary.effective.weakpoint_crit_chance, 0.55)
        self.assertAlmostEqual(primary.flat_dph(), 55.8)
        self.assertAlmostEqual(primary.flat_weakpoint_dph(), 167.4)
        self.assertAlmostEqual(primary.flat_dotph_for(primary.effective.damage_dist, primary.base.forced_procs, primary.effective.crit_chance, primary.average_crit_multiplier()), 3.255)

    def test_hunter_munitions_internal_bleeding_overlap(self) -> None:
        weapon = Primary(damage_dist=Dist(impact=10, slash=5), crit_chance=0.5, crit_damage=2.0, status_chance=0.75, fire_rate=3.0, reload_speed=4.0, magazine_capacity=5, multishot=2.0)
        weapon.configure(Upgrade(hunter_munitions=1.0, internal_bleeding=1.0))

        hunter_only = Primary(damage_dist=Dist(impact=10, slash=5), crit_chance=0.5, crit_damage=2.0, status_chance=0.75, fire_rate=3.0, reload_speed=4.0, magazine_capacity=5, multishot=2.0)
        hunter_only.configure(Upgrade(hunter_munitions=1.0))

        bleeding_only = Primary(damage_dist=Dist(impact=10, slash=5), crit_chance=0.5, crit_damage=2.0, status_chance=0.75, fire_rate=3.0, reload_speed=4.0, magazine_capacity=5, multishot=2.0)
        bleeding_only.configure(Upgrade(internal_bleeding=1.0))

        combined_dotph = weapon.flat_dotph_for(weapon.effective.damage_dist, weapon.base.forced_procs, weapon.effective.crit_chance, weapon.average_crit_multiplier())
        hunter_dotph = hunter_only.flat_dotph_for(hunter_only.effective.damage_dist, hunter_only.base.forced_procs, hunter_only.effective.crit_chance, hunter_only.average_crit_multiplier())
        bleeding_dotph = bleeding_only.flat_dotph_for(bleeding_only.effective.damage_dist, bleeding_only.base.forced_procs, bleeding_only.effective.crit_chance, bleeding_only.average_crit_multiplier())

        self.assertAlmostEqual(weapon.effective.hunter_munitions, 1.0)
        self.assertAlmostEqual(weapon.effective.internal_bleeding, 1.0)
        self.assertAlmostEqual(weapon.effective.fire_rate, 3.0)
        self.assertAlmostEqual(hunter_dotph, 70.875)
        self.assertAlmostEqual(bleeding_dotph, 55.125)
        self.assertAlmostEqual(combined_dotph, 94.5)
        self.assertLess(combined_dotph, hunter_dotph + bleeding_dotph)
        self.assertGreater(combined_dotph, hunter_dotph)
        self.assertGreater(combined_dotph, bleeding_dotph)


if __name__ == "__main__":
    unittest.main()