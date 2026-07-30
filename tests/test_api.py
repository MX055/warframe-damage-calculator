import unittest
import warnings

from warframe_damage_calculator import Attack, AttackStats, Build, BuildCompatibilityWarning, Compatibility, Dist, Effect, Enemy, EnemyStats, Melee, Primary, UnimplementedUpgradeWarning, Upgrade, UpgradeStats, arsenal


class ApiTests(unittest.TestCase):
    def test_direct_objects_calculate_without_data_wrappers(self):
        weapon = Primary(name="Example", subtype="rifle", attacks=[Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), crit_chance=0.2, crit_damage=2, fire_rate=2))], magazine_size=10, reload_time=1)
        upgrade = Upgrade(name="Damage", stats=UpgradeStats(damage_bonus=Effect(1)))
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
        upgrade = Upgrade(name="Rifle", compatibility=Compatibility(subtypes=["rifle"]), stats=UpgradeStats(damage_bonus=Effect(1)))
        weapon = arsenal.weapon.get("Lato")
        baseline = weapon.results.main.effective.damage.total
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            weapon.configure(upgrade)
        self.assertTrue(caught)
        self.assertGreater(weapon.results.main.effective.damage.total, baseline)

    def test_compatibility_fields_do_not_match_other_weapon_fields(self):
        upgrade = Upgrade(name="Name only", compatibility=Compatibility(names=["pistol"]))
        with self.assertWarns(BuildCompatibilityWarning):
            arsenal.weapon.get("Lato").configure(upgrade)

    def test_unimplemented_upgrades_warn_once_and_do_not_apply(self):
        weapon = arsenal.weapon.get("Lato")
        baseline = weapon.results.main.final.total_dps
        unsupported = arsenal.upgrade.get("Cascadia Empowered")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            weapon.configure(unsupported)
            weapon.results.resolve()
            weapon.results.resolve()
        unimplemented = [warning for warning in caught if warning.category is UnimplementedUpgradeWarning]
        self.assertEqual(len(unimplemented), 1)
        self.assertFalse(unsupported.implemented)
        self.assertEqual(weapon.build[0].name, unsupported.name)
        self.assertFalse(weapon.build[0].implemented)
        self.assertEqual(weapon.results.main.final.total_dps, baseline)

    def test_evolution_manual_runtime_defaults_to_each_effect_cap(self):
        weapon = arsenal.weapon.get("Gorgon")
        self.assertEqual(weapon.runtime.reload_from_empty, 3)

    def test_expected_procs_include_forced_and_damage_proc_effects(self):
        attack = Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), forced_procs=Dist(impact=0.25), crit_chance=0.2, status_chance=0.5, multishot=2))
        upgrade = Upgrade(name="Proc effects", stats=UpgradeStats(
            puncture_proc=Effect(0.5),
            slash_proc=(
                Effect(1).automate(on='critical_hit', chance=0.3),
                Effect(1).automate(on='impact_status_proc', chance=0.35),
            ),
        ))
        result = Primary(name="Example", subtype="rifle", attacks=[attack]).configure(upgrade).results.main
        self.assertAlmostEqual(result.average.procs_per_shot, 3.2075)

    def test_formatters_cover_ranged_melee_and_contributions(self):
        ranged = arsenal.weapon.get("Braton").configure(Build(arsenal.upgrade.get("Serration")), Enemy(name="Test Target"))
        melee = arsenal.weapon.get("Bo Prime")
        self.assertIn("TOTAL DPS", ranged.format.summary())
        self.assertIn("ATTACK SPEED", melee.format.summary())
        self.assertIn("EXPECTED PROCS PER HIT", melee.format.summary())
        upgrades = ranged.format.upgrades()
        self.assertIn("Serration", upgrades)
        self.assertEqual(upgrades.splitlines()[0], "Braton - Normal Attack vs Test Target")

    def test_melee_slams_use_aoe_mass_and_show_density(self):
        for category in ("slam", "heavy_slam"):
            with self.subTest(category=category):
                slam = Melee(name="Slam", attacks=[Attack(name=category, category=category, stats=AttackStats(damage=Dist(impact=100), falloff={"start_range": 0, "end_range": 6, "final_multiplier": 0.5}))])
                result = slam.results.main
                summary = slam.format.summary()
                self.assertGreater(result.density.damage_mass, 0)
                self.assertIsNotNone(result.density.total_dph)
                self.assertIn("DAMAGE MASS", summary)
                self.assertNotIn("DAMAGE DENSITY", summary)
                self.assertIn("m³", summary)
                self.assertLess(summary.index("HIT MULTIPLIER"), summary.index("DAMAGE MASS"))
                self.assertLess(summary.index("AVERAGE FALLOFF MULTIPLIER"), summary.index("DAMAGE MASS"))
                self.assertLess(summary.index("DAMAGE MASS"), summary.index("EXPECTED PROCS PER HIT"))

    def test_summary_preserves_the_original_table_format(self):
        ranged = arsenal.weapon.get("Corinth Prime")
        summary = ranged.format.summary()
        lines = summary.splitlines()
        self.assertEqual(lines[1], "=" * len(lines[2]))
        self.assertEqual(lines[-1], lines[1])
        self.assertIn("FIRE RATE", summary)
        self.assertIn("rps", summary)
        self.assertIn("RELOAD TIME", summary)
        self.assertIn("MAGAZINE CAPACITY", summary)
        self.assertIn("EXPECTED PROCS PER SHOT", summary)
        self.assertLess(summary.index("HIT MULTIPLIER"), summary.index("AVERAGE FALLOFF MULTIPLIER"))
        self.assertLess(summary.index("AVERAGE FALLOFF MULTIPLIER"), summary.index("EXPECTED PROCS PER SHOT"))
        self.assertIn("WEAKPOINT DAMAGE", summary)
        self.assertNotIn("effective", lines[2])
        self.assertNotIn("EXPECTED PROCS/SHOT", summary)
        self.assertIn("ATTACK SPEED", arsenal.weapon.get("Bo Prime").format.summary())


if __name__ == "__main__": unittest.main()
