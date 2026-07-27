import unittest

from database_builder.reconstruct_database import validate_enemies
from warframe_damage_calculator import Build, Enemy, Melee, Primary, Upgrade, arsenal
from warframe_damage_calculator.calculators import target_calculator
from warframe_damage_calculator.loader.construction import DatabaseFactory


factory = DatabaseFactory()


def weapon(damage, *, status_chance=0, forced_procs=None):
    data = {"name": "Target Test", "type": "primary", "ammo": {"magazine_size": 10, "reload_time": 1}, "attacks": {"normal": {"stats": {"damage": damage, "forced_procs": forced_procs or {}, "crit_chance": 0, "crit_damage": 1, "status_chance": status_chance, "fire_rate": 1, "multishot": 1}}}}
    data["runtime"] = factory._default_weapon_runtime(data)
    return Primary(data)


def enemy(*, health=100, shields=0, armor=0, overguard=0, faction="Neutral", bodyparts=None, modifiers=None):
    return Enemy({"name": "Target", "faction": faction, "base_level": 1, "stats": {"health": health, "shields": shields, "armor": armor, "overguard": overguard}, "bodyparts": bodyparts or {"body": {"type": "normal", "multiplier": 1}}, "modifiers": modifiers or {}, "runtime": {"level": 1, "steel_path": False, "empowered": False}})


def upgrade(name, stats):
    data = {"name": name, "type": "primary", "stats": stats}
    data["runtime"] = factory._default_upgrade_runtime(data)
    return Upgrade(data)


