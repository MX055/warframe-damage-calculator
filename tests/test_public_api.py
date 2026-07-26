import unittest
from collections.abc import Mapping
from types import MappingProxyType
from typing import get_args

from warframe_damage_calculator import Build, Enemy, Melee, Primary, Secondary, Upgrade, Weapon, arsenal
from warframe_damage_calculator.calculators import formulas
from warframe_damage_calculator.calculators.build_calculator import BuildCalculator
from warframe_damage_calculator.calculators.upgrade_calculator import UpgradeCalculator
from warframe_damage_calculator.calculators.weapon_calculator import WeaponCalculator
from warframe_damage_calculator.loader.bundled_names import EnemyName, MeleeName, PrimaryName, SecondaryName, UpgradeName
from warframe_damage_calculator.core.data import Data
from warframe_damage_calculator.core.dist import Dist
from warframe_damage_calculator.core.dist_data import DistData
from warframe_damage_calculator.fields.attack_result import AttackResult
from warframe_damage_calculator.fields.calculated import CalculatedStats
from warframe_damage_calculator.fields.enemy import BodyPart, BodyParts, EnemyData, EnemyModifiers, EnemyRuntime, EnemyStats
from warframe_damage_calculator.fields.upgrade import ResolvedStat
from warframe_damage_calculator.fields.weapon_data import Attack, Attacks, Evolutions
from warframe_damage_calculator.loader.construction import DatabaseFactory


factory = DatabaseFactory()


def runtime_upgrade(data):
    definition = dict(data)
    runtime = factory._default_upgrade_runtime(definition)
    runtime.update(definition.get("runtime", {}))
    definition["runtime"] = runtime
    return Upgrade(definition)


def runtime_weapon(model, data):
    definition = dict(data)
    runtime = factory._default_weapon_runtime(definition)
    runtime.update(definition.get("runtime", {}))
    definition["runtime"] = runtime
    return model(definition)


def galvanized_build() -> Build:
    return Build(
        arsenal.get("Galvanized Chamber", context={"on_kill": 5}),
        arsenal.get("Galvanized Aptitude", context={"on_kill": 2}),
    )


def selected(weapon: Weapon):
    return weapon.results.main


class DataDefaults(Data):
    children: list[Data] = []
    stats: CalculatedStats = CalculatedStats()
    label: str = "base"


class OverriddenDataDefaults(DataDefaults):
    children: list[Data] = [Data({"source": "override"})]
    label: str = "child"


