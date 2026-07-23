import unittest
from types import MappingProxyType
from typing import get_args

from warframe_damage_calculator import Build, Primary, Upgrade, Weapon, arsenal
from warframe_damage_calculator.loader.bundled_names import MeleeName, PrimaryName, SecondaryName, UpgradeName
from warframe_damage_calculator.models.data import Data
from warframe_damage_calculator.models.dist import Dist
from warframe_damage_calculator.fields.attack_result import AttackResult
from warframe_damage_calculator.fields.calculated import CalculatedStats
from warframe_damage_calculator.fields.dist_data import DistData
from warframe_damage_calculator.fields.upgrade import ResolvedStat
from warframe_damage_calculator.fields.weapon_data import Attack, Attacks, Evolutions


def galvanized_build() -> Build:
    return Build(
        arsenal.get("Galvanized Chamber", context={"stacks": 5}),
        arsenal.get("Galvanized Aptitude", context={"stacks": 2}),
    )


def selected(weapon: Weapon):
    return weapon.stats.attacks[weapon._attack]


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

        for distribution in (attack.stats.damage, attack.stats.forced_procs, CalculatedStats().damage, resolved.damage):
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
        self.assertIn("normal", weapon.stats.attacks)

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

    def test_arsenal_loads_fresh_weapons_and_safe_upgrades(self):
        first = arsenal.get("Corinth Prime")
        second = arsenal.get("Corinth Prime")
        mod = arsenal.get("Galvanized Chamber")

        self.assertIsInstance(first, Primary)
        self.assertIsInstance(mod, Upgrade)
        self.assertIsNot(first, second)
        first.configure(attack="air_burst_projectile")
        self.assertEqual(second._attack, "buckshot")

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
        self.assertTrue(hasattr(weapon, "stats"))
        self.assertFalse(hasattr(weapon, "attacks"))
        self.assertTrue(hasattr(weapon.stats, "attacks"))
        self.assertFalse(hasattr(weapon.stats, "final"))
        for attribute in ("base", "modded", "effective", "average", "final", "children"):
            self.assertTrue(hasattr(next(iter(weapon.stats.attacks.values())), attribute))
        for attribute in ("base", "modded", "effective", "average", "children", "parent", "child"):
            self.assertFalse(hasattr(weapon.stats, attribute))
        for attribute in ("type", "subtype", "base", "moded", "modded", "effective", "total_dps", "calculation_build"):
            self.assertFalse(hasattr(weapon, attribute))
        self.assertTrue(all(attack.name == key for key, attack in weapon.data.attacks.items()))
        self.assertEqual(set(weapon.stats.attacks), set(weapon.data.attacks))
        self.assertEqual(weapon.data.ammo.reload_time, 3)
        self.assertEqual(weapon.data.ammo.magazine_size, 20)
        self.assertNotIn("damage", weapon.data.ammo)
        self.assertEqual(weapon.data.attacks[weapon._attack].stats.damage.total_damage(), 90)
        self.assertNotIn("reload_time", weapon.data.attacks[weapon._attack].stats)

    def test_default_mode_switching(self):
        weapon = arsenal.get("Corinth Prime")
        self.assertEqual(weapon._attack, "buckshot")

        self.assertIs(weapon.configure(attack="air_burst_projectile"), weapon)
        self.assertEqual(weapon.data.attacks[weapon._attack].children, ["air_burst_explosion"])
        self.assertEqual(selected(weapon).base.damage.total_damage(), 100)
        self.assertEqual(weapon.stats.attacks.air_burst_explosion.effective.damage.total_damage(), 2200)
        self.assertIs(weapon.stats.attacks.air_burst_explosion.attack, weapon.data.attacks.air_burst_explosion)

    def test_mode_specific_stats_and_global_ranged_stats(self):
        weapon = arsenal.get("Corinth Prime").configure(attack="buckshot")
        mode = weapon.data.attacks[weapon._attack].stats

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
        weapon = arsenal.get("Corinth Prime").configure(attack="air_burst_projectile")
        related = weapon.data.attacks.air_burst_explosion
        related.stats.fire_rate = 2
        weapon.stats.recompute()

        self.assertNotEqual(
            weapon.stats._effective_attacks_per_second(selected(weapon)),
            weapon.stats._effective_attacks_per_second(weapon.stats.attacks.air_burst_explosion),
        )

    def test_selected_and_child_attacks_use_independent_buckets(self):
        weapon = arsenal.get("Corinth Prime").configure(attack="air_burst_projectile")
        parent = selected(weapon)
        child = weapon.stats.attacks.air_burst_explosion

        self.assertIs(parent.attack, weapon.data.attacks[weapon._attack])
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
        parent = weapon.stats.attacks.parent
        child = weapon.stats.attacks.child
        grandchild = weapon.stats.attacks.grandchild

        self.assertNotEqual(parent.effective.crit_chance, child.effective.crit_chance)
        self.assertNotEqual(child.effective.status_chance, grandchild.effective.status_chance)
        expected_dph = sum(bucket.average.flat_dph for bucket in (parent, child, grandchild))
        self.assertAlmostEqual(parent.final.flat_dph, expected_dph)
        self.assertAlmostEqual(
            parent.final.flat_dps,
            weapon.stats._effective_attacks_per_second(parent) * expected_dph,
        )
        self.assertNotEqual(parent.final.flat_dps, sum(bucket.average.flat_dps for bucket in (parent, child, grandchild)))
        expected_dotph = sum(bucket.average.flat_dotph for bucket in (parent, child, grandchild))
        self.assertGreater(expected_dotph, 0)
        self.assertAlmostEqual(parent.final.flat_dotph, expected_dotph)
        self.assertAlmostEqual(parent.final.total_dph, expected_dph + expected_dotph)
        self.assertAlmostEqual(parent.final.flat_dotps, weapon.stats._effective_attacks_per_second(parent) * expected_dotph)
        self.assertAlmostEqual(child.final.flat_dph, child.average.flat_dph + grandchild.average.flat_dph)
        self.assertAlmostEqual(grandchild.final.flat_dph, grandchild.average.flat_dph)

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
        parent = weapon.stats.attacks.parent
        child = weapon.stats.attacks.child

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
        weapon = arsenal.get("Ceramic Dagger").configure(attack="spectral_dagger")

        self.assertIs(weapon.stats.attacks.spectral_dagger_explosion.attack, weapon.data.attacks.spectral_dagger_explosion)
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
            with_duplicate.stats._average_condition_overload_bonus(selected(with_duplicate)),
            without_duplicate.stats._average_condition_overload_bonus(selected(without_duplicate)),
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
        build.stats.resolve()
        self.assertGreater(selected(weapon).effective.multishot, base_multishot)

    def test_build_iteration_addition_and_subtraction_remain_available(self):
        chamber = arsenal.get("Galvanized Chamber", context={"stacks": 5})
        aptitude = arsenal.get("Galvanized Aptitude")
        build = Build(chamber) + aptitude

        self.assertEqual(len(list(build)), 2)
        reduced = build - chamber
        self.assertEqual([upgrade.data.name for upgrade in reduced], ["Galvanized Aptitude"])

    def test_contribution_recomputes_through_attack_buckets_and_restores_build(self):
        serration = arsenal.get("Serration")
        weapon = arsenal.get("Braton").configure(Build(serration))
        full_dps = selected(weapon).final.total_dps

        self.assertGreater(weapon.stats.contribution(serration), 0)
        self.assertAlmostEqual(selected(weapon).final.total_dps, full_dps)
        self.assertEqual([upgrade.data.name for upgrade in weapon.build], ["Serration"])
        self.assertGreater(weapon.stats.contribution_values()["Serration"], 0)

    def test_build_has_one_canonical_upgrade_collection(self):
        build = galvanized_build()

        self.assertFalse(hasattr(build, "data"))
        self.assertTrue(build.upgrades)

    def test_upgrade_copy_preserves_runtime_without_sharing_data(self):
        upgrade = arsenal.get("Galvanized Chamber", context={"stacks": 3})
        copied = upgrade.copy()

        self.assertEqual(copied.data.runtime.stacks, 3)
        self.assertIsNot(copied.data, upgrade.data)
        copied.data.stats.multishot = 99
        self.assertNotEqual(copied.data.stats.multishot, upgrade.data.stats.multishot)

    def test_configure_attack_and_build_are_order_independent(self):
        build = galvanized_build()
        first = arsenal.get("Corinth Prime").configure(build, attack="air_burst_projectile")
        second = arsenal.get("Corinth Prime").configure(attack="air_burst_projectile").configure(build)

        self.assertEqual(selected(first).effective, selected(second).effective)
        self.assertAlmostEqual(selected(first).final.total_dps, selected(second).final.total_dps, places=6)

    def test_incarnon_evolution_selection_recomputes(self):
        weapon = arsenal.get("Telos Boltor")
        self.assertIsInstance(weapon.data.evolutions, Evolutions)
        initial_damage = selected(weapon).effective.damage.total_damage()

        self.assertIs(weapon.configure(evolutions={2: 1}), weapon)
        self.assertEqual(weapon._evolutions, {2: 1})
        self.assertGreater(selected(weapon).effective.damage.total_damage(), initial_damage)

    def test_upgrade_and_build_configure_update_runtime_conditions(self):
        upgrade = Upgrade({"name": "Headshot", "type": "mod", "max_rank": 0, "stats": {"crit_chance": [1.2, {"value": 0.8, "when": "headshot"}]}})
        self.assertEqual(upgrade.stats.total.crit_chance, 2.0)
        upgrade.configure({"headshot": False})
        self.assertEqual(upgrade.stats.total.crit_chance, 1.2)

        build = Build(
            Upgrade({"name": "CC", "type": "mod", "max_rank": 0, "stats": {"crit_chance": {"value": 0.8, "when": "headshot"}}}),
            Upgrade({"name": "CD", "type": "mod", "max_rank": 0, "stats": {"crit_damage": {"value": 0.8, "when": "headshot"}}}),
        )
        self.assertEqual(build.stats.total.crit_chance, 0.8)
        self.assertEqual(build.stats.total.crit_damage, 0.8)
        build.configure({"headshot": False})
        self.assertEqual(build.stats.total.crit_chance, 0)
        self.assertEqual(build.stats.total.crit_damage, 0)

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
                self.assertAlmostEqual(arsenal.get(name).stats.static[stat], value)

    def test_calculator_uses_largest_faction_damage_bonus(self):
        corpus = arsenal.get("Primed Bane of Corpus")
        grineer = arsenal.get("Bane of Grineer")
        weapon = arsenal.get("Braton").configure(Build(corpus, grineer))

        self.assertEqual(weapon.build.stats.total.corpus_damage, 0.55)
        self.assertEqual(weapon.build.stats.total.grineer_damage, 0.3)
        attack = weapon.stats.attacks[weapon._attack]
        self.assertEqual(attack.modded.corpus_damage, 1.55)
        self.assertEqual(attack.effective.corpus_damage, 1.55)
        self.assertEqual(attack.average.corpus_damage, 1.55)
        self.assertEqual(attack.modded.grineer_damage, 1.3)
        self.assertEqual(weapon.stats._max_average_faction_damage(attack), 1.55)

    def test_upgrade_stats_accept_scalar_and_single_record_shorthand(self):
        scalar = Upgrade({"name": "Scalar", "type": "mod", "max_rank": 0, "stats": {"base_damage": 1.5}})
        record = Upgrade({"name": "Record", "type": "mod", "max_rank": 0, "stats": {"crit_damage": {"value": 2.5, "when": "active"}}})

        self.assertEqual(scalar.stats.static.base_damage, 1.5)
        self.assertEqual(record.stats.conditional.crit_damage, 2.5)
        self.assertEqual(scalar.data.stats.base_damage, 1.5)

    def test_upgrade_stats_accept_mixed_scalar_and_record_lists(self):
        upgrade = Upgrade({
            "name": "Mixed",
            "type": "mod",
            "max_rank": 0,
            "stats": {"base_damage": [1.5, {"value": 2.5, "when": "active"}]},
        })

        self.assertEqual(upgrade.stats.static.base_damage, 1.5)
        self.assertEqual(upgrade.stats.conditional.base_damage, 2.5)
        self.assertEqual(upgrade.stats.total.base_damage, 4)

        cannonade = arsenal.get("Corinth Prime").configure(Build(
            arsenal.get("Semi-Shotgun Cannonade"),
            arsenal.get("Critical Delay"),
        ))
        self.assertTrue(cannonade.build.stats.total.fire_rate_lock)
        self.assertAlmostEqual(selected(cannonade).effective.fire_rate, selected(cannonade).base.fire_rate)

        acuity = Build(arsenal.get("Primary Acuity"))
        self.assertTrue(acuity.stats.total.multishot_lock)
        self.assertAlmostEqual(acuity.stats.total.multiplicative_weakpoint_crit_chance, 3.498)
        self.assertEqual(acuity.stats.total.weakpoint_crit_chance, 0)
        self.assertAlmostEqual(arsenal.get("Furor").stats.total.attack_speed, 0.1)

    def test_upgrade_effect_buckets_apply_sensible_defaults(self):
        chamber = arsenal.get("Galvanized Chamber")
        self.assertAlmostEqual(chamber.stats.static.multishot, 0.8)
        self.assertAlmostEqual(chamber.stats.stacking.multishot, 1.5)
        self.assertAlmostEqual(chamber.stats.total.multishot, 2.3)

        no_stacks = Build(arsenal.get("Galvanized Chamber", context={"stacks": 0}))
        self.assertEqual(no_stacks.stats.stacking.multishot, 0)
        self.assertAlmostEqual(no_stacks.stats.total.multishot, 0.8)

        merciless = arsenal.get("Primary Merciless")
        self.assertAlmostEqual(merciless.stats.stacking.base_damage, 3.6)
        self.assertAlmostEqual(merciless.stats.rank_locked.reload_speed, 0.3)

        conditional = Upgrade({
            "name": "Conditional",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"base_damage": [{"value": 1, "when": "kill"}]},
        })
        self.assertEqual(conditional.stats.conditional.base_damage, 1)
        conditional.data.runtime.kill = False
        disabled = Build(conditional)
        self.assertEqual(disabled.stats.conditional.base_damage, 0)

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
            "stats": {"base_damage": [{"value": 1}]},
        })
        build = Build(condition_overload, base_damage)

        additive = arsenal.get("Cernos").configure(build, attack="charged_shot")
        additive_base = selected(additive).base.damage.total_damage()
        self.assertEqual(additive.data.attacks[additive._attack].stats.co_factor, 0.5)
        self.assertEqual(additive.data.attacks[additive._attack].stats.co_effect, "adds")
        self.assertGreater(selected(additive).effective.damage.total_damage(), additive_base * 2)
        self.assertLess(selected(additive).effective.damage.total_damage(), additive_base * 3)

        multiplicative = arsenal.get("Coda Bassocyst").configure(build, attack="normal_attack")
        multiplicative_base = selected(multiplicative).base.damage.total_damage()
        self.assertEqual(multiplicative.data.attacks[multiplicative._attack].stats.co_effect, "multiplies")
        self.assertGreater(selected(multiplicative).effective.damage.total_damage(), multiplicative_base * 2)
        self.assertLess(selected(multiplicative).effective.damage.total_damage(), multiplicative_base * 6)

    def test_condition_overload_database_values_remain_structured(self):
        expected = {
            "Condition Overload": ({"value": 0.8, "stacks": {"when": "status_type"}}, {"value": 0.8, "max_stacks": "inf"}),
            "Cull the Weak": ({"value": 0.6, "stacks": {"when": "status_type", "max": 3}}, {"value": 0.6, "max_stacks": 3}),
            "Galvanized Aptitude": ({"value": 0.4, "stacks": {"when": "on_kill", "max": 2}}, {"value": 0.4, "max_stacks": 2}),
            "Galvanized Savvy": ({"value": 0.4, "stacks": {"when": "on_kill", "max": 2}}, {"value": 0.4, "max_stacks": 2}),
            "Galvanized Shot": ({"value": 0.4, "stacks": {"when": "on_kill", "max": 3}}, {"value": 0.4, "max_stacks": 3}),
        }
        for name, (canonical, resolved) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(arsenal.upgrades[name]["stats"]["condition_overload"], [canonical])
                self.assertEqual(arsenal.get(name).stats.total.condition_overload, resolved)

    def test_condition_overload_bonus_uses_expected_stacks_over_five_seconds(self):
        condition_overload = Upgrade({
            "name": "Condition Overload",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 0.8, "stacks": {"when": "status_type", "max": 2}}]},
        })
        weapon = arsenal.get("Cernos").configure(Build(condition_overload))

        self.assertGreater(weapon.stats._average_condition_overload_bonus(selected(weapon)), 0)
        self.assertLess(weapon.stats._average_condition_overload_bonus(selected(weapon)), 1.6)

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
        parent = weapon.stats.attacks.parent
        child = weapon.stats.attacks.child

        self.assertEqual(weapon.stats._average_condition_overload_bonus(parent), 0)
        self.assertGreater(weapon.stats._average_condition_overload_bonus(child), 0)
        self.assertEqual(parent.modded.base_damage, 1)
        self.assertGreater(child.modded.base_damage, 1)

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
        weapon = arsenal.get("Corinth Prime").configure(galvanized_build(), attack="buckshot")
        summary = weapon.format.summary()
        upgrades = weapon.format.upgrades()

        self.assertIn("Corinth Prime", summary)
        self.assertIn("Buckshot", summary)
        self.assertIn("TOTAL DPS", summary)
        self.assertIn("Galvanized Chamber", upgrades)

    def test_formatter_renders_related_attack_base_and_total_damage(self):
        weapon = arsenal.get("Corinth Prime").configure(attack="air_burst_projectile")
        summary = weapon.format.summary()
        blast = next(line for line in summary.splitlines() if line.startswith("Air Burst Explosion BLAST:"))
        total = next(line for line in summary.splitlines() if line.startswith("Air Burst Explosion TOTAL DAMAGE:"))

        self.assertRegex(blast, r"2200\.00\s+-> 2200\.00$")
        self.assertRegex(total, r"2200\.00\s+-> 2200\.00$")


if __name__ == "__main__":
    unittest.main()
