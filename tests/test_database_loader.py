from __future__ import annotations

import unittest

from warframe_damage_calculator import Melee, Primary, Secondary, dist, load_arcane, load_melee, load_mod, load_primary, load_secondary


class TestDatabaseLoader(unittest.TestCase):
    def test_loads_ranked_plain_mod(self):
        self.assertAlmostEqual(load_mod("Serration", rank=10).base_damage, 1.65)
        self.assertAlmostEqual(load_mod("serration", rank=0).base_damage, 0.15)

    def test_loads_stackable_mod(self):
        upgrade = load_mod("Galvanized Chamber", rank=10, stacks=5)
        self.assertAlmostEqual(upgrade.multishot, 0.80003 + 0.29997 * 5)

    def test_loads_max_rank_conditional_arcane(self):
        upgrade = load_arcane("Primary Merciless", rank=5, stacks=12)
        self.assertAlmostEqual(upgrade.base_damage, 0.3 * 12)
        self.assertAlmostEqual(upgrade.reload_speed, 0.3)

        unmaxed = load_arcane("Primary Merciless", rank=4, stacks=12)
        self.assertAlmostEqual(unmaxed.base_damage, 0.25 * 12)
        self.assertAlmostEqual(unmaxed.reload_speed, 0.0)

    def test_loads_damage_distribution(self):
        upgrade = load_mod("Hellfire", rank=5)
        self.assertEqual(upgrade.damage_dist, dist(heat=0.9))

    def test_rejects_invalid_rank_and_stacks(self):
        with self.assertRaises(ValueError):
            load_mod("Serration", rank=11)

        with self.assertRaises(ValueError):
            load_mod("Galvanized Chamber", rank=10, stacks=6)

    def test_kind_specific_lookup(self):
        with self.assertRaises(KeyError):
            load_arcane("Serration", rank=10)

        with self.assertRaises(KeyError):
            load_primary("Kuva Nukor")

    def test_loads_primary_weapon(self):
        weapon = load_primary("Corinth Prime")
        self.assertIsInstance(weapon, Primary)
        self.assertEqual(weapon.stats.base.damage_dist, dist(impact=25.2, puncture=37.8, slash=27))
        self.assertEqual(weapon.stats.base.magazine_capacity, 20)

    def test_loads_secondary_weapon(self):
        weapon = load_secondary("Kuva Nukor")
        self.assertIsInstance(weapon, Secondary)
        self.assertTrue(weapon.stats.base.is_beam)
        self.assertEqual(weapon.stats.base.damage_dist, dist(radiation=21))

    def test_loads_melee_weapon(self):
        weapon = load_melee("Paracesis")
        self.assertIsInstance(weapon, Melee)
        self.assertAlmostEqual(weapon.stats.base.attack_speed, 0.916667)
        self.assertEqual(weapon.stats.base.damage_dist, dist(impact=48.84, puncture=17.76, slash=155.4))


if __name__ == "__main__":
    unittest.main()