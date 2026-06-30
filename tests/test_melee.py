from __future__ import annotations

import unittest

from warframe_damage_calculator import Dist, Melee, Upgrade


class MeleeTestCase(unittest.TestCase):
    def test_melee_pipeline(self) -> None:
        melee = Melee(damage_dist=Dist(impact=10, slash=5), crit_chance=0.5, crit_damage=2.0, status_chance=0.25, attack_speed=2.0)
        configured = melee.configure(Upgrade(attack_speed=0.5, melee_duplicate=0.5, crit_chance=1.0, crit_damage=0.5, status_chance=1.0, base_damage=0.5))

        self.assertIs(configured, melee)
        self.assertAlmostEqual(melee.effective.attack_speed, 3.0)
        self.assertAlmostEqual(melee.effective.total_damage, 22.5)
        self.assertAlmostEqual(melee.average_duplicate_multiplier(), 2.5)
        self.assertAlmostEqual(melee.average_crit_multiplier(), 3.0)
        self.assertAlmostEqual(melee.crit_probability_for_tier(1), 1.0)
        self.assertAlmostEqual(melee.crit_probability_for_tier(2), 0.0)
        self.assertAlmostEqual(melee.crit_multiplier_for_tier(1), 3.0)
        self.assertAlmostEqual(melee.flat_dph(), 168.75)
        self.assertAlmostEqual(melee.flat_dotph(), 19.6875)
        self.assertAlmostEqual(melee.total_dph(), 188.4375)
        self.assertAlmostEqual(melee.flat_dps(), 506.25)
        self.assertAlmostEqual(melee.flat_dotps(), 59.0625)
        self.assertAlmostEqual(melee.total_dps(), 565.3125)

        summary = melee.summary()
        self.assertIn("ATTACK SPEED:", summary)
        self.assertIn("TOTAL DPS:", summary)


if __name__ == "__main__":
    unittest.main()