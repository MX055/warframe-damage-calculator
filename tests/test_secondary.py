from __future__ import annotations

import unittest

from warframe_damage_calculator import Dist, Secondary, Upgrade


class SecondaryTestCase(unittest.TestCase):
    def test_secondary_pipeline(self) -> None:
        secondary = Secondary(damage_dist=Dist(impact=10, slash=5), crit_chance=0.95, crit_damage=2.0, status_chance=0.25, fire_rate=2.0, reload_speed=4.0, magazine_capacity=5, multishot=2.0)
        configured = secondary.configure(Upgrade(crit_chance=0.2, secondary_enervate=1))

        self.assertIs(configured, secondary)
        self.assertAlmostEqual(secondary.effective.secondary_enervate, 1)
        self.assertAlmostEqual(secondary.average_secondary_enervate_bonus(), 0.15852307452895675)
        self.assertAlmostEqual(secondary.average_weakpoint_secondary_enervate_bonus(), 0.15852307452895675)
        self.assertAlmostEqual(secondary.flat_dotph_for(secondary.effective.damage_dist, secondary.base.forced_procs, secondary.effective.crit_chance, secondary.average_crit_multiplier()), 4.022415380425674)

        internal_bleeding = Secondary(damage_dist=Dist(impact=10, slash=5), crit_chance=0.5, crit_damage=2.0, status_chance=0.25, fire_rate=2.0, reload_speed=4.0, magazine_capacity=5, multishot=2.0)
        internal_bleeding.configure(Upgrade(internal_bleeding=1.0))

        self.assertAlmostEqual(internal_bleeding.effective.internal_bleeding, 2.0)
        self.assertAlmostEqual(internal_bleeding.flat_dotph_for(internal_bleeding.effective.damage_dist, internal_bleeding.base.forced_procs, internal_bleeding.effective.crit_chance, internal_bleeding.average_crit_multiplier()), 34.125)


if __name__ == "__main__":
    unittest.main()