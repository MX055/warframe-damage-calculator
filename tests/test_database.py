from __future__ import annotations

import unittest
from unittest.mock import patch

from warframe_damage_calculator import Dist, Melee, Primary, Secondary, load_upgrade, load_weapon
from warframe_damage_calculator.database import Database
from warframe_damage_calculator.states import MeleeState, PrimaryState, SecondaryState
from tester_helpers import make_database_fixture


class DatabaseTestCase(unittest.TestCase):
    def test_database_and_loaders(self) -> None:
        database, tempdir = make_database_fixture()
        self.addCleanup(tempdir.cleanup)

        mapping: dict[str, float] = {}
        Database.add(mapping, "impact", 1.5)
        Database.add(mapping, "impact", 0.5)
        self.assertAlmostEqual(mapping["impact"], 2.0)

        table, record = database.find(("secondary", "primary"), "Test Secondary")
        self.assertEqual(table, "secondary")
        self.assertIn("crit_damage", record)

        self.assertIsInstance(database.weapon("Test Melee"), Melee)
        self.assertIsInstance(database.weapon("Test Primary"), Primary)
        self.assertIsInstance(database.weapon("Test Secondary"), Secondary)

        melee = database.weapon("Test Melee")
        self.assertIsInstance(melee.base, MeleeState)
        self.assertAlmostEqual(melee.base.attack_speed, 2.0)
        self.assertEqual(melee.base.damage_dist, Dist(impact=10, slash=5))

        primary = database.weapon("Test Primary")
        self.assertIsInstance(primary.base, PrimaryState)
        self.assertTrue(primary.base.is_beam)
        self.assertEqual(primary.base.explosion_damage_dist, Dist(heat=4))

        secondary = database.weapon("Test Secondary")
        self.assertIsInstance(secondary.base, SecondaryState)
        self.assertFalse(secondary.base.is_beam)

        upgrade = database.upgrade("Test Mod")
        self.assertEqual(upgrade.damage_dist, Dist(impact=2))
        self.assertAlmostEqual(upgrade.base_damage, 1.0)
        self.assertAlmostEqual(upgrade.status_chance, 0.6)
        self.assertAlmostEqual(upgrade.crit_chance, 0.5)
        self.assertTrue(upgrade.fire_rate_lock)
        self.assertAlmostEqual(upgrade.multishot, 0.2)

        arcane = database.upgrade("Test Arcane")
        self.assertAlmostEqual(arcane.base_damage, 0.3)
        self.assertAlmostEqual(arcane.reload_speed, 0.25)

        with patch("warframe_damage_calculator.database.default_database", database):
            self.assertIsInstance(load_weapon("Test Primary"), Primary)
            self.assertIsInstance(load_weapon("Test Secondary"), Secondary)
            self.assertIsInstance(load_weapon("Test Melee"), Melee)
            self.assertEqual(load_upgrade("Test Mod").damage_dist, Dist(impact=2))

    def test_loaders_missing_name_suggestions(self) -> None:
        database, tempdir = make_database_fixture()
        self.addCleanup(tempdir.cleanup)

        with patch("warframe_damage_calculator.database.default_database", database):
            with self.assertRaisesRegex(SystemExit, r"ERROR: 'Test Primari' not found, did you mean 'Test Primary'\?"):
                load_weapon("Test Primari")

            with self.assertRaisesRegex(SystemExit, r"ERROR: 'Test Mdo' not found, did you mean 'Test Mod'\?"):
                load_upgrade("Test Mdo")

            with self.assertRaisesRegex(SystemExit, r"ERROR: 'Completely Unknown' not found"):
                load_weapon("Completely Unknown")

    def test_loaders_upgrade_rank_and_stack(self) -> None:
        database, tempdir = make_database_fixture()
        self.addCleanup(tempdir.cleanup)

        default_upgrade = database.upgrade("Test Mod")
        self.assertEqual(default_upgrade.damage_dist, Dist(impact=2))
        self.assertAlmostEqual(default_upgrade.base_damage, 1.0)
        self.assertAlmostEqual(default_upgrade.status_chance, 0.6)
        self.assertAlmostEqual(default_upgrade.crit_chance, 0.5)
        self.assertAlmostEqual(default_upgrade.multishot, 0.2)

        rank_zero = database.upgrade("Test Mod", rank=0)
        self.assertEqual(rank_zero.damage_dist, Dist(impact=0))
        self.assertAlmostEqual(rank_zero.base_damage, 0.0)
        self.assertAlmostEqual(rank_zero.status_chance, 0.0)
        self.assertAlmostEqual(rank_zero.crit_chance, 0.0)

        rank_one = database.upgrade("Test Mod", rank=1)
        self.assertEqual(rank_one.damage_dist, Dist(impact=1))
        self.assertAlmostEqual(rank_one.base_damage, 0.5)
        self.assertAlmostEqual(rank_one.status_chance, 0.3)
        self.assertAlmostEqual(rank_one.crit_chance, 0.25)

        with patch("builtins.print"):
            rank_clamped = database.upgrade("Test Mod", rank=9)
        self.assertEqual(rank_clamped.damage_dist, Dist(impact=2))
        self.assertAlmostEqual(rank_clamped.base_damage, 1.0)
        self.assertAlmostEqual(rank_clamped.status_chance, 0.9)
        self.assertAlmostEqual(rank_clamped.crit_chance, 0.5)

        stacks_zero = database.upgrade("Test Mod", stacks=0)
        self.assertEqual(stacks_zero.damage_dist, Dist(impact=2))
        self.assertAlmostEqual(stacks_zero.base_damage, 1.0)
        self.assertAlmostEqual(stacks_zero.status_chance, 0.0)
        self.assertAlmostEqual(stacks_zero.crit_chance, 0.5)

        stacks_two = database.upgrade("Test Mod", stacks=2)
        self.assertEqual(stacks_two.damage_dist, Dist(impact=2))
        self.assertAlmostEqual(stacks_two.base_damage, 1.0)
        self.assertAlmostEqual(stacks_two.status_chance, 0.4)
        self.assertAlmostEqual(stacks_two.crit_chance, 0.5)

        with patch("builtins.print"):
            stacks_clamped = database.upgrade("Test Mod", stacks=9)
        self.assertEqual(stacks_clamped.damage_dist, Dist(impact=2))
        self.assertAlmostEqual(stacks_clamped.base_damage, 1.0)
        self.assertAlmostEqual(stacks_clamped.status_chance, 1.8)
        self.assertAlmostEqual(stacks_clamped.crit_chance, 0.5)

        conditional_false = database.upgrade("Test Mod", conditional=False)
        self.assertEqual(conditional_false.damage_dist, Dist(impact=2))
        self.assertAlmostEqual(conditional_false.base_damage, 1.0)
        self.assertAlmostEqual(conditional_false.status_chance, 0.6)
        self.assertAlmostEqual(conditional_false.crit_chance, 0.0)

        conditional_true = database.upgrade("Test Mod", conditional=True)
        self.assertEqual(conditional_true.damage_dist, Dist(impact=2))
        self.assertAlmostEqual(conditional_true.base_damage, 1.0)
        self.assertAlmostEqual(conditional_true.status_chance, 0.6)
        self.assertAlmostEqual(conditional_true.crit_chance, 0.5)


if __name__ == "__main__":
    unittest.main()