import unittest

from warframe_damage_calculator import Build, Upgrade, arsenal


class UpgradeResolverTests(unittest.TestCase):
    def test_weapon_condition_is_automatic(self):
        upgrade = arsenal.get("Speed Trigger")

        bow = arsenal.get("Dread").configure(upgrade)
        rifle = arsenal.get("Braton").configure(upgrade)

        self.assertAlmostEqual(bow.stats.resolved_stats["fire_rate"], 1.2)
        self.assertAlmostEqual(rifle.stats.resolved_stats["fire_rate"], 0.6)

    def test_sacrificial_set_condition_is_automatic(self):
        pressure = arsenal.get("Sacrificial Pressure")
        steel = arsenal.get("Sacrificial Steel")

        solo = arsenal.get("Skana").configure(pressure)
        paired = arsenal.get("Skana").configure(Build(pressure, steel))

        self.assertAlmostEqual(solo.stats.resolved_stats["base_damage"], 1.1)
        self.assertAlmostEqual(paired.stats.resolved_stats["base_damage"], 1.375)

    def test_combat_condition_requires_manual_activation(self):
        upgrade = Upgrade(
            conditional_stats={"crit_chance": (0.5, "headshot")},
        )

        inactive = arsenal.get("Braton").configure(upgrade, context={})
        active = arsenal.get("Braton").configure(
            upgrade,
            context={"headshot": True},
        )

        self.assertNotIn("crit_chance", inactive.stats.resolved_stats)
        self.assertAlmostEqual(active.stats.resolved_stats["crit_chance"], 0.5)

    def test_missing_context_enables_conditions_by_default(self):
        upgrade = Upgrade(
            conditional_stats={"crit_chance": (0.5, "headshot")},
        )

        weapon = arsenal.get("Braton").configure(upgrade)

        self.assertAlmostEqual(weapon.stats.resolved_stats["crit_chance"], 0.5)

    def test_stacking_stat_uses_context_and_max_stacks(self):
        upgrade = Upgrade(
            name="Example Arcane",
            max_stacks=3,
            stacking_stats={"base_damage": (0.3, "kill")},
        )
        context = {"kill": 5}

        weapon = arsenal.get("Braton").configure(upgrade, context=context)

        self.assertAlmostEqual(weapon.stats.resolved_stats["base_damage"], 0.9)

    def test_database_stack_is_activated_by_stack_count(self):
        merciless = arsenal.get("Primary Merciless")
        context = {"stacks": 4}

        weapon = arsenal.get("Braton").configure(merciless, context=context)

        self.assertAlmostEqual(weapon.stats.resolved_stats["base_damage"], 1.2)
        self.assertAlmostEqual(weapon.stats.resolved_stats["reload_speed"], 0.3)

    def test_missing_context_uses_max_stacks_by_default(self):
        merciless = arsenal.get("Primary Merciless")

        weapon = arsenal.get("Braton").configure(merciless)

        self.assertAlmostEqual(weapon.stats.resolved_stats["base_damage"], 3.6)

    def test_stacking_upgrade_does_not_require_name(self):
        upgrade = Upgrade(stacking_stats={"base_damage": (0.3, "kill")})

        weapon = arsenal.get("Braton").configure(upgrade, context={"kill": 2})

        self.assertAlmostEqual(weapon.stats.resolved_stats["base_damage"], 0.6)

    def test_boolean_is_not_a_valid_stack_count(self):
        upgrade = Upgrade(stacking_stats={"base_damage": (0.3, "kill")})

        with self.assertRaises(ValueError):
            arsenal.get("Braton").configure(upgrade, context={"kill": True})


if __name__ == "__main__":
    unittest.main()