class EnemyTargetTests(unittest.TestCase):
    def test_default_enemy_is_a_neutral_calculation_target(self):
        target = Enemy()
        self.assertEqual(Enemy({}).data, target.data)
        self.assertEqual(target.data.name, "Enemy")
        self.assertEqual(dict(target.data.runtime), {"level": 1, "steel_path": False, "empowered": False})
        self.assertEqual(dict(target.results.effective), {"health": 1.0, "shields": 0.0, "armor": 0, "overguard": 0.0})
        untargeted = weapon({"impact": 100})
        targeted = weapon({"impact": 100}).configure(target=target)
        self.assertAlmostEqual(targeted.results.main.final.flat_dph, untargeted.results.main.final.flat_dph)
        self.assertIsNone(targeted.results.main.final.flat_weakpoint_dph)
        self.assertIsNone(targeted.results.main.final.flat_resistant_dph)

    def test_weapon_configure_copies_and_preserves_target(self):
        source = enemy(health=100, armor=100)
        configured = weapon({"impact": 100}).configure(target=source)
        self.assertIsNot(configured.target, source)
        self.assertEqual(configured.target.data, source.data)
        configured.configure(Build())
        self.assertIsNotNone(configured.target)
        copied = configured.copy()
        self.assertIsNot(copied.target, configured.target)
        preserved = configured.target
        configured.configure(target=None)
        self.assertIs(configured.target, preserved)
        self.assertIsNotNone(copied.target)

    def test_target_runtime_mutation_recomputes_weapon_results(self):
        configured = weapon({"impact": 100}).configure(target=enemy(health=100, armor=100))
        before = configured.results.main.final.flat_dph
        configured.target.set({"level": 100})
        self.assertLess(configured.results.main.final.flat_dph, before)

    def test_weighted_shields_and_health(self):
        configured = weapon({"impact": 100}).configure(target=enemy(health=50, shields=50))
        self.assertAlmostEqual(configured.results.main.final.flat_dph, 75)

    def test_damage_type_modifiers_and_armor_apply_per_component(self):
        configured = weapon({"impact": 50, "corrosive": 50}).configure(target=enemy(health=100, armor=300, modifiers={"impact": 1.5, "corrosive": 0.5}))
        self.assertAlmostEqual(configured.results.main.final.flat_dph, 70)

    def test_target_selects_matching_faction_bonus(self):
        bonuses = Build(upgrade("Banes", {"grineer_damage": [{"value": 0.5}], "corpus_damage": [{"value": 1.0}]}))
        configured = weapon({"impact": 100}).configure(bonuses, enemy(faction="Grineer"))
        self.assertAlmostEqual(configured.results.main.final.flat_dph, 150)

    def test_bodypart_averages_and_weakpoint_bonus(self):
        parts = {
            "body": {"type": "normal", "multiplier": 1},
            "torso": {"type": "normal", "multiplier": 2},
            "head": {"type": "weakpoint", "multiplier": 3},
            "core": {"type": "weakpoint", "multiplier": 5},
            "legs": {"type": "resistant", "multiplier": 0.5},
            "shell": {"type": "resistant", "multiplier": 0.25},
        }
        configured = weapon({"impact": 100}).configure(Build(upgrade("Deadhead", {"weakpoint_damage": [{"value": 0.3}]})), enemy(bodyparts=parts))
        final = configured.results.main.final
        self.assertAlmostEqual(final.flat_dph, 150)
        self.assertAlmostEqual(final.flat_weakpoint_dph, 520)
        self.assertAlmostEqual(final.flat_resistant_dph, 37.5)

    def test_missing_hit_zone_categories_are_none_and_omitted_from_summary(self):
        final = weapon({"impact": 100}).configure(target=enemy()).results.main.final
        self.assertIsNone(final.flat_weakpoint_dph)
        self.assertIsNone(final.flat_resistant_dph)
        summary = weapon({"impact": 100}).configure(target=enemy()).format.summary()
        self.assertNotIn("None", summary)
        self.assertIn("(normal)", summary)
        total_dps = next(line for line in summary.splitlines() if line.startswith("TOTAL DPS"))
        self.assertNotIn("|", total_dps.split("|", 3)[-1])

    def test_normal_metrics_are_none_without_normal_bodyparts(self):
        parts = {"head": {"type": "weakpoint", "multiplier": 3}, "shell": {"type": "resistant", "multiplier": 0.5}}
        configured = weapon({"impact": 100}).configure(target=enemy(bodyparts=parts))
        final = configured.results.main.final
        self.assertIsNone(final.flat_dph)
        self.assertAlmostEqual(final.flat_weakpoint_dph, 300)
        self.assertAlmostEqual(final.flat_resistant_dph, 50)
        summary = configured.format.summary()
        self.assertNotIn("None", summary)
        self.assertIn("(weakpoint | resistant)", summary)

    def test_dot_damage_uses_hit_zones_and_overguard_immunity(self):
        parts = {"body": {"type": "normal", "multiplier": 1}, "head": {"type": "weakpoint", "multiplier": 3}, "legs": {"type": "resistant", "multiplier": 0.5}}
        final = weapon({"heat": 100}, status_chance=1).configure(target=enemy(bodyparts=parts)).results.main.final
        self.assertGreater(final.flat_dotph, 0)
        self.assertAlmostEqual(final.flat_weakpoint_dotph, final.flat_dotph * 3)
        self.assertAlmostEqual(final.flat_resistant_dotph, final.flat_dotph * 0.5)
        guarded = weapon({"heat": 100}, status_chance=1).configure(target=enemy(health=0, overguard=100, bodyparts=parts)).results.main.final
        self.assertEqual(guarded.flat_dotph, 0)

    def test_melee_and_child_attacks_produce_target_hit_zone_metrics(self):
        parts = {"body": {"type": "normal", "multiplier": 1}, "head": {"type": "weakpoint", "multiplier": 3}, "legs": {"type": "resistant", "multiplier": 0.5}}
        melee_data = {"name": "Melee Target", "type": "melee", "attacks": {"normal": {"stats": {"damage": {"impact": 100}, "crit_chance": 0, "crit_damage": 1, "status_chance": 0, "attack_speed": 1}}}}
        melee_data["runtime"] = factory._default_weapon_runtime(melee_data)
        melee = Melee(melee_data).configure(target=enemy(bodyparts=parts)).results.main.final
        self.assertAlmostEqual(melee.flat_weakpoint_dph, melee.flat_dph * 3)
        self.assertAlmostEqual(melee.flat_resistant_dph, melee.flat_dph * 0.5)

        child_data = {"name": "Tree Target", "type": "primary", "attacks": {"normal": {"children": ["explosion"], "stats": {"damage": {"impact": 100}, "crit_chance": 0, "crit_damage": 1, "status_chance": 0, "fire_rate": 1, "multishot": 1}}, "explosion": {"stats": {"damage": {"impact": 50}, "crit_chance": 0, "crit_damage": 1, "status_chance": 0, "fire_rate": 1, "multishot": 1}}}}
        child_data["runtime"] = factory._default_weapon_runtime(child_data)
        tree = Primary(child_data).configure(target=enemy(health=50, shields=50, bodyparts=parts)).results.main.final
        self.assertAlmostEqual(tree.flat_dph, 112.5)
        self.assertAlmostEqual(tree.flat_resistant_dph, 56.25)

    def test_magazine_effects_and_resistant_contributions_use_target(self):
        parts = {"body": {"type": "normal", "multiplier": 1}, "legs": {"type": "resistant", "multiplier": 0.5}}
        target = enemy(bodyparts=parts)
        base = arsenal.get("Vectis").configure(target=target)
        chamber = arsenal.get("Vectis").configure(Build(arsenal.get("Primed Chamber")), target)
        self.assertGreater(chamber.results.main.final.flat_resistant_dph, base.results.main.final.flat_resistant_dph)

        damage = upgrade("Damage", {"damage_bonus": [{"value": 0.5}]})
        configured = weapon({"impact": 100}).configure(Build(damage), target)
        contributions = configured.results.removal_contributions("total_resistant_dps")
        self.assertIn("Damage", contributions)
        self.assertGreater(contributions["Damage"], 0)

    def test_type_aware_defense_bypass_and_overguard(self):
        mixed = enemy(health=50, shields=50, armor=300)
        self.assertAlmostEqual(target_calculator.defense_multiplier(mixed, "impact"), 0.6)
        self.assertAlmostEqual(target_calculator.defense_multiplier(mixed, "toxin"), 0.7)
        self.assertAlmostEqual(target_calculator.defense_multiplier(mixed, "true"), 1)
        armored = enemy(health=100, armor=300)
        self.assertAlmostEqual(target_calculator.defense_multiplier(armored, "slash", dot=True), 1)
        guarded = enemy(health=0, overguard=100)
        self.assertAlmostEqual(target_calculator.defense_multiplier(guarded, "impact"), 1)
        self.assertAlmostEqual(target_calculator.defense_multiplier(guarded, "void"), 1.5)
        self.assertAlmostEqual(target_calculator.defense_multiplier(guarded, "heat", dot=True), 0)

    def test_viral_status_amplifies_health_but_not_shields(self):
        health = weapon({"impact": 100}, forced_procs={"viral": 1}).configure(target=enemy(health=100)).results.main
        shields = weapon({"impact": 100}, forced_procs={"viral": 1}).configure(target=enemy(health=0, shields=100)).results.main
        self.assertEqual(health.status_effects.viral, 6)
        self.assertAlmostEqual(health.final.flat_dph, 325)
        self.assertAlmostEqual(shields.final.flat_dph, 50)

    def test_magnetic_status_amplifies_shields_and_overguard(self):
        shields = weapon({"impact": 100}, forced_procs={"magnetic": 1}).configure(target=enemy(health=0, shields=100)).results.main
        overguard = weapon({"impact": 100}, forced_procs={"magnetic": 1}).configure(target=enemy(health=0, overguard=100)).results.main
        health = weapon({"impact": 100}, forced_procs={"magnetic": 1}).configure(target=enemy(health=100)).results.main
        self.assertEqual(shields.status_effects.magnetic, 6)
        self.assertAlmostEqual(shields.final.flat_dph, 162.5)
        self.assertAlmostEqual(overguard.final.flat_dph, 325)
        self.assertAlmostEqual(health.final.flat_dph, 100)

    def test_corrosive_and_heat_status_strip_armor_multiplicatively(self):
        corrosive = weapon({"impact": 100}, forced_procs={"corrosive": 1}).configure(target=enemy(health=100, armor=300)).results.main
        heat = weapon({"impact": 100}, forced_procs={"heat": 1}).configure(target=enemy(health=100, armor=300)).results.main
        combined = weapon({"impact": 100}, forced_procs={"corrosive": 1, "heat": 1}).configure(target=enemy(health=100, armor=300)).results.main
        self.assertEqual(corrosive.status_effects.corrosive, 8)
        self.assertEqual(heat.status_effects.heat, 1)
        self.assertAlmostEqual(target_calculator.remaining_armor_multiplier(corrosive.status_effects), 0.32)
        self.assertAlmostEqual(target_calculator.remaining_armor_multiplier(heat.status_effects), 0.5)
        self.assertAlmostEqual(target_calculator.remaining_armor_multiplier(combined.status_effects), 0.16)
        self.assertGreater(corrosive.final.flat_dph, 70)
        self.assertGreater(heat.final.flat_dph, 70)
        self.assertGreater(combined.final.flat_dph, corrosive.final.flat_dph)
        self.assertGreater(combined.final.flat_dph, heat.final.flat_dph)

    def test_status_vulnerability_and_armor_strip_caps(self):
        self.assertEqual(target_calculator.status_vulnerability(0), 1)
        self.assertEqual(target_calculator.status_vulnerability(1), 2)
        self.assertEqual(target_calculator.status_vulnerability(10), 4.25)
        self.assertEqual(target_calculator.status_vulnerability(20), 4.25)
        self.assertEqual(target_calculator.corrosive_armor_strip(0), 0)
        self.assertEqual(target_calculator.corrosive_armor_strip(1), 0.26)
        self.assertAlmostEqual(target_calculator.corrosive_armor_strip(10), 0.8)

    def test_zero_pool_enemy_validation_fails(self):
        invalid = {"Unknown": {"name": "Unknown", "faction": "Unknown", "base_level": 1, "stats": {"health": 0, "shields": 0, "armor": 0, "overguard": 0}, "bodyparts": {"body": {"type": "normal", "multiplier": 1}}, "modifiers": {}}}
        with self.assertRaisesRegex(ValueError, "nonzero health, shields, or overguard"):
            validate_enemies(invalid)


if __name__ == "__main__":
    unittest.main()
