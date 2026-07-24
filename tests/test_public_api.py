import unittest
from collections.abc import Mapping
from types import MappingProxyType
from typing import get_args

from warframe_damage_calculator import Build, Melee, Primary, Upgrade, Weapon, arsenal
from warframe_damage_calculator.calculators import formulas
from warframe_damage_calculator.calculators.build_calculator import BuildCalculator
from warframe_damage_calculator.calculators.upgrade_calculator import UpgradeCalculator
from warframe_damage_calculator.calculators.weapon_calculator import WeaponCalculator
from warframe_damage_calculator.loader.bundled_names import MeleeName, PrimaryName, SecondaryName, UpgradeName
from warframe_damage_calculator.core.data import Data
from warframe_damage_calculator.core.dist import Dist
from warframe_damage_calculator.core.dist_data import DistData
from warframe_damage_calculator.fields.attack_result import AttackResult
from warframe_damage_calculator.fields.calculated import CalculatedStats
from warframe_damage_calculator.fields.upgrade import ResolvedStat
from warframe_damage_calculator.fields.weapon_data import Attack, Attacks, Evolutions


def galvanized_build() -> Build:
    return Build(
        arsenal.get("Galvanized Chamber", context={"stacks": 5}),
        arsenal.get("Galvanized Aptitude", context={"stacks": 2}),
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

        for distribution in (attack.stats.damage, attack.stats.forced_procs, CalculatedStats().damage, resolved.additive.damage):
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
        weapon = Weapon({"name": "Test Weapon", "type": "test", "attacks": {"normal": {"stats": {"damage": {"impact": 10}}}}})

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
        }
        for alias, names in expected.items():
            self.assertEqual(set(get_args(alias.__value__)), names)

    def test_bundled_database_uses_explicit_effect_modes(self):
        allowed_modes = {"additive", "multiplicative", "base", "flat"}
        self.assertEqual(arsenal.database["schema_version"], 3)

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

    def test_arsenal_loads_fresh_weapons_and_safe_upgrades(self):
        first = arsenal.get("Corinth Prime")
        second = arsenal.get("Corinth Prime")
        mod = arsenal.get("Galvanized Chamber")

        self.assertIsInstance(first, Primary)
        self.assertIsInstance(mod, Upgrade)
        self.assertIsNot(first, second)
        first.configure(context={"attack": "air_burst_projectile"})
        self.assertEqual(second.data.selected_attack, "buckshot")

        mod.data.runtime.stacks = 99
        self.assertIsNone(arsenal.get("Galvanized Chamber").data.runtime.get("stacks"))

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
        self.assertTrue(all(attack.name == key for key, attack in weapon.data.attacks.items()))
        self.assertEqual(weapon.results.main.name, weapon.data.selected_attack)
        self.assertEqual(weapon.data.ammo.reload_time, 3)
        self.assertEqual(weapon.data.ammo.magazine_size, 20)
        self.assertNotIn("damage", weapon.data.ammo)
        self.assertEqual(weapon.data.attacks[weapon.data.selected_attack].stats.damage.total_damage(), 90)
        self.assertNotIn("reload_time", weapon.data.attacks[weapon.data.selected_attack].stats)

    def test_default_mode_switching(self):
        weapon = arsenal.get("Corinth Prime")
        self.assertEqual(weapon.data.selected_attack, "buckshot")

        self.assertIs(weapon.configure(context={"attack": "air_burst_projectile"}), weapon)
        self.assertEqual(weapon.data.attacks[weapon.data.selected_attack].children, ["air_burst_explosion"])
        self.assertEqual(selected(weapon).base.damage.total_damage(), 100)
        self.assertEqual(weapon.results.child[0].effective.damage.total_damage(), 2200)
        self.assertIs(weapon.results.child[0].attack, weapon.data.attacks.air_burst_explosion)

    def test_mode_specific_stats_and_global_ranged_stats(self):
        weapon = arsenal.get("Corinth Prime").configure(context={"attack": "buckshot"})
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
        weapon = arsenal.get("Corinth Prime").configure(context={"attack": "air_burst_projectile"})
        related = weapon.data.attacks.air_burst_explosion
        related.stats.fire_rate = 2
        weapon.results.resolve()

        self.assertNotEqual(
            weapon.results._effective_attacks_per_second(selected(weapon)),
            weapon.results._effective_attacks_per_second(weapon.results.child[0]),
        )

    def test_selected_and_child_attacks_use_independent_buckets(self):
        weapon = arsenal.get("Corinth Prime").configure(context={"attack": "air_burst_projectile"})
        parent = selected(weapon)
        child = weapon.results.child[0]

        self.assertIs(parent.attack, weapon.data.attacks[weapon.data.selected_attack])
        self.assertIsNot(parent.average, parent.final)
        self.assertIs(child.attack, weapon.data.attacks.air_burst_explosion)
        self.assertNotEqual(parent.base.damage, child.base.damage)
        self.assertIsNot(parent.average, child.average)

    def test_attack_final_recurses_and_uses_parent_fire_rate(self):
        weapon = Primary({
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
        weapon.configure(context={"attack": "child"})
        grandchild = weapon.results.child[0]
        grandchild_avg_dph = grandchild.average.flat_dph
        grandchild_avg_dps = grandchild.average.flat_dps
        grandchild_avg_dotph = grandchild.average.flat_dotph
        grandchild_final_dph = grandchild.final.flat_dph
        grandchild_status = grandchild.effective.status_chance
        weapon.configure(context={"attack": "parent"})
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
            Primary({
                "name": "Cycle",
                "type": "primary",
                "attacks": {
                    "parent": {"children": ["child"], "stats": {"damage": {"impact": 10}}},
                    "child": {"children": ["parent"], "stats": {"damage": {"impact": 20}}},
                },
            })

    def test_ammo_cost_is_local_to_each_attack_bucket(self):
        weapon = Primary({
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

    def test_multiple_child_attacks_are_combined_once(self):
        weapon = Primary({
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
        weapon = arsenal.get("Ceramic Dagger").configure(context={"attack": "incarnon_spectral_dagger"})

        self.assertIs(weapon.results.child[0].attack, weapon.data.attacks.incarnon_spectral_dagger_explosion)
        self.assertGreater(selected(weapon).final.flat_dph, selected(weapon).effective.damage.total_damage())

    def test_melee_duplicate_increases_condition_overload_status_acquisition(self):
        condition_overload = arsenal.get("Condition Overload")
        duplicate = Upgrade({
            "name": "Duplicate",
            "type": "arcane",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"melee_duplicate": [{"value": 1}]},
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
            upgrade.data.runtime.stacks = 0
        build.results.resolve()
        self.assertGreater(selected(weapon).effective.multishot, base_multishot)

    def test_build_iteration_addition_and_subtraction_remain_available(self):
        chamber = arsenal.get("Galvanized Chamber", context={"stacks": 5})
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

        upgrade = arsenal.get("Galvanized Chamber", context={"stacks": 3})
        copied = upgrade.copy()
        result_hints = get_type_hints(UpgradeCalculator)

        self.assertTrue(hasattr(upgrade, "results"))
        self.assertIs(get_type_hints(Upgrade)["results"], UpgradeCalculator)
        for bucket in ("static", "conditional", "modular", "stacking", "rank_locked", "total"):
            self.assertIs(result_hints[bucket], ResolvedStat)
        self.assertEqual(copied.data.runtime.stacks, 3)
        self.assertIsNot(copied.data, upgrade.data)
        copied.data.stats.multishot = 99
        self.assertNotEqual(copied.data.stats.multishot, upgrade.data.stats.multishot)

    def test_weapon_copy_preserves_configuration_without_sharing_state(self):
        build = galvanized_build()
        weapon = arsenal.get("Corinth Prime").configure(build, context={"attack": "air_burst_projectile"})
        copied = weapon.copy()

        self.assertIsNot(copied, weapon)
        self.assertIsNot(copied.data, weapon.data)
        self.assertIsNot(copied.build, weapon.build)
        self.assertEqual(copied.data.selected_attack, weapon.data.selected_attack)
        self.assertEqual(copied.data.selected_evolutions, weapon.data.selected_evolutions)
        self.assertEqual(selected(copied).effective, selected(weapon).effective)

        copied.configure(context={"attack": next(name for name in copied.data.attacks if name != copied.data.selected_attack)})
        self.assertNotEqual(copied.data.selected_attack, weapon.data.selected_attack)
        self.assertEqual(weapon.data.runtime.attack, "air_burst_projectile")

        telos = arsenal.get("Telos Boltor").configure(build, context={"evolutions": {2: 1}})
        telos_copy = telos.copy()
        self.assertEqual(telos_copy.data.runtime.evolutions, {2: 1})
        telos_copy.configure(context={"evolutions": {2: 2}})
        self.assertEqual(telos.data.runtime.evolutions, {2: 1})
        self.assertNotEqual(selected(telos_copy).effective, selected(telos).effective)

    def test_configure_attack_and_build_are_order_independent(self):
        build = galvanized_build()
        first = arsenal.get("Corinth Prime").configure(build, context={"attack": "air_burst_projectile"})
        second = arsenal.get("Corinth Prime").configure(context={"attack": "air_burst_projectile"}).configure(build)

        self.assertEqual(selected(first).effective, selected(second).effective)
        self.assertAlmostEqual(selected(first).final.total_dps, selected(second).final.total_dps, places=6)

    def test_weapon_configure_context_sets_runtime_combo(self):
        weapon = arsenal.get("Furax").configure(context={"combo": 6})
        self.assertEqual(weapon.data.runtime.combo, 6)
        self.assertEqual(weapon.data.selected_combo, 6)

        copied = weapon.copy()
        self.assertEqual(copied.data.runtime.combo, 6)
        self.assertEqual(copied.data.selected_combo, 6)

        weapon.configure(context={"combo": 99})
        self.assertEqual(weapon.data.runtime.combo, 12)
        self.assertEqual(weapon.data.selected_combo, 12)

    def test_weapon_combo_scales_blood_rush(self):
        blood_rush = arsenal.get("Blood Rush")
        self.assertIsNone(blood_rush.data.runtime.get("stacks"))
        low = arsenal.get("Furax").configure(Build(blood_rush), context={"combo": 6})
        high = arsenal.get("Furax").configure(Build(arsenal.get("Blood Rush")), context={"combo": 12})
        self.assertIsNone(low.build.upgrades[0].data.runtime.get("stacks"))
        self.assertIsNone(high.build.upgrades[0].data.runtime.get("stacks"))
        self.assertGreater(selected(high).effective.crit_chance, selected(low).effective.crit_chance)

    def test_upgrade_stacks_override_weapon_combo(self):
        blood_rush = arsenal.get("Blood Rush")
        blood_rush.data.runtime.stacks = 3
        weapon = arsenal.get("Furax").configure(Build(blood_rush), context={"combo": 12})
        at_stacks_3 = arsenal.get("Furax").configure(Build(arsenal.get("Blood Rush")), context={"combo": 3})
        at_combo_12 = arsenal.get("Furax").configure(Build(arsenal.get("Blood Rush")), context={"combo": 12})
        self.assertAlmostEqual(selected(weapon).effective.crit_chance, selected(at_stacks_3).effective.crit_chance)
        self.assertLess(selected(weapon).effective.crit_chance, selected(at_combo_12).effective.crit_chance)

    def test_incarnon_evolution_selection_recomputes(self):
        weapon = arsenal.get("Telos Boltor")
        self.assertIsInstance(weapon.data.evolutions, Evolutions)
        initial_damage = selected(weapon).effective.damage.total_damage()
        raw_base = selected(weapon).base.damage.total_damage()

        self.assertIs(weapon.configure(context={"evolutions": {2: 1}}), weapon)
        self.assertEqual(weapon.data.runtime.evolutions, {2: 1})
        self.assertGreater(selected(weapon).effective.damage.total_damage(), initial_damage)
        self.assertAlmostEqual(selected(weapon).base.damage.total_damage(), raw_base + 4)
        self.assertEqual(len(weapon.build), 0)
        self.assertAlmostEqual(selected(weapon).evolutions.base.damage, 4)

    def test_incarnon_base_damage_scales_with_serration(self):
        serration = Upgrade({"name": "Serration", "type": "mod", "max_rank": 0, "stats": {"damage_bonus": [{"value": 1.0}]}})
        weapon = arsenal.get("Telos Boltor")
        raw = selected(weapon).base.damage.total_damage()
        weapon.configure(Build(serration), context={"evolutions": {2: 1}})
        # +4 on base, then ×2 from Serration — not ×5 from treating +4 as additive %
        self.assertAlmostEqual(selected(weapon).base.damage.total_damage(), raw + 4)
        self.assertAlmostEqual(selected(weapon).effective.damage.total_damage(), (raw + 4) * 2)

    def test_incarnon_base_magazine_capacity_adds_to_base(self):
        weapon = arsenal.get("Telos Boltor")
        raw_mag = selected(weapon).base.magazine_capacity
        weapon.configure(context={"evolutions": {3: 2}})
        self.assertAlmostEqual(selected(weapon).base.magazine_capacity, raw_mag + 20)
        self.assertEqual(selected(weapon).modded.additive.magazine_capacity, raw_mag + 20)

    def test_incarnon_flat_crit_penalty_cannot_make_crit_chance_negative(self):
        negative_crit = Upgrade({"name": "Negative Crit", "stats": {"crit_chance": [{"value": -2.0}]}})
        weapon = arsenal.get("Laetum").configure(Build(negative_crit), context={"evolutions": {4: 3}})
        result = selected(weapon)

        self.assertAlmostEqual(result.evolutions.flat.crit_chance, -0.1)
        self.assertEqual(result.modded.additive.crit_chance, 0)
        self.assertEqual(result.effective.crit_chance, 0)
        self.assertEqual(result.effective.weakpoint_crit_chance, 0)
        self.assertEqual(result.average.crit_chance, 0)
        self.assertEqual(result.average.weakpoint_crit_chance, 0)

    def test_incarnon_chance_floors_survive_conversion_refreshes(self):
        negative_chances = Upgrade({
            "name": "Negative Chances",
            "stats": {
                "crit_chance": [{"value": -2.0}],
                "status_chance": [{"value": -2.0}],
            },
        })
        weapon = Primary({
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
        }).configure(Build(negative_chances), context={"evolutions": {2: 1}})
        result = selected(weapon)

        self.assertAlmostEqual(result.base.crit_chance, 0.2)
        self.assertAlmostEqual(result.base.status_chance, 0.2)
        self.assertEqual(result.effective.crit_chance, 0)
        self.assertEqual(result.effective.weakpoint_crit_chance, 0)
        self.assertEqual(result.effective.status_chance, 0)

    def test_incarnon_crit_from_status_updates_base(self):
        status_mod = Upgrade({"name": "Status", "type": "mod", "max_rank": 0, "stats": {"status_chance": [{"value": 1.0}]}})
        weapon = arsenal.get("Dera Vandal")
        raw_crit = selected(weapon).base.crit_chance
        weapon.configure(Build(status_mod), context={"evolutions": {4: 2}})
        effective_status = selected(weapon).effective.status_chance
        expected_bonus = min(0.35, 0.25 * effective_status)
        self.assertAlmostEqual(selected(weapon).base.crit_chance, raw_crit + expected_bonus)
        self.assertAlmostEqual(selected(weapon).modded.additive.crit_chance, selected(weapon).base.crit_chance)

    def test_incarnon_status_from_crit_updates_base(self):
        crit_mod = Upgrade({"name": "Crit", "type": "mod", "max_rank": 0, "stats": {"crit_chance": [{"value": 1.0}]}})
        weapon = arsenal.get("Sicarus")
        raw_status = selected(weapon).base.status_chance
        weapon.configure(Build(crit_mod), context={"evolutions": {4: 3}})
        effective_crit = selected(weapon).effective.crit_chance
        # status_from_crit uses effective crit after conversion refresh of status only;
        # conversion reads effective crit from the first pass (before status refresh).
        first_pass_crit = selected(weapon).base.crit_chance * (1 + 1.0)
        expected_bonus = min(0.40, 0.3 * first_pass_crit)
        self.assertAlmostEqual(selected(weapon).base.status_chance, raw_status + expected_bonus, places=6)

    def test_incarnon_gunco_ignores_base_damage(self):
        gunco = Upgrade({
            "name": "GunCO",
            "type": "mod",
            "max_rank": 0,
            "stats": {"condition_overload": [{"value": 1, "stacks": {"when": "status_type", "max": 1}}]},
        })
        weapon = Primary({
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
        with_evo = weapon.configure(Build(gunco), context={"evolutions": {2: 1}}).results.main
        # Serration-less: damage = 1*(100+50) + CO*100. CO contribution equals the no-evo CO contribution.
        co_without = without_evo - 100
        self.assertAlmostEqual(with_evo.base.damage.total_damage(), 150)
        self.assertAlmostEqual(with_evo.effective.damage.total_damage(), 150 + co_without)
        self.assertAlmostEqual(with_evo.original_damage.total_damage(), 100)

    def test_melee_incarnon_attack_applies_baked_damage_bonus(self):
        normal = selected(arsenal.get("Furax"))
        incarnon = selected(arsenal.get("Furax").configure(context={"attack": "incarnon_normal_attack"}))
        # Innate attack damage_bonus 1 + base 1 => effective 2; total damage doubles vs normal.
        self.assertAlmostEqual(incarnon.effective.damage_bonus, 2)
        self.assertAlmostEqual(
            incarnon.effective.damage.total_damage(),
            normal.effective.damage.total_damage() * 2,
        )

    def test_melee_incarnon_damage_bonus_stacks_additively_with_pressure_point(self):
        pressure_point = arsenal.get("Primed Pressure Point")
        self.assertAlmostEqual(pressure_point.results.total.additive.damage_bonus, 1.65)
        weapon = arsenal.get("Furax").configure(Build(pressure_point), context={"attack": "incarnon_normal_attack"})
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
        weapon = arsenal.get("Ruvox").configure(context={"attack": "incarnon_normal_attack"})
        attack = weapon.data.attacks["incarnon_normal_attack"]
        result = selected(weapon)
        damage = dict(result.base.damage)
        self.assertIn("puncture", damage)
        self.assertAlmostEqual(float(damage.get("impact", 0) or 0), 0)
        self.assertAlmostEqual(attack.stats.fire_rate, 0.65)
        self.assertAlmostEqual(result.effective.attack_speed, 0.65)
        self.assertAlmostEqual(result.effective.range, 3)

    def test_hate_spectral_is_incarnon_only(self):
        attacks = arsenal.get("Hate").data.attacks
        self.assertIn("incarnon_spectral_blade", attacks)
        self.assertEqual(attacks["incarnon_spectral_blade"].form, "incarnon")
        self.assertNotIn("spectral_blade", attacks)

    def test_heavy_attack_doubles_crit_chance_upgrade_bonus(self):
        true_steel = Upgrade({
            "name": "True Steel",
            "type": "mod",
            "max_rank": 0,
            "stats": {"crit_chance": [{"value": 1.2}]},
        })
        base_crit = selected(arsenal.get("Furax")).base.crit_chance
        normal = selected(arsenal.get("Furax").configure(Build(true_steel), context={"attack": "normal_attack"}))
        heavy = selected(arsenal.get("Furax").configure(Build(true_steel), context={"attack": "heavy_attack"}))
        # Normal: base * (1 + 1.2); heavy doubles the upgrade bonus: base * (1 + 2.4)
        self.assertAlmostEqual(normal.effective.crit_chance, base_crit * 2.2)
        self.assertAlmostEqual(heavy.effective.crit_chance, base_crit * 3.4)

    def test_non_crit_bonus_from_cull_the_weak(self):
        cull = arsenal.get("Cull the Weak")
        self.assertAlmostEqual(cull.results.total.additive.non_crit_bonus_damage, 2.4)
        non_crit = Upgrade({"name": "NonCrit", "type": "mod", "max_rank": 0, "stats": {"non_crit_bonus_damage": [{"value": 2.4}]}})
        weapon = Melee({
            "name": "NCD Melee",
            "type": "melee",
            "attacks": {
                "normal_attack": {"stats": {"damage": {"slash": 100}, "crit_chance": 0.0, "crit_damage": 2.0, "status_chance": 0.1, "fire_rate": 1}},
            },
        }).configure(Build(non_crit))
        # 0% crit → every hit is non-crit → ×(1+2.4)
        self.assertAlmostEqual(selected(weapon).effective.non_crit_bonus_damage, 2.4)
        self.assertAlmostEqual(selected(weapon).average.flat_dph, 100 * 3.4)

    def test_non_crit_bonus_devouring_attrition(self):
        weapon = arsenal.get("Laetum")
        raw = selected(weapon)
        base_dph = raw.average.flat_dph
        weapon.configure(context={"evolutions": {5: 1}})
        result = selected(weapon)
        self.assertAlmostEqual(result.evolutions.additive.non_crit_bonus_damage, 20)
        self.assertAlmostEqual(result.evolutions.additive.non_crit_bonus_chance, 0.5)
        self.assertAlmostEqual(result.effective.non_crit_bonus_damage, 20)
        self.assertAlmostEqual(result.effective.non_crit_bonus_chance, 0.5)
        cc, cd = result.average.crit_chance, result.effective.crit_damage
        expected_mult = formulas.hit_multiplier(cc, cd, 20, 0.5)
        expected_dph = result.effective.damage.total_damage() * result.effective.multishot * expected_mult
        self.assertAlmostEqual(result.average.flat_dph, expected_dph)
        self.assertGreater(result.average.flat_dph, base_dph)

    def test_upgrade_and_build_configure_update_runtime_conditions(self):
        upgrade = Upgrade({"name": "Headshot", "type": "mod", "max_rank": 0, "stats": {"crit_chance": [1.2, {"value": 0.8, "when": "headshot"}]}})
        self.assertEqual(upgrade.results.total.additive.crit_chance, 2.0)
        upgrade.configure({"headshot": False})
        self.assertEqual(upgrade.results.total.additive.crit_chance, 1.2)

        build = Build(
            Upgrade({"name": "CC", "type": "mod", "max_rank": 0, "stats": {"crit_chance": {"value": 0.8, "when": "headshot"}}}),
            Upgrade({"name": "CD", "type": "mod", "max_rank": 0, "stats": {"crit_damage": {"value": 0.8, "when": "headshot"}}}),
        )
        self.assertEqual(build.results.total.additive.crit_chance, 0.8)
        self.assertEqual(build.results.total.additive.crit_damage, 0.8)
        build.configure({"headshot": False})
        self.assertEqual(build.results.total.additive.crit_chance, 0)
        self.assertEqual(build.results.total.additive.crit_damage, 0)

    def test_special_upgrades_keep_calculator_values(self):
        expected = {
            "Charged Chamber": ("primed_chamber", 0.4),
            "Hemorrhage": ("internal_bleeding", 0.35),
            "Hunter Munitions": ("hunter_munitions", 0.3),
            "Internal Bleeding": ("internal_bleeding", 0.35),
            "Melee Doughty": ("melee_doughty", 1),
            "Melee Duplicate": ("melee_duplicate", 1),
            "Primed Chamber": ("primed_chamber", 1),
            "Secondary Encumber": ("secondary_encumber", 0.24),
            "Secondary Enervate": ("secondary_enervate", 6),
            "Vigilante Supplies": ("vigilante_bonus", 0.05),
        }
        for name, (stat, value) in expected.items():
            with self.subTest(name=name):
                self.assertAlmostEqual(arsenal.get(name).results.static.additive[stat], value)

    def test_calculator_uses_largest_faction_damage_bonus(self):
        corpus = arsenal.get("Primed Bane of Corpus")
        grineer = arsenal.get("Bane of Grineer")
        weapon = arsenal.get("Braton").configure(Build(corpus, grineer))

        self.assertEqual(weapon.build.results.total.additive.corpus_damage, 0.55)
        self.assertEqual(weapon.build.results.total.additive.grineer_damage, 0.3)
        attack = weapon.results.main
        self.assertEqual(attack.modded.additive.corpus_damage, 1.55)
        self.assertEqual(attack.effective.corpus_damage, 1.55)
        self.assertEqual(attack.average.corpus_damage, 1.55)
        self.assertEqual(attack.modded.additive.grineer_damage, 1.3)
        self.assertEqual(weapon.results._max_average_faction_damage(attack), 1.55)

    def test_upgrade_stats_accept_scalar_and_single_record_shorthand(self):
        scalar = Upgrade({"name": "Scalar", "type": "mod", "max_rank": 0, "stats": {"damage_bonus": 1.5}})
        record = Upgrade({"name": "Record", "type": "mod", "max_rank": 0, "stats": {"crit_damage": {"value": 2.5, "when": "active"}}})

        self.assertEqual(scalar.results.static.additive.damage_bonus, 1.5)
        self.assertEqual(record.results.conditional.additive.crit_damage, 2.5)
        self.assertEqual(scalar.data.stats.damage_bonus, 1.5)

    def test_upgrade_stats_resolve_effect_modes(self):
        upgrade = Upgrade({
            "name": "Modes",
            "type": "buff",
            "max_rank": 0,
            "stats": {
                "crit_chance": [
                    {"value": 1.2, "mode": "additive"},
                    {"value": 0.2, "mode": "flat"},
                    {"value": 0.5, "mode": "multiplicative"},
                ],
                "crit_damage": {"value": 0.4, "mode": "base"},
            },
        })

        self.assertAlmostEqual(upgrade.results.total.additive.crit_chance, 1.2)
        self.assertAlmostEqual(upgrade.results.total.flat.crit_chance, 0.2)
        self.assertAlmostEqual(upgrade.results.total.multiplicative.crit_chance, 0.5)
        self.assertAlmostEqual(upgrade.results.total.base.crit_damage, 0.4)

    def test_upgrade_stats_default_to_additive_mode(self):
        explicit = Upgrade({"stats": {"crit_chance": {"value": 1.2, "mode": "additive"}}})
        omitted = Upgrade({"stats": {"crit_chance": {"value": 1.2}}})

        self.assertEqual(explicit.results.total.additive.crit_chance, omitted.results.total.additive.crit_chance)

    def test_calculated_stats_use_mode_buckets(self):
        upgrade = Upgrade({
            "stats": {
                "crit_chance": [
                    {"value": 1.2, "mode": "additive"},
                    {"value": 0.2, "mode": "flat"},
                    {"value": 0.5, "mode": "multiplicative"},
                ],
            },
        })
        modded = selected(arsenal.get("Braton").configure(Build(upgrade))).modded

        self.assertGreater(modded.additive.crit_chance, 0)
        self.assertGreaterEqual(modded.additive.status_damage, 1)
        self.assertEqual(modded.flat.crit_chance, 0.2)
        self.assertEqual(modded.multiplicative.crit_chance, 1.5)
        self.assertEqual(set(modded), {"additive", "multiplicative", "base", "flat"})

    def test_upgrade_stats_reject_unknown_modes(self):
        with self.assertRaisesRegex(ValueError, "unsupported effect mode"):
            Upgrade({"stats": {"crit_chance": {"value": 1.2, "mode": "percent"}}})

    def test_upgrade_stats_accept_mixed_scalar_and_record_lists(self):
        upgrade = Upgrade({
            "name": "Mixed",
            "type": "mod",
            "max_rank": 0,
            "stats": {"damage_bonus": [1.5, {"value": 2.5, "when": "active"}]},
        })

        self.assertEqual(upgrade.results.static.additive.damage_bonus, 1.5)
        self.assertEqual(upgrade.results.conditional.additive.damage_bonus, 2.5)
        self.assertEqual(upgrade.results.total.additive.damage_bonus, 4)

        cannonade = arsenal.get("Corinth Prime").configure(Build(
            arsenal.get("Semi-Shotgun Cannonade"),
            arsenal.get("Critical Delay"),
        ))
        self.assertTrue(cannonade.build.results.total.additive.fire_rate_lock)
        self.assertAlmostEqual(selected(cannonade).effective.fire_rate, selected(cannonade).base.fire_rate)

        acuity = Build(arsenal.get("Primary Acuity"))
        self.assertTrue(acuity.results.total.additive.multishot_lock)
        self.assertAlmostEqual(acuity.results.total.multiplicative.weakpoint_crit_chance, 3.498)
        self.assertEqual(acuity.results.total.additive.weakpoint_crit_chance, 0)
        self.assertAlmostEqual(arsenal.get("Furor").results.total.additive.attack_speed, 0.1)

    def test_upgrade_effect_buckets_apply_sensible_defaults(self):
        chamber = arsenal.get("Galvanized Chamber")
        self.assertAlmostEqual(chamber.results.static.additive.multishot, 0.8)
        self.assertAlmostEqual(chamber.results.stacking.additive.multishot, 1.5)
        self.assertAlmostEqual(chamber.results.total.additive.multishot, 2.3)

        no_stacks = Build(arsenal.get("Galvanized Chamber", context={"stacks": 0}))
        self.assertEqual(no_stacks.results.stacking.additive.multishot, 0)
        self.assertAlmostEqual(no_stacks.results.total.additive.multishot, 0.8)

        merciless = arsenal.get("Primary Merciless")
        self.assertAlmostEqual(merciless.results.stacking.additive.damage_bonus, 3.6)
        self.assertAlmostEqual(merciless.results.rank_locked.additive.reload_speed, 0.3)

        conditional = Upgrade({
            "name": "Conditional",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"damage_bonus": [{"value": 1, "when": "kill"}]},
        })
        self.assertEqual(conditional.results.conditional.additive.damage_bonus, 1)
        conditional.data.runtime.kill = False
        disabled = Build(conditional)
        self.assertEqual(disabled.results.conditional.additive.damage_bonus, 0)

    def test_condition_overload_uses_status_cap_and_attack_rules(self):
        condition_overload = Upgrade({
            "name": "Condition Overload",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 1, "stacks": {"when": "status_type", "max": 2}}]},
        })
        base_damage = Upgrade({
            "name": "Base Damage",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"damage_bonus": [{"value": 1}]},
        })
        build = Build(condition_overload, base_damage)

        additive = arsenal.get("Cernos").configure(build, context={"attack": "charged_shot"})
        additive_base = selected(additive).base.damage.total_damage()
        self.assertEqual(additive.data.attacks[additive.data.selected_attack].stats.co_factor, 0.5)
        self.assertEqual(additive.data.attacks[additive.data.selected_attack].stats.co_effect, "adds")
        self.assertGreater(selected(additive).effective.damage.total_damage(), additive_base * 2)
        self.assertLess(selected(additive).effective.damage.total_damage(), additive_base * 3)

        multiplicative = arsenal.get("Coda Bassocyst").configure(build, context={"attack": "normal_attack"})
        multiplicative_base = selected(multiplicative).base.damage.total_damage()
        self.assertEqual(multiplicative.data.attacks[multiplicative.data.selected_attack].stats.co_effect, "multiplies")
        self.assertGreater(selected(multiplicative).effective.damage.total_damage(), multiplicative_base * 2)
        self.assertLess(selected(multiplicative).effective.damage.total_damage(), multiplicative_base * 6)

    def test_condition_overload_database_values_remain_structured(self):
        expected = {
            "Condition Overload": ({"value": 0.8, "mode": "additive", "stacks": {"when": "status_type"}}, {"value": 0.8, "max_stacks": "inf"}),
            "Cull the Weak": ({"value": 0.6, "mode": "additive", "stacks": {"when": "status_type", "max": 3}}, {"value": 0.6, "max_stacks": 3}),
            "Galvanized Aptitude": ({"value": 0.4, "mode": "additive", "stacks": {"when": "on_kill", "max": 2}}, {"value": 0.4, "max_stacks": 2}),
            "Galvanized Savvy": ({"value": 0.4, "mode": "additive", "stacks": {"when": "on_kill", "max": 2}}, {"value": 0.4, "max_stacks": 2}),
            "Galvanized Shot": ({"value": 0.4, "mode": "additive", "stacks": {"when": "on_kill", "max": 3}}, {"value": 0.4, "max_stacks": 3}),
        }
        for name, (canonical, resolved) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(arsenal.upgrades[name]["stats"]["condition_overload"], [canonical])
                self.assertEqual(arsenal.get(name).results.total.additive.condition_overload, resolved)

    def test_condition_overload_bonus_uses_sustained_unique_procs(self):
        condition_overload = Upgrade({
            "name": "Condition Overload",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 0.8, "stacks": {"when": "status_type", "max": 2}}]},
        })
        weapon = arsenal.get("Cernos").configure(Build(condition_overload))

        self.assertGreater(weapon.results._average_condition_overload_bonus(selected(weapon)), 0)
        self.assertLess(weapon.results._average_condition_overload_bonus(selected(weapon)), 1.6)

    def test_condition_overload_scales_with_status_duration(self):
        condition_overload = Upgrade({
            "name": "Condition Overload",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 0.8, "stacks": {"when": "status_type", "max": 3}}]},
        })
        duration = Upgrade({
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
        condition_overload = Upgrade({
            "name": "Condition Overload",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 1, "stacks": {"when": "status_type", "max": 1}}]},
        })
        weapon = Primary({
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
        condition_overload = Upgrade({
            "name": "Condition Overload",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 1, "stacks": {"when": "status_type", "max": 1}}]},
        })
        weapon = Primary({
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
        self.assertEqual(parent.modded.additive.damage_bonus, 1)
        self.assertGreater(child.modded.additive.damage_bonus, 1)

    def test_condition_overload_mod_has_no_status_cap(self):
        heat = Upgrade({
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
        weapon = arsenal.get("Corinth Prime").configure(galvanized_build(), context={"attack": "buckshot"})
        summary = weapon.format.summary()
        upgrades = weapon.format.upgrades()

        self.assertIn("Corinth Prime", summary)
        self.assertIn("Buckshot", summary)
        self.assertIn("TOTAL DPS", summary)
        self.assertIn("Galvanized Chamber", upgrades)
        self.assertIn("shapley", upgrades)
        self.assertIn("removal", upgrades)

    def test_projectile_speed_scales_falloff_without_changing_dps(self):
        base = arsenal.get("Corinth Prime").configure(context={"attack": "buckshot"})
        modded = arsenal.get("Corinth Prime").configure(Build(arsenal.get("Fatal Acceleration")), context={"attack": "buckshot"})
        base_result = selected(base)
        modded_result = selected(modded)

        self.assertAlmostEqual(base_result.effective.start_range, 18)
        self.assertAlmostEqual(base_result.effective.end_range, 36)
        self.assertAlmostEqual(modded_result.effective.projectile_speed, 0.4)
        self.assertAlmostEqual(modded_result.effective.start_range, 18 * 1.4)
        self.assertAlmostEqual(modded_result.effective.end_range, 36 * 1.4)
        self.assertAlmostEqual(base_result.average.total_dps, modded_result.average.total_dps)

    def test_formatter_renders_related_attack_base_and_total_damage(self):
        weapon = arsenal.get("Corinth Prime").configure(context={"attack": "air_burst_projectile"})
        summary = weapon.format.summary()
        blast = next(line for line in summary.splitlines() if line.startswith("AIR BURST EXPLOSION BLAST"))
        total = next(line for line in summary.splitlines() if line.startswith("AIR BURST EXPLOSION TOTAL DAMAGE"))

        self.assertRegex(blast, r"2200\.00\s+\|\s+2200\.00")
        self.assertRegex(total, r"2200\.00\s+\|\s+2200\.00")

    def test_rank_scaled_and_rank_locked_effects_resolve_independently(self):
        upgrade = Upgrade({
            "name": "Hybrid Rank",
            "type": "mod",
            "max_rank": 5,
            "stats": {
                "damage_bonus": 1.65,
                "reload_speed": [{"value": 0.3, "rank": 5}],
            },
        })

        low = upgrade.configure({"rank": 2})
        self.assertAlmostEqual(low.results.static.additive.damage_bonus, 1.65 * 3 / 6)
        self.assertEqual(low.results.rank_locked.additive.reload_speed, 0)
        self.assertAlmostEqual(low.results.total.additive.damage_bonus, 1.65 * 3 / 6)

        high = upgrade.configure({"rank": 5})
        self.assertAlmostEqual(high.results.static.additive.damage_bonus, 1.65)
        self.assertEqual(high.results.rank_locked.additive.reload_speed, 0.3)
        self.assertAlmostEqual(high.results.total.additive.damage_bonus, 1.65)
        self.assertAlmostEqual(high.results.total.additive.reload_speed, 0.3)

        merciless = arsenal.get("Primary Merciless", context={"rank": 2, "stacks": 12})
        self.assertAlmostEqual(merciless.results.stacking.additive.damage_bonus, 0.3 * 3 / 6 * 12)
        self.assertEqual(merciless.results.rank_locked.additive.reload_speed, 0)

        rank_locked = Upgrade({"stats": {"crit_chance": {"value": 2, "rank": 10}}, "max_rank": 11})
        rank_locked.configure({"rank": 10})
        self.assertEqual(rank_locked.results.rank_locked.additive.crit_chance, 2)
        self.assertEqual(rank_locked.results.total.additive.crit_chance, 2)
        rank_locked.configure({"rank": 9})
        self.assertEqual(rank_locked.results.total.additive.crit_chance, 0)

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

        different = Upgrade({"name": "Serration", "type": "mod", "max_rank": 10, "stats": {"damage_bonus": 0.1}})
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

        upgrade = Upgrade({"name": "Proto", "type": "mod", "max_rank": 0, "stats": {"damage_bonus": 1}})
        weapon = arsenal.get("Braton")

        self.assertIsInstance(upgrade, UpgradeOwner)
        self.assertIsInstance(weapon, WeaponCalculatorOwner)
        self.assertIsInstance(weapon, ConfigurableWeaponOwner)
        self.assertIsInstance(weapon, WeaponFormatterOwner)
        self.assertEqual(UpgradeCalculator(upgrade).total.additive.damage_bonus, 1)
        self.assertEqual(weapon.results.main.name, weapon.data.selected_attack)
        self.assertIn(weapon.data.name, weapon.format.summary())

    def test_effect_buckets_aggregate_independently(self):
        upgrade = Upgrade({
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

        self.assertAlmostEqual(upgrade.results.static.additive.damage_bonus, 0.30)
        self.assertAlmostEqual(upgrade.results.conditional.additive.damage_bonus, 0.20)
        self.assertAlmostEqual(upgrade.results.stacking.additive.damage_bonus, 0.20)
        self.assertAlmostEqual(upgrade.results.rank_locked.additive.damage_bonus, 0.25)
        self.assertAlmostEqual(upgrade.results.modular.additive.damage_bonus, 0.15)
        self.assertAlmostEqual(upgrade.results.total.additive.damage_bonus, 1.10)

        alone = Upgrade(upgrade.data.copy())
        alone.data.runtime.update({"rank": 5, "headshot": True, "kill": 2})
        alone.results.resolve()
        self.assertEqual(alone.results.modular.additive.damage_bonus, 0)
        self.assertAlmostEqual(alone.results.total.additive.damage_bonus, 0.95)

    def test_condition_overload_applies_before_modded_damage(self):
        from warframe_damage_calculator.calculators.weapon_calculator import WeaponCalculator

        condition_overload = Upgrade({
            "name": "CO",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 1, "stacks": {"when": "status_type", "max": 1}}]},
        })
        weapon = Primary({
            "name": "CO Order",
            "type": "primary",
            "attacks": {
                "shot": {"stats": {"damage": {"heat": 100}, "status_chance": 1, "fire_rate": 1, "multishot": 1}},
            },
        }).configure(Build(condition_overload))

        result = weapon.results.main
        self.assertGreater(result.modded.additive.damage_bonus, 1)
        expected_damage = result.modded.additive.damage_bonus * result.base.damage.apply(result.build.additive.damage).combine().sorted()
        self.assertEqual(dict(result.modded.additive.damage), dict(expected_damage))

        damage_assignments: list[float] = []
        original = WeaponCalculator._compute_modded_damage
        test_case = self

        def tracked(calculator, attack_result):
            damage_assignments.append(attack_result.modded.additive.damage_bonus)
            original(calculator, attack_result)
            test_case.assertEqual(
                dict(attack_result.modded.additive.damage),
                dict(attack_result.modded.additive.damage_bonus * attack_result.base.damage.apply(attack_result.build.additive.damage).combine().sorted()),
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
        self.assertEqual(fresh.modded.additive.damage.total_damage(), 0)
        model = calculator._sustained_status_model(fresh)
        calculator._apply_status_effect_stacks(fresh, model)
        calculator._apply_condition_overload(fresh, model)
        calculator._compute_modded_damage(fresh)
        self.assertGreater(fresh.modded.additive.damage.total_damage(), 0)
        self.assertIsInstance(calculator, WeaponCalculator)

    def test_status_effect_stacks_database_shape(self):
        frostbite = arsenal.upgrades["Primary Frostbite"]["stats"]["status_effect_stacks"]
        self.assertEqual(frostbite, [
            {"value": 0.03, "stat": "crit_damage", "mode": "additive", "status": "cold", "max_stacks": 40},
            {"value": 0.022, "stat": "multishot", "mode": "additive", "status": "cold", "max_stacks": 40},
        ])
        resolved = arsenal.get("Primary Frostbite").results.total.additive.status_effect_stacks
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0]["status"], "cold")
        self.assertEqual(resolved[0]["stat"], "crit_damage")

    def test_status_effect_stacks_use_sustained_procs(self):
        cold = Upgrade({"name": "Cold", "type": "mod", "max_rank": 0, "stats": {"cold": [{"value": 1.0}]}})
        without = arsenal.get("Braton").configure(Build(cold))
        with_arcane = arsenal.get("Braton").configure(Build(cold, arsenal.get("Primary Frostbite")))
        self.assertGreater(selected(with_arcane).effective.crit_damage, selected(without).effective.crit_damage)
        self.assertGreater(selected(with_arcane).effective.multishot, selected(without).effective.multishot)

    def test_status_effect_stacks_runtime_override(self):
        cold = Upgrade({"name": "Cold", "type": "mod", "max_rank": 0, "stats": {"cold": [{"value": 1.0}]}})
        auto = arsenal.get("Braton").configure(Build(cold, arsenal.get("Primary Frostbite")))
        capped = arsenal.get("Braton").configure(Build(cold, arsenal.get("Primary Frostbite")), context={"on_cold_status_effect": 40})
        zero = arsenal.get("Braton").configure(Build(cold, arsenal.get("Primary Frostbite")), context={"on_cold_status_effect": 0})
        self.assertGreater(selected(capped).effective.crit_damage, selected(auto).effective.crit_damage)
        self.assertAlmostEqual(selected(zero).effective.crit_damage, selected(arsenal.get("Braton").configure(Build(cold))).effective.crit_damage)


if __name__ == "__main__":
    unittest.main()
