import unittest
import warnings

from warframe_damage_calculator import Attack, AttackStats, Build, Compatibility, Dist, Effect, Enemy, EnemyStats, Primary, Upgrade, UpgradeStats, arsenal


class ApiTests(unittest.TestCase):
    def test_direct_objects_calculate_without_data_wrappers(self):
        weapon = Primary(name="Example", subtype="rifle", attacks=[Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), crit_chance=0.2, crit_damage=2, fire_rate=2))], magazine_size=10, reload_time=1)
        upgrade = Upgrade(name="Damage", stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1})))
        weapon.configure(Build(upgrade))
        self.assertFalse(hasattr(weapon, "data"))
        self.assertFalse(hasattr(upgrade, "data"))
        self.assertGreater(weapon.results.main.final.total_dps, 0)

    def test_category_repositories_return_fresh_objects(self):
        first = arsenal.weapon.get("Corinth Prime")
        second = arsenal.weapon.get("corinth prime")
        self.assertIsNot(first, second)
        self.assertEqual(arsenal.upgrade.get("Serration").name, "Serration")
        self.assertEqual(arsenal.enemy.get("Heavy Gunner").name, "Heavy Gunner")

    def test_configuration_copies_build_and_target(self):
        build = Build(arsenal.upgrade.get("Serration"))
        target = Enemy(name="Target", faction="grineer", stats=EnemyStats(health=100, armor=100))
        weapon = arsenal.weapon.get("Braton").configure(build, target)
        self.assertIsNot(weapon.build, build)
        self.assertIsNot(weapon.target, target)
        self.assertGreater(weapon.results.main.final.total_dps, 0)

    def test_incompatible_effects_warn_but_apply(self):
        upgrade = Upgrade(name="Rifle", compatibility=Compatibility(subtypes=["rifle"]), stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1})))
        weapon = arsenal.weapon.get("Lato")
        baseline = weapon.results.main.effective.damage.total
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            weapon.configure(upgrade)
        self.assertTrue(caught)
        self.assertGreater(weapon.results.main.effective.damage.total, baseline)

    def test_evolution_manual_runtime_defaults_to_each_effect_cap(self):
        weapon = arsenal.weapon.get("Gorgon")
        self.assertEqual(weapon.runtime.reload_from_empty, 3)

    def test_formatters_cover_ranged_melee_and_contributions(self):
        ranged = arsenal.weapon.get("Braton").configure(Build(arsenal.upgrade.get("Serration")))
        melee = arsenal.weapon.get("Bo Prime")
        self.assertIn("TOTAL DPS", ranged.format.summary())
        self.assertIn("ATTACK SPEED", melee.format.summary())
        self.assertIn("Serration", ranged.format.upgrades())

    def test_summary_preserves_the_original_table_format(self):
        ranged = arsenal.weapon.get("Corinth Prime")
        summary = ranged.format.summary()
        lines = summary.splitlines()
        self.assertEqual(lines[1], "=" * len(lines[2]))
        self.assertEqual(lines[-1], lines[1])
        self.assertIn("FIRE RATE", summary)
        self.assertIn("rps", summary)
        self.assertIn("RELOAD SPEED", summary)
        self.assertIn("MAGAZINE CAPACITY", summary)
        self.assertIn("EXPECTED PROCS PER SHOT", summary)
        self.assertIn("WEAKPOINT DAMAGE", summary)
        self.assertNotIn("effective", lines[2])
        self.assertNotIn("EXPECTED PROCS/SHOT", summary)
        self.assertIn("ATTACK SPEED", arsenal.weapon.get("Bo Prime").format.summary())


if __name__ == "__main__": unittest.main()