class PublicApiTests(unittest.TestCase):
    def test_data_accepts_generic_mappings_and_converts_assignments(self):
        source = MappingProxyType({"nested": {"value": 1}, "extra": {"value": 2}})
        data = Data(source)

        self.assertIsInstance(data.nested, Data)
        self.assertIsInstance(data.extra, Data)
        self.assertIs(type(data.nested), Data)
        self.assertIs(type(data.extra), Data)
        data["item"] = {"value": 3}
        data.attribute = {"value": 4}
        self.assertIs(type(data.item), Data)
        self.assertIs(type(data.attribute), Data)

    def test_data_preserves_existing_subclasses_and_concrete_copy_type(self):
        stats = CalculatedStats()
        wrapped = Data({"stats": stats})
        original = OverriddenDataDefaults()
        copied = original.copy()

        self.assertIs(wrapped.stats, stats)
        self.assertIs(type(copied), OverriddenDataDefaults)
        self.assertIsNot(copied.children, original.children)
        self.assertIsNot(copied.children[0], original.children[0])
        self.assertIsNot(copied.stats, original.stats)

    def test_distribution_fields_use_dist_data(self):
        attack = Attack({"stats": {"damage": {"impact": 10}, "forced_procs": {"slash": 1}}})
        resolved = ResolvedStat()

        for distribution in (attack.stats.damage, attack.stats.forced_procs, CalculatedStats().damage, resolved.proportional.damage):
            self.assertIs(type(distribution), Dist)
            self.assertIs(type(distribution.data), DistData)

    def test_mutable_inherited_and_overridden_defaults_are_independent(self):
        first = OverriddenDataDefaults()
        second = OverriddenDataDefaults()

        first.children.append(Data({"source": "first"}))
        first.stats.damage = Dist({"impact": 100})
        self.assertEqual(first.label, "child")
        self.assertEqual(second.label, "child")
        self.assertEqual(len(second.children), 1)
        self.assertNotEqual(second.stats.damage, first.stats.damage)
        self.assertIsNot(first.children, second.children)
        self.assertIsNot(first.children[0], second.children[0])
        self.assertIsNot(first.stats, second.stats)

    def test_data_satisfies_mutable_mapping_deletion_iteration_and_length(self):
        data = Data({"first": 1, "second": 2})

        self.assertEqual(len(data), 2)
        self.assertEqual(list(iter(data)), ["first", "second"])
        del data["first"]
        self.assertEqual(len(data), 1)
        self.assertNotIn("first", data)

    def test_attack_result_defaults_and_copy_are_independent(self):
        first = AttackResult()
        second = AttackResult()

        first.children = ["child"]
        first.base.damage = Dist({"impact": 100})
        copied = first.copy()
        self.assertEqual(len(second.children), 0)
        self.assertNotEqual(second.base.damage, first.base.damage)
        self.assertIsInstance(first.build, ResolvedStat)
        self.assertIs(type(copied), AttackResult)
        self.assertEqual(copied.children, ["child"])
        self.assertIsNot(copied.children, first.children)

    def test_generic_weapon_uses_the_shared_calculation_pipeline(self):
        weapon = runtime_weapon(Weapon, {"name": "Test Weapon", "type": "test", "attacks": {"normal": {"stats": {"damage": {"impact": 10}}}}})

        self.assertEqual(selected(weapon).effective.damage.total_damage(), 10)
        self.assertEqual(len(selected(weapon).children), 0)
        self.assertEqual(weapon.data.attacks.normal.name, "normal")
        self.assertEqual(weapon.results.main.name, "normal")
        self.assertEqual(weapon.results.child, [])
        self.assertFalse(hasattr(weapon.results, "attacks"))

    def test_data_mapping_views_match_explicit_values(self):
        data = Data({"first": 1})
        keys = data.keys()
        values = data.values()
        items = data.items()

        self.assertEqual(repr(keys), "dict_keys(['first'])")
        self.assertEqual(list(values), [1])
        self.assertEqual(list(items), [("first", 1)])

        data["second"] = 2
        self.assertEqual(list(keys), ["first", "second"])
        self.assertEqual(list(values), [1, 2])
        self.assertEqual(list(items), [("first", 1), ("second", 2)])

    def test_generated_literal_names_match_database(self):
        expected = {
            PrimaryName: {data["name"] for data in arsenal.weapons.values() if data["type"] in {"primary", "archgun"}},
            SecondaryName: {data["name"] for data in arsenal.weapons.values() if data["type"] == "secondary"},
            MeleeName: {data["name"] for data in arsenal.weapons.values() if data["type"] == "melee"},
            UpgradeName: {data["name"] for data in arsenal.upgrades.values()},
            EnemyName: set(arsenal.enemies),
        }
        for alias, names in expected.items():
            self.assertEqual(set(get_args(alias.__value__)), names)

    def test_bundled_database_uses_explicit_effect_modes(self):
        allowed_modes = {None, "proportional", "base", "flat"}
        self.assertEqual(arsenal.database["schema_version"], 4)

        stat_mappings = [upgrade["stats"] for upgrade in arsenal.upgrades.values()]
        stat_mappings.extend(
            perk.get("stats", {})
            for weapon in arsenal.weapons.values()
            for tier in weapon.get("evolutions", {}).values()
            for perk in tier.values()
        )
        for stats in stat_mappings:
            for stat, effects in stats.items():
                for effect in effects:
                    self.assertIn(effect.get("mode"), allowed_modes)

    def test_bundled_database_contains_normalized_enemy_data(self):
        enemies = arsenal.database["enemies"]
        self.assertEqual(len(enemies), 978)
        self.assertTrue({"Kuva", "Elite Exo Ramsled", "Ogma Elite", "Grineer Queens", "Cryo Sentry", "Narmer Coildrive", "Narmer Bolkor", "Narmer Firbolg", "H-04 Efervon Tank", "Liminus", "Persecutor Liminus"}.isdisjoint(enemies))
        heavy = enemies["Arid Heavy Gunner"]
        self.assertEqual(heavy["name"], "Arid Heavy Gunner")
        self.assertEqual(heavy["faction"], "Grineer")
        self.assertEqual(heavy["base_level"], 8)
        self.assertEqual(heavy["stats"], {"health": 300, "shields": 0, "armor": 500, "overguard": 0})
        self.assertEqual(heavy["bodyparts"]["head"], {"type": "weakpoint", "multiplier": 3.0})
        self.assertEqual(heavy["modifiers"], {"corrosive": 1.5, "impact": 1.5})
        self.assertEqual(enemies["Deimos Jugulus Rex"]["bodyparts"]["body"], {"type": "resistant", "multiplier": 0.5})
        self.assertEqual(enemies["Scaldra Dedicant"]["stats"]["overguard"], 22)

    def test_enemy_model_uses_typed_nested_data_and_loader_runtime(self):
        enemy = arsenal.get("Arid Heavy Gunner")
        copied = enemy.copy()

        self.assertIsInstance(enemy, Enemy)
        self.assertIsInstance(enemy.data, EnemyData)
        self.assertIsInstance(enemy.data.stats, EnemyStats)
        self.assertIsInstance(enemy.data.bodyparts, BodyParts)
        self.assertIsInstance(enemy.data.bodyparts.head, BodyPart)
        self.assertIsInstance(enemy.data.modifiers, EnemyModifiers)
        self.assertIsInstance(enemy.data.runtime, EnemyRuntime)
        self.assertEqual(enemy.data.stats.health, 300)
        self.assertEqual(enemy.data.bodyparts.head.type, "weakpoint")
        self.assertEqual(enemy.data.modifiers.impact, 1.5)
        self.assertEqual(dict(enemy.data.runtime), {"level": 100, "steel_path": False, "empowered": False})
        self.assertIsInstance(copied, Enemy)
        self.assertIsNot(copied.data, enemy.data)
        self.assertIsNot(copied.data.stats, enemy.data.stats)
        self.assertIsNot(copied.data.runtime, enemy.data.runtime)

        direct = Enemy({"name": "Direct Enemy"})
        self.assertIn("runtime", direct.data)
        self.assertEqual(dict(direct.data.runtime), {})

    def test_enemy_calculator_scales_level_and_runtime_modifiers(self):
        enemy = arsenal.get("Arid Heavy Gunner")
        self.assertEqual(dict(enemy.results.effective), {"health": 83815.99, "shields": 0.0, "armor": 2700, "overguard": 0.0})
        configured = arsenal.get("Arid Heavy Gunner", context={"level": 8})
        self.assertEqual(dict(configured.data.runtime), {"level": 8, "steel_path": False, "empowered": False})
        configured.set({"empowered": True})
        self.assertEqual(dict(configured.data.runtime), {"level": 8, "steel_path": False, "empowered": True})
        self.assertEqual(arsenal.get("Arid Heavy Gunner", attribute="level"), 100)

        base = Enemy({"name": "Base", "faction": "Grineer", "base_level": 1, "stats": {"health": 100, "shields": 100, "armor": 100, "overguard": 100}, "runtime": {"level": 1, "steel_path": False, "empowered": False}})
        self.assertEqual(dict(base.results.effective), {"health": 100.0, "shields": 100.0, "armor": 100, "overguard": 100.0})
        base.set({"steel_path": True})
        self.assertEqual(dict(base.results.effective), {"health": 250.0, "shields": 250.0, "armor": 250, "overguard": 100.0})
        base.set({"steel_path": False, "empowered": True})
        self.assertEqual(dict(base.results.effective), {"health": 250.0, "shields": 250.0, "armor": 100, "overguard": 100.0})
        base.data.runtime.level = 2
        self.assertNotEqual(base.results.effective.health, 250)

    def test_enemy_loader_supports_identifiers_filters_and_attributes(self):
        variant = arsenal.get("Senta Turret (Kuva Fortress)")
        enemies = arsenal.get(type="enemy")
        grineer = arsenal.get(type="grineer")

        self.assertIsInstance(variant, Enemy)
        self.assertEqual(variant.data.name, "Senta Turret")
        self.assertEqual(len(enemies), 978)
        self.assertTrue(all(isinstance(enemy, Enemy) for enemy in enemies.values()))
        self.assertEqual(len(grineer), 248)
        self.assertTrue(all(enemy.data.faction == "Grineer" for enemy in grineer.values()))
        self.assertEqual(arsenal.get("Arid Heavy Gunner", attribute="health"), 83815.99)
        self.assertEqual(arsenal.get("Arid Heavy Gunner", attribute="impact"), 1.5)

    def test_arsenal_loads_fresh_weapons_and_safe_upgrades(self):
        first = arsenal.get("Corinth Prime")
        second = arsenal.get("Corinth Prime")
        mod = arsenal.get("Galvanized Chamber")

        self.assertIsInstance(first, Primary)
        self.assertIsInstance(mod, Upgrade)
        self.assertIsNot(first, second)
        first.set({"attack": "air_burst_projectile"})
        self.assertEqual(second.data.selected_attack, "buckshot")

        mod.data.runtime.on_kill = 99
        self.assertEqual(arsenal.get("Galvanized Chamber").data.runtime.on_kill, 5)

    def test_runtime_is_explicit_loader_defaults_and_set_merges(self):
        direct = runtime_upgrade({"name": "Direct", "max_rank": 5, "stats": {"damage_bonus": {"value": 1, "when": "active"}}})
        self.assertIn("runtime", direct.data)
        self.assertEqual(dict(direct.data.runtime), {"rank": 5, "active": True})
        self.assertEqual(direct.results.total.proportional.damage_bonus, 1)

        loaded = arsenal.get("Galvanized Chamber", context={"rank": 4})
        self.assertEqual(dict(loaded.data.runtime), {"rank": 4, "on_kill": 5})
        loaded.set({"on_kill": 2})
        self.assertEqual(loaded.data.runtime.rank, 4)
        self.assertEqual(loaded.data.runtime.on_kill, 2)

        weapon = arsenal.get("Corinth Prime").set({"attack": "air_burst_projectile"})
        self.assertIn("runtime", weapon.data)
        self.assertEqual(weapon.data.runtime.attack, "air_burst_projectile")

        default_weapon = arsenal.get("Corinth Prime")
        self.assertEqual(dict(default_weapon.data.runtime), {"attack": "buckshot"})
        self.assertEqual(default_weapon.data.selected_attack, "buckshot")
        self.assertEqual(dict(arsenal.get("Galatine Prime").data.runtime), {"attack": "normal_attack", "combo": 12, "stance_combo": "neutral"})
        self.assertIn("evolutions", arsenal.get("Telos Boltor").data.runtime)
        self.assertNotIn("evolutions", default_weapon.data.runtime)
        self.assertIn("ability_strength", arsenal.get("Exalted Blade").data.runtime)
        self.assertNotIn("ability_strength", default_weapon.data.runtime)

    def test_weapon_data_separates_global_stats_and_attacks(self):
        weapon = arsenal.get("Corinth Prime")

        self.assertEqual(weapon.data.name, "Corinth Prime")
        self.assertEqual(weapon.data.type, "primary")
        self.assertEqual(weapon.data.subtype, "shotgun")
        self.assertIsInstance(weapon.data.attacks, Attacks)
        self.assertTrue(all(isinstance(attack, Attack) for attack in weapon.data.attacks.values()))
        self.assertFalse(hasattr(weapon, "context"))
        self.assertFalse(hasattr(weapon, "mode_name"))
        self.assertTrue(hasattr(weapon, "results"))
        self.assertFalse(hasattr(weapon, "stats"))
        self.assertFalse(hasattr(weapon, "attacks"))
        self.assertTrue(hasattr(weapon.results, "main"))
        self.assertTrue(hasattr(weapon.results, "child"))
        self.assertFalse(hasattr(weapon.results, "attacks"))
        self.assertFalse(hasattr(weapon.results, "final"))
        for attribute in ("base", "modded", "effective", "average", "final", "children"):
            self.assertTrue(hasattr(weapon.results.main, attribute))
        for attribute in ("base", "modded", "effective", "average", "attacks", "parent"):
            self.assertFalse(hasattr(weapon.results, attribute))
        for attribute in ("type", "subtype", "base", "moded", "modded", "effective", "total_dps", "calculation_build"):
            self.assertFalse(hasattr(weapon, attribute))
        self.assertTrue(all(isinstance(attack.name, str) and attack.name for attack in weapon.data.attacks.values()))
        self.assertEqual(weapon.data.attacks["buckshot"].name, "Buckshot")
        self.assertEqual(weapon.results.main.name, weapon.data.selected_attack)
        self.assertEqual(weapon.data.ammo.reload_time, 3)
        self.assertEqual(weapon.data.ammo.magazine_size, 20)
        self.assertNotIn("damage", weapon.data.ammo)
        self.assertEqual(weapon.data.attacks[weapon.data.selected_attack].stats.damage.total_damage(), 90)
        self.assertNotIn("reload_time", weapon.data.attacks[weapon.data.selected_attack].stats)

    def test_default_mode_switching(self):
        weapon = arsenal.get("Corinth Prime")
        self.assertEqual(weapon.data.selected_attack, "buckshot")

        self.assertIs(weapon.set({"attack": "air_burst_projectile"}), weapon)
        self.assertEqual(weapon.data.attacks[weapon.data.selected_attack].children, ["air_burst_explosion"])
        self.assertEqual(selected(weapon).base.damage.total_damage(), 100)
        self.assertEqual(weapon.results.child[0].effective.damage.total_damage(), 2200)
        self.assertIs(weapon.results.child[0].attack, weapon.data.attacks.air_burst_explosion)

    def test_mode_specific_stats_and_global_ranged_stats(self):
        weapon = arsenal.get("Corinth Prime").set({"attack": "buckshot"})
        mode = weapon.data.attacks[weapon.data.selected_attack].stats

        self.assertAlmostEqual(mode.crit_chance, 0.3)
        self.assertAlmostEqual(mode.status_chance, 0.09)
        self.assertAlmostEqual(mode.fire_rate, 1.42)
        self.assertEqual(mode.co_factor, 1)
        self.assertEqual(mode.co_effect, "adds")
        self.assertEqual(selected(weapon).base.magazine_capacity, 20)
        self.assertEqual(selected(weapon).base.reload_speed, 3)

        battery = arsenal.get("Tenet Cycron")
        self.assertIn("recharge_delay", battery.data.ammo)
        self.assertAlmostEqual(battery.data.ammo.recharge_rate, 26.66666667)
        self.assertAlmostEqual(selected(battery).base.recharge_rate, 26.66666667)

    def test_related_attacks_use_their_own_average_fire_rate(self):
        weapon = arsenal.get("Corinth Prime").set({"attack": "air_burst_projectile"})
        related = weapon.data.attacks.air_burst_explosion
        related.stats.fire_rate = 2
        weapon.results.resolve()

        self.assertNotEqual(
            weapon.results._effective_attacks_per_second(selected(weapon)),
            weapon.results._effective_attacks_per_second(weapon.results.child[0]),
        )

    def test_selected_and_child_attacks_use_independent_buckets(self):
        weapon = arsenal.get("Corinth Prime").set({"attack": "air_burst_projectile"})
        parent = selected(weapon)
        child = weapon.results.child[0]

        self.assertIs(parent.attack, weapon.data.attacks[weapon.data.selected_attack])
        self.assertIsNot(parent.average, parent.final)
        self.assertIs(child.attack, weapon.data.attacks.air_burst_explosion)
        self.assertNotEqual(parent.base.damage, child.base.damage)
        self.assertIsNot(parent.average, child.average)

    def test_attack_final_recurses_and_uses_parent_fire_rate(self):
        weapon = runtime_weapon(Primary, {
            "name": "Nested",
            "type": "primary",
            "ammo": {"magazine_size": 10, "reload_time": 1},
            "attacks": {
                "parent": {"children": ["child"], "stats": {"damage": {"slash": 10}, "fire_rate": 2}},
                "child": {"children": ["grandchild"], "stats": {"damage": {"slash": 20}, "fire_rate": 5, "crit_chance": 0.5, "crit_damage": 2, "status_chance": 0.5}},
                "grandchild": {"stats": {"damage": {"slash": 30}, "fire_rate": 9, "status_chance": 0.75}},
            },
        })
        parent = weapon.results.main
        child = weapon.results.child[0]
        weapon.set({"attack": "child"})
        grandchild = weapon.results.child[0]
        grandchild_avg_dph = grandchild.average.flat_dph
        grandchild_avg_dps = grandchild.average.flat_dps
        grandchild_avg_dotph = grandchild.average.flat_dotph
        grandchild_final_dph = grandchild.final.flat_dph
        grandchild_status = grandchild.effective.status_chance
        weapon.set({"attack": "parent"})
        parent = weapon.results.main
        child = weapon.results.child[0]

        self.assertNotEqual(parent.effective.crit_chance, child.effective.crit_chance)
        self.assertNotEqual(child.effective.status_chance, grandchild_status)
        expected_dph = parent.average.flat_dph + child.average.flat_dph + grandchild_avg_dph
        self.assertAlmostEqual(parent.final.flat_dph, expected_dph)
        self.assertAlmostEqual(
            parent.final.flat_dps,
            weapon.results._effective_attacks_per_second(parent) * expected_dph,
        )
        self.assertNotEqual(
            parent.final.flat_dps,
            parent.average.flat_dps + child.average.flat_dps + grandchild_avg_dps,
        )
        expected_dotph = parent.average.flat_dotph + child.average.flat_dotph + grandchild_avg_dotph
        self.assertGreater(expected_dotph, 0)
        self.assertAlmostEqual(parent.final.flat_dotph, expected_dotph)
        self.assertAlmostEqual(parent.final.total_dph, expected_dph + expected_dotph)
        self.assertAlmostEqual(parent.final.flat_dotps, weapon.results._effective_attacks_per_second(parent) * expected_dotph)
        self.assertAlmostEqual(child.final.flat_dph, child.average.flat_dph + grandchild_avg_dph)
        self.assertAlmostEqual(grandchild_final_dph, grandchild_avg_dph)

    def test_attack_relationship_cycles_are_detected_by_name(self):
        with self.assertRaisesRegex(ValueError, "cyclic attack relationship detected: parent"):
            runtime_weapon(Primary, {
                "name": "Cycle",
                "type": "primary",
                "attacks": {
                    "parent": {"children": ["child"], "stats": {"damage": {"impact": 10}}},
                    "child": {"children": ["parent"], "stats": {"damage": {"impact": 20}}},
                },
            })

    def test_ammo_cost_is_local_to_each_attack_bucket(self):
        weapon = runtime_weapon(Primary, {
            "name": "Mixed Delivery",
            "type": "primary",
            "ammo": {"magazine_size": 100, "reload_time": 2},
            "attacks": {
                "parent": {"delivery": "hitscan", "children": ["child"], "stats": {"damage": {"impact": 10}, "multishot": 2, "fire_rate": 10}},
                "child": {"delivery": "beam", "stats": {"damage": {"heat": 20}, "multishot": 3, "ammo_cost": 0.5, "fire_rate": 10}},
            },
        })
        parent = weapon.results.main
        child = weapon.results.child[0]

        self.assertEqual(parent.effective.ammo_cost, 1)
        self.assertEqual(child.effective.ammo_cost, 0.5)
        self.assertEqual(parent.effective.ammo_efficiency, 0)
        self.assertEqual(child.effective.ammo_efficiency, 0)
        self.assertGreater(child.average.fire_rate, parent.average.fire_rate)

    def test_multishot_consumes_ammo_scales_cost_and_unique_damage(self):
        split = arsenal.get("Split Chamber")
        bare = selected(arsenal.get("Braton"))
        weapon = arsenal.get("Braton").configure(Build(split)).set({"evolutions": {2: 2}})
        result = selected(weapon)
        self.assertTrue(formulas.multishot_consumes_ammo_enabled(result.evolutions))
        self.assertAlmostEqual(formulas.multishot_consumes_ammo_bonus(result.evolutions), 0.6)
        # Munitions Grit +20% MS stacks with Split Chamber; ammo cost scales with total multishot.
        self.assertAlmostEqual(result.effective.multishot, bare.effective.multishot * (1 + 0.9 + 0.2))
        self.assertAlmostEqual(result.effective.ammo_cost, result.effective.multishot)
        self.assertGreater(formulas.multishot_ammo_damage_factor(result.effective.multishot, 0.6), 1.0)
        self.assertLess(result.average.fire_rate, bare.average.fire_rate)

    def test_spectral_serration_is_conditional_on_invisible(self):
        upgrade = arsenal.get("Spectral Serration")
        self.assertEqual(upgrade.data.stats.damage_bonus, [{"value": 3.3, "when": "invisible"}])
        self.assertAlmostEqual(upgrade.results.total.proportional.damage_bonus, 3.3)
        upgrade.set({"invisible": False})
        self.assertAlmostEqual(upgrade.results.total.proportional.damage_bonus, 0)

    def test_beam_dot_scales_with_multishot_squared(self):
        def heat_weapon(delivery: str, multishot: float) -> Primary:
            return runtime_weapon(Primary, {"name": f"{delivery}-{multishot}", "type": "primary", "ammo": {"magazine_size": 100, "reload_time": 1}, "attacks": {"tick": {"delivery": delivery, "stats": {"damage": {"heat": 100}, "status_chance": 1.0, "crit_chance": 0.0, "crit_damage": 2.0, "multishot": multishot, "fire_rate": 12}}}})

        hitscan_ms1 = selected(heat_weapon("hitscan", 1.0)).average.flat_dotph
        hitscan_ms2 = selected(heat_weapon("hitscan", 2.0)).average.flat_dotph
        beam_ms1 = selected(heat_weapon("beam", 1.0)).average.flat_dotph
        beam_ms2 = selected(heat_weapon("beam", 2.0)).average.flat_dotph
        self.assertGreater(hitscan_ms1, 0)
        self.assertAlmostEqual(hitscan_ms2 / hitscan_ms1, 2.0)
        self.assertAlmostEqual(beam_ms1, hitscan_ms1)
        self.assertAlmostEqual(beam_ms2 / beam_ms1, 4.0)

    def test_multiple_child_attacks_are_combined_once(self):
        weapon = runtime_weapon(Primary, {
            "name": "Multiple Children",
            "type": "primary",
            "attacks": {
                "parent": {"children": ["first", "second"], "stats": {"damage": {"impact": 10}}},
                "first": {"stats": {"damage": {"impact": 20}}},
                "second": {"stats": {"damage": {"impact": 30}}},
            },
        })

        self.assertEqual(selected(weapon).children, ["first", "second"])
        self.assertAlmostEqual(selected(weapon).final.flat_dph, 60)

    def test_melee_weapons_include_related_attacks(self):
        weapon = arsenal.get("Ceramic Dagger").set({"attack": "incarnon_spectral_dagger"})

        self.assertIs(weapon.results.child[0].attack, weapon.data.attacks.incarnon_spectral_dagger_explosion)
        self.assertGreater(selected(weapon).final.flat_dph, selected(weapon).effective.damage.total_damage())

    def test_melee_duplicate_increases_condition_overload_status_acquisition(self):
        condition_overload = arsenal.get("Condition Overload")
        duplicate = runtime_upgrade({
            "name": "Duplicate",
            "type": "arcane",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"duplicated_hit": [{"value": 1, "behavior": "NEAR_YELLOW", "automatic": True, "behavior_data": {}}]},
        })
        without_duplicate = arsenal.get("Skana").configure(Build(condition_overload))
        with_duplicate = arsenal.get("Skana").configure(Build(condition_overload, duplicate))

        self.assertGreater(
            with_duplicate.results._average_condition_overload_bonus(selected(with_duplicate)),
            without_duplicate.results._average_condition_overload_bonus(selected(without_duplicate)),
        )
        self.assertGreater(selected(with_duplicate).average.flat_dotph, selected(without_duplicate).average.flat_dotph)

    def test_build_configuration_copies_and_recomputes(self):
        build = galvanized_build()
        weapon = arsenal.get("Corinth Prime")
        base_multishot = selected(weapon).effective.multishot
        base_damage = selected(weapon).effective.damage.total_damage()

        self.assertIs(weapon.configure(build), weapon)
        self.assertIsNot(weapon.build, build)
        self.assertGreater(selected(weapon).effective.multishot, base_multishot)
        self.assertGreater(selected(weapon).effective.damage.total_damage(), base_damage)

        for upgrade in build.upgrades:
            upgrade.data.runtime.on_kill = 0
        build.results.resolve()
        self.assertGreater(selected(weapon).effective.multishot, base_multishot)

        single = arsenal.get("Braton").configure(arsenal.get("Serration"))
        self.assertEqual([upgrade.data.name for upgrade in single.build], ["Serration"])

    def test_build_iteration_addition_and_subtraction_remain_available(self):
        chamber = arsenal.get("Galvanized Chamber", context={"on_kill": 5})
        aptitude = arsenal.get("Galvanized Aptitude")
        build = Build(chamber) + aptitude

        self.assertEqual(len(list(build)), 2)
        reduced = build - chamber
        self.assertEqual([upgrade.data.name for upgrade in reduced], ["Galvanized Aptitude"])

    def test_contribution_uses_shapley_values_without_mutating_weapon(self):
        serration = arsenal.get("Serration")
        heavy_caliber = arsenal.get("Heavy Caliber")
        weapon = arsenal.get("Braton").configure(Build(serration, heavy_caliber))
        full_dps = selected(weapon).final.total_dps

        proportions = weapon.results.shapley_contributions()
        self.assertGreater(proportions["Serration"], 0)
        self.assertGreater(proportions["Heavy Caliber"], 0)
        self.assertAlmostEqual(sum(proportions.values()), 1.0)
        self.assertAlmostEqual(selected(weapon).final.total_dps, full_dps)
        self.assertEqual([upgrade.data.name for upgrade in weapon.build], ["Serration", "Heavy Caliber"])

        without_serration = weapon.copy().configure(Build(heavy_caliber))
        without_heavy = weapon.copy().configure(Build(serration))
        removals = weapon.results.removal_contributions()
        self.assertAlmostEqual(removals["Serration"], full_dps - selected(without_serration).final.total_dps)
        self.assertAlmostEqual(removals["Heavy Caliber"], full_dps - selected(without_heavy).final.total_dps)
        self.assertAlmostEqual(selected(weapon).final.total_dps, full_dps)
        self.assertEqual([upgrade.data.name for upgrade in weapon.build], ["Serration", "Heavy Caliber"])

        full_dph = selected(weapon).final.total_dph
        dph_removals = weapon.results.removal_contributions("total_dph")
        self.assertAlmostEqual(dph_removals["Serration"], full_dph - selected(without_serration).final.total_dph)
        self.assertAlmostEqual(dph_removals["Heavy Caliber"], full_dph - selected(without_heavy).final.total_dph)
        dph_shares = weapon.results.shapley_contributions(target="total_dph")
        self.assertAlmostEqual(sum(dph_shares.values()), 1.0)
        with self.assertRaisesRegex(ValueError, "unsupported contribution target"):
            weapon.results.removal_contributions("not_a_metric")

    def test_build_has_one_canonical_upgrade_collection(self):
        from typing import get_type_hints

        build = galvanized_build()
        result_hints = get_type_hints(BuildCalculator)

        self.assertFalse(hasattr(build, "data"))
        self.assertTrue(hasattr(build, "results"))
        self.assertIs(get_type_hints(Build)["results"], BuildCalculator)
        for bucket in ("static", "conditional", "modular", "stacking", "rank_locked", "total"):
            self.assertIs(result_hints[bucket], ResolvedStat)
        self.assertTrue(build.upgrades)

    def test_upgrade_copy_preserves_runtime_without_sharing_data(self):
        from typing import get_type_hints

        upgrade = arsenal.get("Galvanized Chamber", context={"on_kill": 3})
        copied = upgrade.copy()
        result_hints = get_type_hints(UpgradeCalculator)

        self.assertTrue(hasattr(upgrade, "results"))
        self.assertIs(get_type_hints(Upgrade)["results"], UpgradeCalculator)
        for bucket in ("static", "conditional", "modular", "stacking", "rank_locked", "total"):
            self.assertIs(result_hints[bucket], ResolvedStat)
        self.assertEqual(copied.data.runtime.on_kill, 3)
        self.assertIsNot(copied.data, upgrade.data)
        copied.data.stats.multishot = 99
        self.assertNotEqual(copied.data.stats.multishot, upgrade.data.stats.multishot)

    def test_weapon_copy_preserves_configuration_without_sharing_state(self):
        build = galvanized_build()
        weapon = arsenal.get("Corinth Prime").configure(build).set({"attack": "air_burst_projectile"})
        copied = weapon.copy()

        self.assertIsNot(copied, weapon)
        self.assertIsNot(copied.data, weapon.data)
        self.assertIsNot(copied.build, weapon.build)
        self.assertEqual(copied.data.selected_attack, weapon.data.selected_attack)
        self.assertEqual(dict(copied.data.runtime), dict(weapon.data.runtime))
        self.assertIsNot(copied.data.runtime, weapon.data.runtime)
        self.assertEqual(selected(copied).effective, selected(weapon).effective)

        copied.set({"attack": next(name for name in copied.data.attacks if name != copied.data.selected_attack)})
        self.assertNotEqual(copied.data.selected_attack, weapon.data.selected_attack)
        self.assertEqual(weapon.data.runtime.attack, "air_burst_projectile")

        telos = arsenal.get("Telos Boltor").configure(build).set({"evolutions": {2: 1}})
        telos_copy = telos.copy()
        self.assertEqual(telos_copy.data.runtime.evolutions, {2: 1})
        telos_copy.set({"evolutions": {2: 2}})
        self.assertEqual(telos.data.runtime.evolutions, {2: 1})
        self.assertNotEqual(selected(telos_copy).effective, selected(telos).effective)

    def test_configure_attack_and_build_are_order_independent(self):
        build = galvanized_build()
        first = arsenal.get("Corinth Prime").configure(build).set({"attack": "air_burst_projectile"})
        second = arsenal.get("Corinth Prime").set({"attack": "air_burst_projectile"}).configure(build)

        self.assertEqual(selected(first).effective, selected(second).effective)
        self.assertAlmostEqual(selected(first).final.total_dps, selected(second).final.total_dps, places=6)

    def test_weapon_set_context_preserves_runtime_combo(self):
        weapon = arsenal.get("Furax").set({"combo": 6})
        self.assertEqual(weapon.data.runtime.combo, 6)
        self.assertEqual(weapon.data.selected_combo, 6)

        copied = weapon.copy()
        self.assertEqual(copied.data.runtime.combo, 6)
        self.assertEqual(copied.data.selected_combo, 6)

        weapon.set({"combo": 99})
        self.assertEqual(weapon.data.runtime.combo, 99)
        self.assertEqual(weapon.data.selected_combo, 99)

    def test_exalted_ability_strength_scales_base_damage(self):
        blade = runtime_weapon(Melee, arsenal.weapons["Exalted Blade"])
        raw = selected(blade).base.damage.total_damage()
        self.assertTrue(blade.data.exalted)
        self.assertFalse(blade.data.pseudo_exalted)

        scaled = blade.set({"ability_strength": 2.5})
        self.assertAlmostEqual(scaled.data.selected_ability_strength, 2.5)
        self.assertAlmostEqual(selected(scaled).base.damage.total_damage(), raw * 2.5)

        # Strength is on base before Pressure Point.
        pressure = runtime_upgrade({"name": "Pressure Point", "type": "mod", "max_rank": 0, "stats": {"damage_bonus": [{"value": 1.0}]}})
        modded = runtime_weapon(Melee, arsenal.weapons["Exalted Blade"]).configure(Build(pressure)).set({"ability_strength": 2.0})
        self.assertAlmostEqual(selected(modded).base.damage.total_damage(), raw * 2.0)
        self.assertAlmostEqual(selected(modded).effective.damage.total_damage(), raw * 2.0 * 2.0)

    def test_pseudo_exalted_ability_strength_scales_base_damage(self):
        whipclaw = arsenal.get("Whipclaw")
        self.assertTrue(whipclaw.data.pseudo_exalted)
        raw = selected(whipclaw).base.damage.total_damage()
        scaled = whipclaw.set({"ability_strength": 2.0})
        self.assertAlmostEqual(selected(scaled).base.damage.total_damage(), raw * 2.0)

    def test_ability_strength_ignored_on_non_exalted_weapons(self):
        weapon = arsenal.get("Braton").set({"ability_strength": 3.0})
        bare = arsenal.get("Braton")
        self.assertFalse(weapon.data.exalted or weapon.data.pseudo_exalted)
        self.assertAlmostEqual(selected(weapon).base.damage.total_damage(), selected(bare).base.damage.total_damage())

    def test_weapon_combo_behavior_scales_blood_rush(self):
        blood_rush = arsenal.get("Blood Rush")
        effect = blood_rush.data.stats.crit_chance[0]
        self.assertEqual(effect.behavior, "WEAPON_COMBO")
        self.assertEqual(dict(effect.behavior_data), {"max_stacks": 12})
        self.assertEqual(dict(blood_rush.data.runtime), {"rank": 10})
        self.assertEqual(arsenal.get("Weeping Wounds").data.stats.status_chance[0].behavior, "WEAPON_COMBO")
        bare = arsenal.get("Furax")
        low = arsenal.get("Furax").configure(Build(blood_rush)).set({"combo": 6})
        high = arsenal.get("Furax").configure(Build(arsenal.get("Blood Rush"))).set({"combo": 12})
        self.assertGreater(selected(high).effective.crit_chance, selected(bare).effective.crit_chance)
        self.assertGreater(selected(high).effective.crit_chance, selected(low).effective.crit_chance)

    def test_upgrade_runtime_combo_does_not_drive_combo_behavior(self):
        normal = arsenal.get("Furax").configure(Build(arsenal.get("Blood Rush"))).set({"combo": 12})
        spoofed = arsenal.get("Furax").configure(Build(arsenal.get("Blood Rush").set({"combo": 1}))).set({"combo": 12})
        self.assertEqual(selected(normal).effective.crit_chance, selected(spoofed).effective.crit_chance)

    def test_incarnon_evolution_selection_recomputes(self):
        weapon = arsenal.get("Telos Boltor")
        self.assertIsInstance(weapon.data.evolutions, Evolutions)
        initial_damage = selected(weapon).effective.damage.total_damage()
        raw_base = selected(weapon).base.damage.total_damage()

        self.assertIs(weapon.set({"evolutions": {2: 1}}), weapon)
        self.assertEqual(weapon.data.runtime.evolutions, {2: 1})
        self.assertGreater(selected(weapon).effective.damage.total_damage(), initial_damage)
        self.assertAlmostEqual(selected(weapon).base.damage.total_damage(), raw_base + 4)
        self.assertEqual(len(weapon.build), 0)
        self.assertAlmostEqual(selected(weapon).evolutions.base.damage, 4)

    def test_incarnon_fire_rate_applies_after_runtime_mutation(self):
        weapon = arsenal.get("Phenmor")
        base_rate = selected(weapon).effective.fire_rate
        weapon.data.runtime.evolutions = {2: 2}
        self.assertAlmostEqual(selected(weapon).evolutions.proportional.fire_rate, 0.2)
        self.assertAlmostEqual(selected(weapon).effective.fire_rate, base_rate * 1.2)

    def test_incarnon_scoped_magazine_skips_incarnon_form(self):
        normal = arsenal.get("Phenmor").set({"evolutions": {3: 1}, "attack": "normal_attack"})
        incarnon = arsenal.get("Phenmor").set({"evolutions": {3: 1}, "attack": "incarnon_form"})
        self.assertAlmostEqual(selected(normal).effective.magazine_capacity, 45)
        self.assertAlmostEqual(selected(incarnon).base.magazine_capacity, 408)
        self.assertAlmostEqual(selected(incarnon).effective.magazine_capacity, 408)
        self.assertAlmostEqual(selected(incarnon).evolutions.proportional.magazine_capacity, 0)

    def test_incarnon_charge_pool_ignores_magazine_mods(self):
        magazine_warp = arsenal.get("Magazine Warp")
        bare = arsenal.get("Phenmor").set({"attack": "incarnon_form"})
        modded = arsenal.get("Phenmor").configure(Build(magazine_warp)).set({"attack": "incarnon_form"})
        self.assertAlmostEqual(selected(bare).effective.magazine_capacity, 408)
        self.assertAlmostEqual(selected(modded).effective.magazine_capacity, 408)
        self.assertGreater(magazine_warp.results.total.proportional.magazine_capacity, 0)

    def test_incarnon_base_damage_scales_with_serration(self):
        serration = runtime_upgrade({"name": "Serration", "type": "mod", "max_rank": 0, "stats": {"damage_bonus": [{"value": 1.0}]}})
        weapon = arsenal.get("Telos Boltor")
        raw = selected(weapon).base.damage.total_damage()
        weapon.configure(Build(serration)).set({"evolutions": {2: 1}})
        # +4 on base, then ×2 from Serration — not ×5 from treating +4 as additive %
        self.assertAlmostEqual(selected(weapon).base.damage.total_damage(), raw + 4)
        self.assertAlmostEqual(selected(weapon).effective.damage.total_damage(), (raw + 4) * 2)

    def test_incarnon_base_magazine_capacity_adds_to_base(self):
        weapon = arsenal.get("Telos Boltor")
        raw_mag = selected(weapon).base.magazine_capacity
        weapon.set({"evolutions": {3: 2}})
        self.assertAlmostEqual(selected(weapon).base.magazine_capacity, raw_mag + 20)
        self.assertEqual(selected(weapon).modded.proportional.magazine_capacity, raw_mag + 20)

    def test_incarnon_flat_crit_penalty_cannot_make_crit_chance_negative(self):
        negative_crit = runtime_upgrade({"name": "Negative Crit", "stats": {"crit_chance": [{"value": -2.0}]}})
        weapon = arsenal.get("Laetum").configure(Build(negative_crit)).set({"evolutions": {4: 3}})
        result = selected(weapon)

        self.assertAlmostEqual(result.evolutions.flat.crit_chance, -0.1)
        self.assertEqual(result.modded.proportional.crit_chance, 0)
        self.assertEqual(result.effective.crit_chance, 0)
        self.assertEqual(result.effective.weakpoint_crit_chance, 0)
        self.assertEqual(result.average.crit_chance, 0)
        self.assertEqual(result.average.weakpoint_crit_chance, 0)

    def test_incarnon_chance_floors_survive_conversion_refreshes(self):
        negative_chances = runtime_upgrade({
            "name": "Negative Chances",
            "stats": {
                "crit_chance": [{"value": -2.0}],
                "status_chance": [{"value": -2.0}],
            },
        })
        weapon = runtime_weapon(Primary, {
            "name": "Negative Conversion Chances",
            "type": "primary",
            "attacks": {
                "shot": {
                    "stats": {
                        "damage": {"impact": 100},
                        "crit_chance": 0.2,
                        "crit_damage": 2,
                        "status_chance": 0.2,
                        "fire_rate": 1,
                    },
                },
            },
            "evolutions": {
                "2": {
                    "1": {
                        "stats": {
                            "crit_chance": [{"value": -0.1, "mode": "flat"}],
                            "status_chance": [{"value": -0.1, "mode": "flat"}],
                            "crit_from_status": [{"value": 0.25, "max": 0.35}],
                            "status_from_crit": [{"value": 0.3, "max": 0.4}],
                        },
                    },
                },
            },
        }).configure(Build(negative_chances)).set({"evolutions": {2: 1}})
        result = selected(weapon)

        self.assertAlmostEqual(result.base.crit_chance, 0.2)
        self.assertAlmostEqual(result.base.status_chance, 0.2)
        self.assertEqual(result.effective.crit_chance, 0)
        self.assertEqual(result.effective.weakpoint_crit_chance, 0)
        self.assertEqual(result.effective.status_chance, 0)

    def test_incarnon_crit_from_status_updates_base(self):
        status_mod = runtime_upgrade({"name": "Status", "type": "mod", "max_rank": 0, "stats": {"status_chance": [{"value": 1.0}]}})
        weapon = arsenal.get("Dera Vandal")
        raw_crit = selected(weapon).base.crit_chance
        weapon.configure(Build(status_mod)).set({"evolutions": {4: 2}})
        effective_status = selected(weapon).effective.status_chance
        expected_bonus = min(0.35, 0.25 * effective_status)
        self.assertAlmostEqual(selected(weapon).base.crit_chance, raw_crit + expected_bonus)
        self.assertAlmostEqual(selected(weapon).modded.proportional.crit_chance, selected(weapon).base.crit_chance)

    def test_incarnon_status_from_crit_updates_base(self):
        crit_mod = runtime_upgrade({"name": "Crit", "type": "mod", "max_rank": 0, "stats": {"crit_chance": [{"value": 1.0}]}})
        weapon = arsenal.get("Sicarus")
        raw_status = selected(weapon).base.status_chance
        weapon.configure(Build(crit_mod)).set({"evolutions": {4: 3}})
        effective_crit = selected(weapon).effective.crit_chance
        # status_from_crit uses effective crit after conversion refresh of status only;
        # conversion reads effective crit from the first pass (before status refresh).
        first_pass_crit = selected(weapon).base.crit_chance * (1 + 1.0)
        expected_bonus = min(0.40, 0.3 * first_pass_crit)
        self.assertAlmostEqual(selected(weapon).base.status_chance, raw_status + expected_bonus, places=6)

    def test_incarnon_gunco_ignores_base_damage(self):
        gunco = runtime_upgrade({
            "name": "GunCO",
            "type": "mod",
            "max_rank": 0,
            "stats": {"damage_bonus": [{"value": 1, "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {"max_stacks": 1}}]},
        })
        weapon = runtime_weapon(Primary, {
            "name": "Evo CO",
            "type": "primary",
            "attacks": {
                "shot": {"stats": {"damage": {"impact": 100}, "status_chance": 1, "fire_rate": 1, "multishot": 1, "co_effect": "adds"}},
            },
            "evolutions": {
                "2": {"1": {"description": "base", "stats": {"damage": [{"value": 50, "mode": "base"}]}}},
            },
        })
        without_evo = weapon.configure(Build(gunco)).results.main.effective.damage.total_damage()
        with_evo = weapon.configure(Build(gunco)).set({"evolutions": {2: 1}}).results.main
        # Serration-less: damage = 1*(100+50) + CO*100. CO contribution equals the no-evo CO contribution.
        co_without = without_evo - 100
        self.assertAlmostEqual(with_evo.base.damage.total_damage(), 150)
        self.assertAlmostEqual(with_evo.effective.damage.total_damage(), 150 + co_without)
        self.assertAlmostEqual(with_evo.original_damage.total_damage(), 100)

    def test_melee_incarnon_attack_applies_baked_damage_bonus(self):
        normal = selected(arsenal.get("Furax"))
        incarnon = selected(arsenal.get("Furax").set({"attack": "incarnon_normal_attack"}))
        # Innate attack damage_bonus 1 + base 1 => effective 2; total damage doubles vs normal.
        self.assertAlmostEqual(incarnon.effective.damage_bonus, 2)
        self.assertAlmostEqual(
            incarnon.effective.damage.total_damage(),
            normal.effective.damage.total_damage() * 2,
        )

    def test_melee_incarnon_damage_bonus_stacks_additively_with_pressure_point(self):
        pressure_point = arsenal.get("Primed Pressure Point")
        self.assertAlmostEqual(pressure_point.results.total.proportional.damage_bonus, 1.65)
        weapon = arsenal.get("Furax").configure(Build(pressure_point)).set({"attack": "incarnon_normal_attack"})
        result = selected(weapon)
        # 1 base + 1.65 Pressure Point + 1 innate incarnon => 3.65
        self.assertAlmostEqual(result.effective.damage_bonus, 3.65)
        self.assertAlmostEqual(
            result.effective.damage.total_damage(),
            result.base.damage.total_damage() * 3.65,
        )

    def test_melee_incarnon_evo1_stats_empty(self):
        stats = arsenal.get("Furax").data.evolutions["1"]["1"].stats
        self.assertIsInstance(stats, Mapping)
        self.assertEqual(dict(stats), {})

    def test_ruvox_incarnon_bakes_conversion_and_speed(self):
        weapon = arsenal.get("Ruvox").set({"attack": "incarnon_normal_attack"})
        attack = weapon.data.attacks["incarnon_normal_attack"]
        result = selected(weapon)
        damage = dict(result.base.damage)
        self.assertIn("puncture", damage)
        self.assertAlmostEqual(float(damage.get("impact", 0) or 0), 0)
        self.assertAlmostEqual(attack.stats.attack_speed, 0.65)
        self.assertAlmostEqual(result.effective.attack_speed, 0.65)
        self.assertAlmostEqual(result.effective.range, 3)

    def test_hate_spectral_is_incarnon_only(self):
        attacks = arsenal.get("Hate").data.attacks
        self.assertIn("incarnon_spectral_blade", attacks)
        self.assertEqual(attacks["incarnon_spectral_blade"].form, "incarnon")
        self.assertNotIn("spectral_blade", attacks)

    def test_heavy_attack_doubles_crit_chance_upgrade_bonus(self):
        true_steel = runtime_upgrade({
            "name": "True Steel",
            "type": "mod",
            "max_rank": 0,
            "stats": {"crit_chance": [{"value": 1.2}]},
        })
        base_crit = selected(arsenal.get("Furax")).base.crit_chance
        normal = selected(arsenal.get("Furax").configure(Build(true_steel)).set({"attack": "normal_attack"}))
        heavy = selected(arsenal.get("Furax").configure(Build(true_steel)).set({"attack": "heavy_attack"}))
        # Normal: base * (1 + 1.2); heavy doubles the upgrade bonus: base * (1 + 2.4)
        self.assertAlmostEqual(normal.effective.crit_chance, base_crit * 2.2)
        self.assertAlmostEqual(heavy.effective.crit_chance, base_crit * 3.4)

    def test_non_crit_bonus_from_cull_the_weak(self):
        cull = arsenal.get("Cull the Weak")
        self.assertAlmostEqual(float(cull.results.total.multiplicative_families["non_crit"].damage_bonus), 2.4)
        non_crit = runtime_upgrade({
            "name": "NonCrit",
            "type": "mod",
            "max_rank": 0,
            "stats": {"damage_bonus": [{"value": 2.4, "family": "non_crit", "behavior": "ON_NON_CRIT", "automatic": True, "behavior_data": {}}]},
        })
        weapon = runtime_weapon(Melee, {
            "name": "NCD Melee",
            "type": "melee",
            "attacks": {
                "normal_attack": {"stats": {"damage": {"slash": 100}, "crit_chance": 0.0, "crit_damage": 2.0, "status_chance": 0.1, "attack_speed": 1}},
            },
        }).configure(Build(non_crit))
        # 0% crit → every hit is non-crit → ×(1+2.4)
        self.assertAlmostEqual(selected(weapon).effective.non_crit_bonus_damage, 2.4)
        self.assertAlmostEqual(selected(weapon).average.flat_dph, 100 * 3.4)

    def test_non_crit_bonus_devouring_attrition(self):
        weapon = arsenal.get("Laetum")
        raw = selected(weapon)
        base_dph = raw.average.flat_dph
        weapon.set({"evolutions": {5: 1}})
        result = selected(weapon)
        self.assertAlmostEqual(float(result.evolutions.multiplicative_families["non_crit"].damage_bonus), 20)
        self.assertAlmostEqual(result.evolutions.proportional.non_crit_bonus_chance, 0.5)
        self.assertAlmostEqual(result.effective.non_crit_bonus_damage, 20)
        self.assertAlmostEqual(result.effective.non_crit_bonus_chance, 0.5)
        cc, cd = result.average.crit_chance, result.effective.crit_damage
        expected_mult = formulas.hit_multiplier(cc, cd, 20, 0.5)
        expected_dph = result.effective.damage.total_damage() * result.effective.multishot * expected_mult
        self.assertAlmostEqual(result.average.flat_dph, expected_dph)
        self.assertGreater(result.average.flat_dph, base_dph)

    def test_upgrade_and_build_set_update_runtime_conditions(self):
        upgrade = runtime_upgrade({"name": "Headshot", "type": "mod", "max_rank": 0, "stats": {"crit_chance": [1.2, {"value": 0.8, "when": "headshot"}]}})
        self.assertEqual(upgrade.results.total.proportional.crit_chance, 2.0)
        upgrade.set({"headshot": False})
        self.assertEqual(upgrade.results.total.proportional.crit_chance, 1.2)

        build = Build(
            runtime_upgrade({"name": "CC", "type": "mod", "max_rank": 0, "stats": {"crit_chance": {"value": 0.8, "when": "headshot"}}}),
            runtime_upgrade({"name": "CD", "type": "mod", "max_rank": 0, "stats": {"crit_damage": {"value": 0.8, "when": "headshot"}}}),
        )
        self.assertEqual(build.results.total.proportional.crit_chance, 0.8)
        self.assertEqual(build.results.total.proportional.crit_damage, 0.8)
        build.set({"headshot": False})
        self.assertEqual(build.results.total.proportional.crit_chance, 0)
        self.assertEqual(build.results.total.proportional.crit_damage, 0)

    def test_special_upgrades_keep_calculator_values(self):
        from warframe_damage_calculator.calculators import application_chance, stacking_reset

        self.assertAlmostEqual(application_chance.hunter_munitions_chance(arsenal.get("Hunter Munitions").results.total.application_chance), 0.3)
        self.assertAlmostEqual(application_chance.internal_bleeding_chance(arsenal.get("Internal Bleeding").results.total.application_chance), 0.35)
        self.assertAlmostEqual(application_chance.internal_bleeding_chance(arsenal.get("Hemorrhage").results.total.application_chance), 0.35)
        self.assertAlmostEqual(application_chance.encumber_chance(arsenal.get("Secondary Encumber").results.total.application_chance), 0.24)
        self.assertAlmostEqual(application_chance.vigilante_flat_crit(arsenal.get("Vigilante Supplies").results.total.application_chance), 0.05)
        self.assertAlmostEqual(application_chance.duplicate_chance(arsenal.get("Melee Duplicate").results.total.application_chance), 1)
        self.assertAlmostEqual(application_chance.doughty_factor(arsenal.get("Melee Doughty").results.total.conversions), 1)
        enervate = arsenal.get("Secondary Enervate")
        self.assertEqual(enervate.data.stats.crit_reset_charges, [{"value": 6, "behavior": "STACK_RESET_CRIT_2_PLUS", "automatic": True, "behavior_data": {"stat": "crit_chance", "mode": "flat", "per_stack": 0.1}}])
        per_stack, charges = stacking_reset.enervate_params(enervate.results.total.stacking_reset)
        self.assertAlmostEqual(per_stack, 0.1)
        self.assertAlmostEqual(charges, 6)

        primed = arsenal.get("Primed Chamber").results.total.magazine_position
        charged = arsenal.get("Charged Chamber").results.total.magazine_position
        synth = arsenal.get("Synth Charge").results.total.magazine_position
        self.assertEqual(primed, [{"stat": "damage_bonus", "value": 1, "mode": "proportional", "when": "first_shot", "family": "chamber"}])
        self.assertEqual(charged, [{"stat": "damage_bonus", "value": 0.4, "mode": "proportional", "when": "first_shot", "family": "chamber"}])
        self.assertEqual(synth, [{"stat": "damage_bonus", "value": 2, "mode": "proportional", "when": "last_shot", "family": "charge", "exclude": ["continuous", "incarnon"]}])

    def test_first_shot_damage_averages_across_magazine(self):
        base = runtime_weapon(Primary, {"name": "Chamber Test", "type": "primary", "subtype": "sniper", "ammo": {"magazine_size": 10, "reload_time": 1}, "attacks": {"shot": {"delivery": "hitscan", "stats": {"damage": {"impact": 100}, "crit_chance": 0, "crit_damage": 2, "multishot": 1, "fire_rate": 1}}}})
        with_chamber = runtime_weapon(Primary, base.data).configure(Build(arsenal.get("Primed Chamber")))
        self.assertAlmostEqual(selected(with_chamber).average.first_shot_damage_multiplier, 1.1)
        self.assertAlmostEqual(selected(with_chamber).average.flat_dph / selected(base).average.flat_dph, 1.1)

        one_round = runtime_weapon(Primary, {"name": "Vectis-like", "type": "primary", "subtype": "sniper", "ammo": {"magazine_size": 1, "reload_time": 1}, "attacks": {"shot": {"delivery": "hitscan", "stats": {"damage": {"impact": 100}, "crit_chance": 0, "crit_damage": 2, "multishot": 1, "fire_rate": 1}}}})
        one_chamber = runtime_weapon(Primary, one_round.data).configure(Build(arsenal.get("Primed Chamber")))
        self.assertAlmostEqual(selected(one_chamber).average.first_shot_damage_multiplier, 2.0)
        self.assertAlmostEqual(selected(one_chamber).average.flat_dph / selected(one_round).average.flat_dph, 2.0)

    def test_multiplicative_families_product_not_sum(self):
        sniper = {"name": "Tier Sniper", "type": "primary", "subtype": "sniper", "ammo": {"magazine_size": 1, "reload_time": 1}, "attacks": {"shot": {"delivery": "hitscan", "stats": {"damage": {"impact": 100}, "crit_chance": 0, "crit_damage": 2, "multishot": 1, "fire_rate": 1}}}}
        bonus = runtime_upgrade({"name": "Bonus Mult", "type": "mod", "max_rank": 0, "stats": {"damage_bonus": [{"value": 0.5, "family": "bonus"}]}})
        with_both = runtime_weapon(Primary, sniper).configure(Build(bonus, arsenal.get("Primed Chamber")))
        # bonus ×1.5 and chamber ×2 product to ×3, not additive ×2.5
        self.assertAlmostEqual(selected(with_both).average.flat_dph, 300.0)
        self.assertEqual(float(with_both.build.results.total.multiplicative_families["bonus"].damage_bonus), 0.5)
        self.assertEqual(with_both.build.results.total.magazine_position[0]["family"], "chamber")

        both_chambers = runtime_weapon(Primary, sniper).configure(Build(arsenal.get("Primed Chamber"), arsenal.get("Charged Chamber")))
        # Same chamber family: Primed + Charged add → +140% → ×2.4
        self.assertAlmostEqual(selected(both_chambers).average.flat_dph, 240.0)
        self.assertAlmostEqual(selected(both_chambers).average.first_shot_damage_multiplier, 2.4)

    def test_last_shot_multishot_and_synth_charge_excludes(self):
        weapon = runtime_weapon(Primary, {"name": "Last MS", "type": "primary", "ammo": {"magazine_size": 5, "reload_time": 1}, "attacks": {"shot": {"delivery": "hitscan", "stats": {"damage": {"heat": 100}, "crit_chance": 0, "crit_damage": 2, "status_chance": 0, "multishot": 1, "fire_rate": 1}}}, "evolutions": {"2": {"1": {"stats": {"multishot": [{"value": 3, "mode": "flat", "when": "last_shot"}]}}}}})
        weapon.set({"evolutions": {2: 1}})
        # 4 normal @ MS1 + 1 last @ MS4 → average DPH = (4*100 + 400)/5 = 160
        self.assertAlmostEqual(selected(weapon).average.flat_dph, 160.0)

        bare = arsenal.get("Lato")
        synth = arsenal.get("Lato").configure(Build(arsenal.get("Synth Charge")))
        self.assertGreater(selected(synth).average.flat_dph, selected(bare).average.flat_dph)

        beam_data = {"name": "Beam Pistol", "type": "secondary", "subtype": "pistol", "ammo": {"magazine_size": 10, "reload_time": 1}, "attacks": {"tick": {"delivery": "beam", "stats": {"damage": {"heat": 100}, "crit_chance": 0, "crit_damage": 2, "multishot": 1, "fire_rate": 8}}}}
        beam = runtime_weapon(Secondary, beam_data)
        beam_synth = runtime_weapon(Secondary, beam_data).configure(Build(arsenal.get("Synth Charge")))
        self.assertAlmostEqual(selected(beam_synth).average.flat_dph, selected(beam).average.flat_dph)

    def test_calculator_uses_largest_faction_damage_bonus(self):
        corpus = arsenal.get("Primed Bane of Corpus")
        grineer = arsenal.get("Bane of Grineer")
        weapon = arsenal.get("Braton").configure(Build(corpus, grineer))

        self.assertEqual(weapon.build.results.total.proportional.corpus_damage, 0.55)
        self.assertEqual(weapon.build.results.total.proportional.grineer_damage, 0.3)
        attack = weapon.results.main
        self.assertEqual(attack.modded.proportional.corpus_damage, 1.55)
        self.assertEqual(attack.effective.corpus_damage, 1.55)
        self.assertEqual(attack.average.corpus_damage, 1.55)
        self.assertEqual(attack.modded.proportional.grineer_damage, 1.3)
        self.assertEqual(weapon.results._max_average_faction_damage(attack), 1.55)

    def test_upgrade_stats_accept_scalar_and_single_record_shorthand(self):
        scalar = runtime_upgrade({"name": "Scalar", "type": "mod", "max_rank": 0, "stats": {"damage_bonus": 1.5}})
        record = runtime_upgrade({"name": "Record", "type": "mod", "max_rank": 0, "stats": {"crit_damage": {"value": 2.5, "when": "active"}}})

        self.assertEqual(scalar.results.static.proportional.damage_bonus, 1.5)
        self.assertEqual(record.results.conditional.proportional.crit_damage, 2.5)
        self.assertEqual(scalar.data.stats.damage_bonus, 1.5)

    def test_upgrade_stats_resolve_effect_modes(self):
        upgrade = runtime_upgrade({
            "name": "Modes",
            "type": "buff",
            "max_rank": 0,
            "stats": {
                "crit_chance": [
                    {"value": 1.2, "mode": "proportional"},
                    {"value": 0.2, "mode": "flat"},
                    {"value": 0.5, "family": "bonus"},
                ],
                "crit_damage": {"value": 0.4, "mode": "base"},
            },
        })

        self.assertAlmostEqual(upgrade.results.total.proportional.crit_chance, 1.2)
        self.assertAlmostEqual(upgrade.results.total.flat.crit_chance, 0.2)
        self.assertAlmostEqual(upgrade.results.total.multiplicative_families["bonus"].crit_chance, 0.5)
        self.assertAlmostEqual(upgrade.results.total.base.crit_damage, 0.4)

    def test_upgrade_stats_default_to_proportional_mode(self):
        explicit = runtime_upgrade({"stats": {"crit_chance": {"value": 1.2, "mode": "proportional"}}})
        omitted = runtime_upgrade({"stats": {"crit_chance": {"value": 1.2}}})

        self.assertEqual(explicit.results.total.proportional.crit_chance, omitted.results.total.proportional.crit_chance)

    def test_calculated_stats_use_mode_buckets(self):
        upgrade = runtime_upgrade({
            "stats": {
                "crit_chance": [
                    {"value": 1.2, "mode": "proportional"},
                    {"value": 0.2, "mode": "flat"},
                    {"value": 0.5, "family": "bonus"},
                ],
            },
        })
        modded = selected(arsenal.get("Braton").configure(Build(upgrade))).modded

        self.assertGreater(modded.proportional.crit_chance, 0)
        self.assertGreaterEqual(modded.proportional.status_damage, 1)
        self.assertEqual(modded.flat.crit_chance, 0.2)
        self.assertAlmostEqual(selected(arsenal.get("Braton").configure(Build(upgrade))).effective.crit_chance, formulas.combine_chance(modded.proportional.crit_chance, 1.5, 0.2))
        self.assertEqual(set(modded) - {"multiplicative_families"}, {"proportional", "base", "flat"})

    def test_upgrade_stats_reject_unknown_modes(self):
        with self.assertRaisesRegex(ValueError, "unsupported effect mode"):
            runtime_upgrade({"stats": {"crit_chance": {"value": 1.2, "mode": "percent"}}})

    def test_upgrade_stats_accept_mixed_scalar_and_record_lists(self):
        upgrade = runtime_upgrade({
            "name": "Mixed",
            "type": "mod",
            "max_rank": 0,
            "stats": {"damage_bonus": [1.5, {"value": 2.5, "when": "active"}]},
        })

        self.assertEqual(upgrade.results.static.proportional.damage_bonus, 1.5)
        self.assertEqual(upgrade.results.conditional.proportional.damage_bonus, 2.5)
        self.assertEqual(upgrade.results.total.proportional.damage_bonus, 4)

        cannonade = arsenal.get("Corinth Prime").configure(Build(
            arsenal.get("Semi-Shotgun Cannonade"),
            arsenal.get("Critical Delay"),
        ))
        self.assertTrue(cannonade.build.results.total.proportional.fire_rate_lock)
        self.assertAlmostEqual(selected(cannonade).effective.fire_rate, selected(cannonade).base.fire_rate)

        acuity = Build(arsenal.get("Primary Acuity"))
        self.assertTrue(acuity.results.total.proportional.multishot_lock)
        self.assertAlmostEqual(acuity.results.total.multiplicative_families["bonus"].weakpoint_crit_chance, 3.498)
        self.assertEqual(acuity.results.total.proportional.weakpoint_crit_chance, 0)
        self.assertAlmostEqual(arsenal.get("Furor").results.total.proportional.attack_speed, 0.1)

    def test_upgrade_effect_buckets_apply_sensible_defaults(self):
        chamber = arsenal.get("Galvanized Chamber")
        self.assertAlmostEqual(chamber.results.static.proportional.multishot, 0.8)
        self.assertAlmostEqual(chamber.results.stacking.proportional.multishot, 1.5)
        self.assertAlmostEqual(chamber.results.total.proportional.multishot, 2.3)

        no_stacks = Build(arsenal.get("Galvanized Chamber", context={"on_kill": 0}))
        self.assertEqual(no_stacks.results.stacking.proportional.multishot, 0)
        self.assertAlmostEqual(no_stacks.results.total.proportional.multishot, 0.8)

        merciless = arsenal.get("Primary Merciless")
        self.assertAlmostEqual(merciless.results.stacking.proportional.damage_bonus, 3.6)
        self.assertAlmostEqual(merciless.results.rank_locked.proportional.reload_speed, 0.3)

        conditional = runtime_upgrade({
            "name": "Conditional",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"damage_bonus": [{"value": 1, "when": "kill"}]},
        })
        self.assertEqual(conditional.results.conditional.proportional.damage_bonus, 1)
        conditional.data.runtime.kill = False
        disabled = Build(conditional)
        self.assertEqual(disabled.results.conditional.proportional.damage_bonus, 0)

    def test_condition_overload_uses_status_cap_and_attack_rules(self):
        condition_overload = runtime_upgrade({
            "name": "Condition Overload",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"damage_bonus": [{"value": 1, "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {"max_stacks": 2}}]},
        })
        base_damage = runtime_upgrade({
            "name": "Base Damage",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"damage_bonus": [{"value": 1}]},
        })
        build = Build(condition_overload, base_damage)

        additive = arsenal.get("Cernos").configure(build).set({"attack": "charged_shot"})
        additive_base = selected(additive).base.damage.total_damage()
        self.assertEqual(additive.data.attacks[additive.data.selected_attack].stats.co_factor, 0.5)
        self.assertEqual(additive.data.attacks[additive.data.selected_attack].stats.co_effect, "adds")
        self.assertGreater(selected(additive).effective.damage.total_damage(), additive_base * 2)
        self.assertLess(selected(additive).effective.damage.total_damage(), additive_base * 3)

        multiplicative = arsenal.get("Coda Bassocyst").configure(build).set({"attack": "normal_attack"})
        multiplicative_base = selected(multiplicative).base.damage.total_damage()
        self.assertEqual(multiplicative.data.attacks[multiplicative.data.selected_attack].stats.co_effect, "multiplies")
        self.assertGreater(selected(multiplicative).effective.damage.total_damage(), multiplicative_base * 2)
        self.assertLess(selected(multiplicative).effective.damage.total_damage(), multiplicative_base * 6)

    def test_condition_overload_database_values_remain_structured(self):
        expected = {
            "Condition Overload": (
                {"value": 0.8, "family": "status", "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {}},
                {"value": 0.8, "max_stacks": "inf"},
            ),
            "Cull the Weak": (
                [
                    {"value": 0.6, "family": "status", "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {"max_stacks": 3}},
                    {"value": 2.4, "family": "non_crit", "behavior": "ON_NON_CRIT", "automatic": True, "behavior_data": {}},
                ],
                {"value": 0.6, "max_stacks": 3},
            ),
            "Galvanized Aptitude": (
                {"value": 0.4, "family": "status", "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {}, "stacks": {"when": "on_kill", "max": 2}},
                {"value": 0.8, "max_stacks": "inf"},
            ),
            "Galvanized Savvy": (
                {"value": 0.4, "family": "status", "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {}, "stacks": {"when": "on_kill", "max": 2}},
                {"value": 0.8, "max_stacks": "inf"},
            ),
            "Galvanized Shot": (
                {"value": 0.4, "family": "status", "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {}, "stacks": {"when": "on_kill", "max": 3}},
                {"value": 1.2, "max_stacks": "inf"},
            ),
        }
        for name, (canonical, resolved) in expected.items():
            with self.subTest(name=name):
                entries = canonical if isinstance(canonical, list) else [canonical]
                self.assertEqual(arsenal.upgrades[name]["stats"]["damage_bonus"], entries)
                actual = arsenal.get(name).results.total.proportional.condition_overload
                self.assertAlmostEqual(float(actual["value"]), float(resolved["value"]))
                self.assertEqual(actual["max_stacks"], resolved["max_stacks"])

    def test_condition_overload_bonus_uses_sustained_unique_procs(self):
        condition_overload = runtime_upgrade({
            "name": "Condition Overload",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"damage_bonus": [{"value": 0.8, "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {"max_stacks": 2}}]},
        })
        weapon = arsenal.get("Cernos").configure(Build(condition_overload))

        self.assertGreater(weapon.results._average_condition_overload_bonus(selected(weapon)), 0)
        self.assertLess(weapon.results._average_condition_overload_bonus(selected(weapon)), 1.6)

    def test_condition_overload_scales_with_status_duration(self):
        condition_overload = runtime_upgrade({
            "name": "Condition Overload",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"damage_bonus": [{"value": 0.8, "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {"max_stacks": 3}}]},
        })
        duration = runtime_upgrade({
            "name": "Lasting Sting",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"status_duration": [{"value": 1}]},
        })
        without_duration = arsenal.get("Skana").configure(Build(condition_overload))
        with_duration = arsenal.get("Skana").configure(Build(condition_overload, duration))

        self.assertGreater(
            with_duration.results._average_condition_overload_bonus(selected(with_duration)),
            without_duration.results._average_condition_overload_bonus(selected(without_duration)),
        )

    def test_condition_overload_forced_proc_is_fully_sustained(self):
        condition_overload = runtime_upgrade({
            "name": "Condition Overload",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"damage_bonus": [{"value": 1, "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {"max_stacks": 1}}]},
        })
        weapon = runtime_weapon(Primary, {
            "name": "Forced CO",
            "type": "primary",
            "attacks": {
                "normal": {
                    "stats": {
                        "damage": {"impact": 10},
                        "status_chance": 0,
                        "fire_rate": 1,
                        "forced_procs": {"heat": 1},
                    },
                },
            },
        }).configure(Build(condition_overload))

        self.assertAlmostEqual(weapon.results._average_condition_overload_bonus(selected(weapon)), 1)

    def test_condition_overload_uses_each_attack_bucket(self):
        condition_overload = runtime_upgrade({
            "name": "Condition Overload",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"damage_bonus": [{"value": 1, "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {"max_stacks": 1}}]},
        })
        weapon = runtime_weapon(Primary, {
            "name": "Bucketed CO",
            "type": "primary",
            "attacks": {
                "parent": {"children": ["child"], "stats": {"damage": {"impact": 10}, "status_chance": 0}},
                "child": {"stats": {"damage": {"heat": 10}, "status_chance": 1}},
            },
        }).configure(Build(condition_overload))
        parent = weapon.results.main
        child = weapon.results.child[0]

        self.assertEqual(weapon.results._average_condition_overload_bonus(parent), 0)
        self.assertGreater(weapon.results._average_condition_overload_bonus(child), 0)
        self.assertEqual(parent.modded.proportional.damage_bonus, 1)
        self.assertGreater(child.modded.proportional.damage_bonus, 1)

    def test_condition_overload_mod_has_no_status_cap(self):
        heat = runtime_upgrade({
            "name": "Heat",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"heat": [{"value": 1}]},
        })
        without_condition_overload = arsenal.get("Skana").configure(Build(heat))
        with_condition_overload = arsenal.get("Skana").configure(Build(heat, arsenal.get("Condition Overload")))

        elemental_damage = selected(without_condition_overload).effective.damage.total_damage()
        self.assertEqual(set(selected(with_condition_overload).effective.damage.data), {"impact", "puncture", "slash", "heat"})
        self.assertGreater(selected(with_condition_overload).effective.damage.total_damage(), elemental_damage)
        self.assertLess(selected(with_condition_overload).effective.damage.total_damage(), elemental_damage * (1 + 0.8 * 4))

    def test_formatter_summary_reads_current_state(self):
        weapon = arsenal.get("Corinth Prime").configure(galvanized_build()).set({"attack": "buckshot"})
        summary = weapon.format.summary()
        upgrades = weapon.format.upgrades()

        self.assertIn("Corinth Prime", summary)
        self.assertIn("Buckshot", summary)
        self.assertIn("TOTAL DPS", summary)
        self.assertIn("Galvanized Chamber", upgrades)
        self.assertIn("shapley", upgrades)
        self.assertIn("removal", upgrades)

    def test_projectile_speed_scales_falloff_without_changing_dps(self):
        base = arsenal.get("Corinth Prime").set({"attack": "buckshot"})
        modded = arsenal.get("Corinth Prime").configure(Build(arsenal.get("Fatal Acceleration"))).set({"attack": "buckshot"})
        base_result = selected(base)
        modded_result = selected(modded)

        self.assertAlmostEqual(base_result.effective.start_range, 18)
        self.assertAlmostEqual(base_result.effective.end_range, 36)
        self.assertAlmostEqual(modded_result.effective.projectile_speed, 0.4)
        self.assertAlmostEqual(modded_result.effective.start_range, 18 * 1.4)
        self.assertAlmostEqual(modded_result.effective.end_range, 36 * 1.4)
        self.assertAlmostEqual(base_result.average.total_dps, modded_result.average.total_dps)

    def test_formatter_renders_related_attack_base_and_total_damage(self):
        weapon = arsenal.get("Corinth Prime").set({"attack": "air_burst_projectile"})
        summary = weapon.format.summary()
        blast = next(line for line in summary.splitlines() if line.startswith("AIR BURST EXPLOSION BLAST"))
        total = next(line for line in summary.splitlines() if line.startswith("AIR BURST EXPLOSION TOTAL DAMAGE"))

        self.assertRegex(blast, r"2200\.00\s+\|\s+2200\.00")
        self.assertRegex(total, r"2200\.00\s+\|\s+2200\.00")

    def test_rank_scaled_and_rank_locked_effects_resolve_independently(self):
        upgrade = runtime_upgrade({
            "name": "Hybrid Rank",
            "type": "mod",
            "max_rank": 5,
            "stats": {
                "damage_bonus": 1.65,
                "reload_speed": [{"value": 0.3, "rank": 5}],
            },
        })

        low = upgrade.set({"rank": 2})
        self.assertAlmostEqual(low.results.static.proportional.damage_bonus, 1.65 * 3 / 6)
        self.assertEqual(low.results.rank_locked.proportional.reload_speed, 0)
        self.assertAlmostEqual(low.results.total.proportional.damage_bonus, 1.65 * 3 / 6)

        high = upgrade.set({"rank": 5})
        self.assertAlmostEqual(high.results.static.proportional.damage_bonus, 1.65)
        self.assertEqual(high.results.rank_locked.proportional.reload_speed, 0.3)
        self.assertAlmostEqual(high.results.total.proportional.damage_bonus, 1.65)
        self.assertAlmostEqual(high.results.total.proportional.reload_speed, 0.3)

        merciless = arsenal.get("Primary Merciless", context={"rank": 2, "on_kill": 12})
        self.assertAlmostEqual(merciless.results.stacking.proportional.damage_bonus, 0.3 * 3 / 6 * 12)
        self.assertEqual(merciless.results.rank_locked.proportional.reload_speed, 0)

        rank_locked = runtime_upgrade({"stats": {"crit_chance": {"value": 2, "rank": 10}}, "max_rank": 11})
        rank_locked.set({"rank": 10})
        self.assertEqual(rank_locked.results.rank_locked.proportional.crit_chance, 2)
        self.assertEqual(rank_locked.results.total.proportional.crit_chance, 2)
        rank_locked.set({"rank": 9})
        self.assertEqual(rank_locked.results.total.proportional.crit_chance, 0)

    def test_build_subtraction_matches_definition_not_runtime(self):
        low = arsenal.get("Serration", context={"rank": 5})
        high = arsenal.get("Serration", context={"rank": 10})
        other = arsenal.get("Point Strike")
        build = Build(high, other)

        self.assertTrue(low == high)
        self.assertNotEqual(low, object())
        self.assertNotEqual(low, "Serration")
        reduced = build - low
        self.assertEqual([upgrade.data.name for upgrade in reduced], ["Point Strike"])

        different = runtime_upgrade({"name": "Serration", "type": "mod", "max_rank": 10, "stats": {"damage_bonus": 0.1}})
        self.assertFalse(different == high)
        untouched = Build(high) - different
        self.assertEqual([upgrade.data.name for upgrade in untouched], ["Serration"])

    def test_protocols_accept_concrete_models(self):
        from warframe_damage_calculator.protocols import (
            ConfigurableWeaponOwner,
            UpgradeOwner,
            WeaponCalculatorOwner,
            WeaponFormatterOwner,
        )

        upgrade = runtime_upgrade({"name": "Proto", "type": "mod", "max_rank": 0, "stats": {"damage_bonus": 1}})
        weapon = arsenal.get("Braton")

        self.assertIsInstance(upgrade, UpgradeOwner)
        self.assertIsInstance(weapon, WeaponCalculatorOwner)
        self.assertIsInstance(weapon, ConfigurableWeaponOwner)
        self.assertIsInstance(weapon, WeaponFormatterOwner)
        self.assertEqual(UpgradeCalculator(upgrade).total.proportional.damage_bonus, 1)
        self.assertEqual(weapon.results.main.name, weapon.data.selected_attack)
        self.assertIn(weapon.data.name, weapon.format.summary())

    def test_effect_buckets_aggregate_independently(self):
        upgrade = runtime_upgrade({
            "name": "Buckets",
            "type": "mod",
            "max_rank": 5,
            "stats": {
                "damage_bonus": [
                    0.30,
                    {"value": 0.20, "when": "headshot"},
                    {"value": 0.10, "stacks": {"when": "kill", "max": 3}},
                    {"value": 0.25, "rank": 5},
                    {"value": 0.15, "equipped": ["Partner"]},
                ],
            },
        })
        upgrade.data.runtime.update({"rank": 5, "headshot": True, "kill": 2})
        upgrade.results.resolve(build=Data({"equipped": ["Partner"]}))

        self.assertAlmostEqual(upgrade.results.static.proportional.damage_bonus, 0.30)
        self.assertAlmostEqual(upgrade.results.conditional.proportional.damage_bonus, 0.20)
        self.assertAlmostEqual(upgrade.results.stacking.proportional.damage_bonus, 0.20)
        self.assertAlmostEqual(upgrade.results.rank_locked.proportional.damage_bonus, 0.25)
        self.assertAlmostEqual(upgrade.results.modular.proportional.damage_bonus, 0.15)
        self.assertAlmostEqual(upgrade.results.total.proportional.damage_bonus, 1.10)

        alone = runtime_upgrade(upgrade.data.copy())
        alone.data.runtime.update({"rank": 5, "headshot": True, "kill": 2})
        alone.results.resolve()
        self.assertEqual(alone.results.modular.proportional.damage_bonus, 0)
        self.assertAlmostEqual(alone.results.total.proportional.damage_bonus, 0.95)

    def test_condition_overload_applies_before_modded_damage(self):
        from warframe_damage_calculator.calculators.weapon_calculator import WeaponCalculator

        condition_overload = runtime_upgrade({
            "name": "CO",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"damage_bonus": [{"value": 1, "behavior": "UNIQUE_STATUS", "automatic": True, "behavior_data": {"max_stacks": 1}}]},
        })
        weapon = runtime_weapon(Primary, {
            "name": "CO Order",
            "type": "primary",
            "attacks": {
                "shot": {"stats": {"damage": {"heat": 100}, "status_chance": 1, "fire_rate": 1, "multishot": 1}},
            },
        }).configure(Build(condition_overload))

        result = weapon.results.main
        self.assertGreater(result.modded.proportional.damage_bonus, 1)
        expected_damage = result.modded.proportional.damage_bonus * result.base.damage.apply(result.build.proportional.damage).combine().sorted()
        self.assertEqual(dict(result.modded.proportional.damage), dict(expected_damage))

        damage_assignments: list[float] = []
        original = WeaponCalculator._compute_modded_damage
        test_case = self

        def tracked(calculator, attack_result):
            damage_assignments.append(attack_result.modded.proportional.damage_bonus)
            original(calculator, attack_result)
            test_case.assertEqual(
                dict(attack_result.modded.proportional.damage),
                dict(attack_result.modded.proportional.damage_bonus * attack_result.base.damage.apply(attack_result.build.proportional.damage).combine().sorted()),
            )

        WeaponCalculator._compute_modded_damage = tracked
        try:
            weapon.configure(Build(condition_overload))
        finally:
            WeaponCalculator._compute_modded_damage = original

        self.assertEqual(len(damage_assignments), 1)
        self.assertGreater(damage_assignments[0], 1)

    def test_modded_scalars_do_not_assign_damage(self):
        from warframe_damage_calculator.calculators.weapon_calculator import WeaponCalculator

        weapon = arsenal.get("Braton")
        result = weapon.results.main
        calculator = weapon.results
        fresh = type(result)({
            "name": result.name,
            "attack": result.attack,
            "build": result.build.copy(),
            "children": list(result.children),
        })
        calculator._compute_base(fresh)
        calculator._apply_evolution_conversions(fresh)
        calculator._compute_modded_scalars(fresh)
        self.assertEqual(fresh.modded.proportional.damage.total_damage(), 0)
        model = calculator._sustained_status_model(fresh)
        calculator._apply_status_effect_stacks(fresh, model)
        calculator._apply_condition_overload(fresh, model)
        calculator._compute_modded_damage(fresh)
        self.assertGreater(fresh.modded.proportional.damage.total_damage(), 0)
        self.assertIsInstance(calculator, WeaponCalculator)

    def test_status_effect_stacks_database_shape(self):
        frostbite = arsenal.upgrades["Primary Frostbite"]["stats"]
        self.assertEqual(frostbite["crit_damage"], [
            {"value": 0.03, "behavior": "STATUS_PROC_STACKS", "automatic": True, "behavior_data": {"status": "cold", "max_stacks": 40, "duration": 12}},
        ])
        self.assertEqual(frostbite["multishot"], [
            {"value": 0.0225, "behavior": "STATUS_PROC_STACKS", "automatic": True, "behavior_data": {"status": "cold", "max_stacks": 40, "duration": 12}},
        ])
        flare = arsenal.upgrades["Cascadia Flare"]["stats"]["damage_bonus"]
        self.assertEqual(flare, [
            {"value": 0.12, "behavior": "STATUS_PROC_STACKS", "automatic": True, "behavior_data": {"status": "heat", "max_stacks": 40, "duration": 10}},
        ])
        resolved = arsenal.get("Primary Frostbite").results.total.proportional.status_effect_stacks
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0]["status"], "cold")
        self.assertEqual(resolved[0]["stat"], "crit_damage")
        self.assertEqual(resolved[0]["duration"], 12)
        self.assertNotIn("status_effect_stacks", frostbite)

    def test_status_effect_stacks_use_sustained_procs(self):
        cold = runtime_upgrade({"name": "Cold", "type": "mod", "max_rank": 0, "stats": {"cold": [{"value": 1.0}]}})
        without = arsenal.get("Braton").configure(Build(cold))
        with_arcane = arsenal.get("Braton").configure(Build(cold, arsenal.get("Primary Frostbite")))
        self.assertGreater(selected(with_arcane).effective.crit_damage, selected(without).effective.crit_damage)
        self.assertGreater(selected(with_arcane).effective.multishot, selected(without).effective.multishot)

    def test_status_effect_stacks_require_matching_status(self):
        bare = arsenal.get("Lato").configure(Build(arsenal.get("Cascadia Flare")))
        heat = runtime_upgrade({"name": "Heat", "type": "mod", "max_rank": 0, "stats": {"heat": [{"value": 1.0}]}})
        with_heat = arsenal.get("Lato").configure(Build(heat, arsenal.get("Cascadia Flare")))
        self.assertAlmostEqual(selected(bare).effective.damage_bonus, selected(arsenal.get("Lato")).effective.damage_bonus)
        self.assertGreater(selected(with_heat).effective.damage_bonus, selected(bare).effective.damage_bonus)
        self.assertAlmostEqual(arsenal.get("Cascadia Flare").results.total.proportional.damage_bonus, 0)

    def test_status_effect_stacks_ignore_runtime_override(self):
        cold = runtime_upgrade({"name": "Cold", "type": "mod", "max_rank": 0, "stats": {"cold": [{"value": 1.0}]}})
        auto = arsenal.get("Braton").configure(Build(cold, arsenal.get("Primary Frostbite")))
        overridden = arsenal.get("Braton").configure(Build(cold, arsenal.get("Primary Frostbite"))).set({"on_cold_status_effect": 0})
        self.assertAlmostEqual(selected(overridden).effective.crit_damage, selected(auto).effective.crit_damage)

    def test_metadata_stats_defaults_and_silence_mods(self):
        rifle = arsenal.get("Braton")
        bow = arsenal.get("Dread")
        melee = arsenal.get("Skana")
        self.assertEqual(selected(rifle).effective.noise_level, "alarming")
        self.assertEqual(selected(bow).effective.noise_level, "silent")
        self.assertEqual(selected(melee).effective.noise_level, "silent")
        silenced = rifle.configure(Build(arsenal.get("Hush")))
        self.assertEqual(selected(silenced).effective.noise_level, "silent")
        self.assertEqual(arsenal.upgrades["Hush"]["stats"]["noise_level"], [{"value": "silent", "mode": "base"}])

    def test_metadata_upgrade_stats_fold_into_effective(self):
        weapon = arsenal.get("Braton").configure(Build(arsenal.get("Eagle Eye"), arsenal.get("Metal Auger"), arsenal.get("Stabilizer")))
        result = selected(weapon)
        self.assertAlmostEqual(result.effective.zoom, 0.4)
        self.assertAlmostEqual(result.effective.punch_through, 2.1)
        self.assertAlmostEqual(result.effective.recoil, -0.6)
        narrowed = arsenal.get("Boar").configure(Build(arsenal.get("Narrow Barrel")))
        self.assertAlmostEqual(selected(narrowed).effective.accuracy, 0.3)

    def test_ammo_maximum_percent_and_evolution_capacity(self):
        base = runtime_weapon(Primary, {"name": "Reserve", "type": "primary", "subtype": "rifle", "ammo": {"magazine_size": 10, "reload_time": 1, "ammo_maximum": 100}, "attacks": {"normal_attack": {"trigger": "auto", "delivery": "hitscan", "stats": {"damage": {"impact": 10}, "crit_chance": 0.1, "crit_damage": 2, "status_chance": 0.1, "fire_rate": 10}}}})
        drummed = base.configure(Build(arsenal.get("Ammo Drum")))
        self.assertAlmostEqual(selected(drummed).effective.ammo_maximum, 190)
        boar = arsenal.get("Boar").set({"evolutions": {3: 2}})
        self.assertAlmostEqual(selected(boar).effective.ammo_maximum, 195)

    def test_stance_combo_scales_attack_speed_and_damage(self):
        bare = selected(arsenal.get("Skana"))
        stance = arsenal.get("Iron Phoenix")
        combo = stance.data.combos["neutral"]
        with_stance = selected(arsenal.get("Skana").configure(Build(stance)))
        self.assertAlmostEqual(with_stance.effective.attack_speed, bare.effective.attack_speed * combo.hits / combo.duration)
        self.assertAlmostEqual(with_stance.effective.damage.total_damage(), bare.effective.damage.total_damage() * combo.multiplier)
        self.assertGreater(with_stance.average.total_dps, bare.average.total_dps)
        forward = selected(arsenal.get("Skana").configure(Build(stance)).set({"stance_combo": "forward"}))
        forward_combo = stance.data.combos["forward"]
        self.assertAlmostEqual(forward.effective.attack_speed, bare.effective.attack_speed * forward_combo.hits / forward_combo.duration)

    def test_heavy_attack_speed_ignores_normal_attack_speed_mods(self):
        fury = arsenal.get("Fury")
        killing_blow = arsenal.get("Killing Blow")
        bare = selected(arsenal.get("Skana").set({"attack": "heavy_attack"}))
        with_fury = selected(arsenal.get("Skana").configure(Build(fury)).set({"attack": "heavy_attack"}))
        with_killing_blow = selected(arsenal.get("Skana").configure(Build(killing_blow)).set({"attack": "heavy_attack"}))
        self.assertAlmostEqual(with_fury.effective.attack_speed, bare.effective.attack_speed)
        self.assertAlmostEqual(with_killing_blow.effective.attack_speed, bare.effective.attack_speed * (1 + killing_blow.results.total.proportional.heavy_attack_speed))
        normal_with_fury = selected(arsenal.get("Skana").configure(Build(fury)))
        self.assertGreater(normal_with_fury.effective.attack_speed, selected(arsenal.get("Skana")).effective.attack_speed)


if __name__ == "__main__":
    unittest.main()
