from __future__ import annotations

import unittest

from warframe_damage_calculator import Dist, Upgrade
from tester_helpers import TestRanged


class RangedTestCase(unittest.TestCase):
    def test_ranged_pipeline(self) -> None:
        ranged = TestRanged(damage_dist=Dist(impact=10, slash=5), crit_chance=0.5, crit_damage=2.0, status_chance=0.25, weakpoint_damage=3.0, fire_rate=2.0, reload_speed=4.0, magazine_capacity=2, multishot=2.0)
        configured = ranged.configure(Upgrade())

        self.assertIs(configured, ranged)
        self.assertAlmostEqual(ranged.average_fire_rate(), 0.4)
        self.assertAlmostEqual(ranged.weakpoint_crit_probability_for_tier(1), 0.5)
        self.assertAlmostEqual(ranged.weakpoint_crit_probability_for_tier(2), 0.0)
        self.assertAlmostEqual(ranged.average_weakpoint_crit_multiplier(), 1.5)
        self.assertAlmostEqual(ranged.beam_dot_multiplier(), 1)
        self.assertAlmostEqual(ranged.flat_dph(), 45.0)
        self.assertAlmostEqual(ranged.flat_weakpoint_dph(), 135.0)
        self.assertAlmostEqual(ranged.flat_dotph(), 2.625)
        self.assertAlmostEqual(ranged.flat_weakpoint_dotph(), 2.625)
        self.assertAlmostEqual(ranged.flat_dps(), 18.0)
        self.assertAlmostEqual(ranged.flat_weakpoint_dps(), 54.0)
        self.assertAlmostEqual(ranged.total_weakpoint_dph(), 137.625)
        self.assertAlmostEqual(ranged.total_weakpoint_dps(), 55.05)

        beam = TestRanged(damage_dist=Dist(impact=10, slash=5), crit_chance=0.5, crit_damage=2.0, status_chance=0.25, weakpoint_damage=3.0, fire_rate=2.0, reload_speed=4.0, magazine_capacity=2, multishot=2.0, is_beam=True)
        beam.configure(Upgrade())
        self.assertAlmostEqual(beam.beam_dot_multiplier(), 2)
        self.assertAlmostEqual(beam.flat_dotph(), 5.25)

        internal_bleeding_low_fire_rate = TestRanged(damage_dist=Dist(impact=10, slash=5), crit_chance=0.5, crit_damage=2.0, status_chance=0.25, weakpoint_damage=3.0, fire_rate=2.0, reload_speed=4.0, magazine_capacity=2, multishot=2.0)
        internal_bleeding_low_fire_rate.configure(Upgrade(internal_bleeding=1.0))
        self.assertAlmostEqual(internal_bleeding_low_fire_rate.effective.internal_bleeding, 2.0)
        self.assertAlmostEqual(internal_bleeding_low_fire_rate.flat_dotph(), 34.125)

        internal_bleeding_high_fire_rate = TestRanged(damage_dist=Dist(impact=10, slash=5), crit_chance=0.5, crit_damage=2.0, status_chance=0.25, weakpoint_damage=3.0, fire_rate=3.0, reload_speed=4.0, magazine_capacity=2, multishot=2.0)
        internal_bleeding_high_fire_rate.configure(Upgrade(internal_bleeding=1.0))
        self.assertAlmostEqual(internal_bleeding_high_fire_rate.effective.internal_bleeding, 1.0)
        self.assertAlmostEqual(internal_bleeding_high_fire_rate.flat_dotph(), 18.375)

        summary = ranged.summary()
        self.assertIn("FIRE RATE:", summary)
        self.assertIn("TOTAL DPS | WEAKPOINT:", summary)


if __name__ == "__main__":
    unittest.main()