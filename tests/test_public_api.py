import unittest
from types import MappingProxyType
from typing import get_args

from warframe_damage_calculator import Build, Primary, Upgrade, Weapon, arsenal
from warframe_damage_calculator.loader.bundled_names import MeleeName, PrimaryName, SecondaryName, UpgradeName
from warframe_damage_calculator.models.data import Data
from warframe_damage_calculator.models.dist import Dist
from warframe_damage_calculator.models.fields import Attack, AttackBucket, Attacks, CalculatedStats, DistData, Evolutions, ResolvedStat


def galvanized_build() -> Build:
    return Build(
        arsenal.get("Galvanized Chamber", context={"stacks": 5}),
        arsenal.get("Galvanized Aptitude", context={"stacks": 2}),
    )


class DataDefaults(Data):
    children: list[Data] = []
    stats: CalculatedStats = CalculatedStats()
    label: str = "base"


class OverriddenDataDefaults(DataDefaults):
    children: list[Data] = [Data({"source": "override"})]
    label: str = "child"


class PublicApiTests(unittest.TestCase):
    def test_data_accepts_generic_mappings_keywords_and_converts_assignments(self):
        source = MappingProxyType({"nested": {"value": 1}})
        data = Data(source, extra={"value": 2})

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
        first.stats.damage = Dist(impact=100)
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

    def test_attack_bucket_defaults_and_copy_are_independent(self):
        first = AttackBucket()
        second = AttackBucket()

        first.children.append(AttackBucket())
        first.base.damage = Dist(impact=100)
        copied = first.copy()
        self.assertEqual(second.children, [])
        self.assertNotEqual(second.base.damage, first.base.damage)
        self.assertIsInstance(first.build, ResolvedStat)
        self.assertIs(type(copied), AttackBucket)
        self.assertIsNot(copied.children, first.children)
        self.assertIsNot(copied.children[0], first.children[0])

    def test_generic_weapon_uses_the_shared_calculation_pipeline(self):
        weapon = Weapon({"Test Weapon": {"type": "test", "attacks": {"normal": {"stats": {"damage": {"impact": 10}}}}}})

        self.assertEqual(weapon.stats.parent.effective.damage.total_damage(), 10)
        self.assertEqual(weapon.stats.child, [])

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
            PrimaryName: {name for name, data in arsenal.weapons.items() if data["type"] in {"primary", "archgun"}},
            SecondaryName: {name for name, data in arsenal.weapons.items() if data["type"] == "secondary"},
            MeleeName: {name for name, data in arsenal.weapons.items() if data["type"] == "melee"},
            UpgradeName: set(arsenal.upgrades),
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
        first.set_mode("Air Burst Projectile")
        self.assertIs(second.mode, second.data.entry.attacks.buckshot)

        mod.data.runtime.stacks = 99
        self.assertIsNone(arsenal.get("Galvanized Chamber").data.runtime.get("stacks"))

    def test_weapon_data_separates_global_stats_and_attacks(self):
        weapon = arsenal.get("Corinth Prime")

        self.assertEqual(weapon.data.name, "Corinth Prime")
        self.assertEqual(weapon.data.entry.type, "primary")
        self.assertEqual(weapon.data.entry.subtype, "shotgun")
        self.assertIsInstance(weapon.data.entry.attacks, Attacks)
        self.assertTrue(all(isinstance(attack, Attack) for attack in weapon.data.entry.attacks.values()))
        self.assertFalse(hasattr(weapon, "context"))
        self.assertFalse(hasattr(weapon, "mode_name"))
        self.assertTrue(hasattr(weapon, "stats"))
        self.assertFalse(hasattr(weapon, "attacks"))
        for attribute in ("base", "modded", "effective"):
            self.assertFalse(hasattr(weapon.stats, attribute))
        for attribute in ("type", "subtype", "base", "moded", "modded", "effective", "total_dps", "calculation_build"):
            self.assertFalse(hasattr(weapon, attribute))
        self.assertEqual(weapon.data.entry.ammo.reload_time, 3)
        self.assertEqual(weapon.data.entry.ammo.magazine_size, 20)
        self.assertNotIn("damage", weapon.data.entry.ammo)
        self.assertEqual(weapon.mode.stats.damage.total_damage(), 90)
        self.assertNotIn("reload_time", weapon.mode.stats)

    def test_default_mode_switching(self):
        weapon = arsenal.get("Corinth Prime")
        self.assertIs(weapon.mode, weapon.data.entry.attacks.buckshot)

        self.assertIs(weapon.set_mode("Air Burst Projectile"), weapon)
        self.assertEqual(weapon.mode.children, ["air_burst_explosion"])
        self.assertEqual(weapon.stats.parent.base.damage.total_damage(), 100)
        self.assertEqual(weapon.stats.child[0].effective.damage.total_damage(), 2200)
        self.assertIs(weapon.stats.child[0].attack, weapon.data.entry.attacks.air_burst_explosion)

    def test_mode_specific_stats_and_global_ranged_stats(self):
        weapon = arsenal.get("Corinth Prime").set_mode("Buckshot")
        mode = weapon.mode.stats

        self.assertAlmostEqual(mode.crit_chance, 0.3)
        self.assertAlmostEqual(mode.status_chance, 0.09)
        self.assertAlmostEqual(mode.fire_rate, 1.42)
        self.assertEqual(mode.co_factor, 1)
        self.assertEqual(mode.co_effect, "adds")
        self.assertEqual(weapon.stats.parent.base.magazine_capacity, 20)
        self.assertEqual(weapon.stats.parent.base.reload_speed, 3)

        battery = arsenal.get("Tenet Cycron")
        self.assertIn("recharge_delay", battery.data.entry.ammo)
        self.assertAlmostEqual(battery.data.entry.ammo.recharge_rate, 26.66666667)
        self.assertAlmostEqual(battery.stats.parent.base.recharge_rate, 26.66666667)

    def test_related_attacks_use_their_own_average_fire_rate(self):
        weapon = arsenal.get("Corinth Prime").set_mode("Air Burst Projectile")
        related = weapon.data.entry.attacks.air_burst_explosion
        related.stats.fire_rate = 2

        self.assertNotEqual(
            weapon.stats._effective_fire_rate(weapon.stats.parent),
            weapon.stats._effective_fire_rate(weapon.stats.child[0]),
        )

    def test_selected_and_child_attacks_use_independent_buckets(self):
        weapon = arsenal.get("Corinth Prime").set_mode("Air Burst Projectile")
        parent = weapon.stats.parent
        child = weapon.stats.child[0]

        self.assertIs(parent.attack, weapon.mode)
        self.assertIsNot(parent.average, weapon.stats.average)
        self.assertIs(child.attack, weapon.data.entry.attacks.air_burst_explosion)
        self.assertNotEqual(parent.base.damage, child.base.damage)
        self.assertIsNot(parent.average, child.average)

    def test_combined_average_recurses_and_uses_parent_fire_rate(self):
        weapon = Primary({"Nested": {
            "type": "primary",
            "ammo": {"magazine_size": 10, "reload_time": 1},
            "attacks": {
                "parent": {"children": ["child"], "stats": {"damage": {"slash": 10}, "fire_rate": 2}},
                "child": {"children": ["grandchild"], "stats": {"damage": {"slash": 20}, "fire_rate": 5, "crit_chance": 0.5, "crit_damage": 2, "status_chance": 0.5}},
                "grandchild": {"stats": {"damage": {"slash": 30}, "fire_rate": 9, "status_chance": 0.75}},
            },
        }})
        parent = weapon.stats.parent
        child = weapon.stats.child[0]
        grandchild = child.children[0]

        self.assertNotEqual(parent.effective.crit_chance, child.effective.crit_chance)
        self.assertNotEqual(child.effective.status_chance, grandchild.effective.status_chance)
        expected_dph = sum(bucket.average.flat_dph for bucket in (parent, child, grandchild))
        self.assertAlmostEqual(weapon.stats.average.flat_dph, expected_dph)
        self.assertAlmostEqual(
            weapon.stats.average.flat_dps,
            weapon.stats._effective_fire_rate(parent) * expected_dph,
        )
        self.assertNotEqual(weapon.stats.average.flat_dps, sum(bucket.average.flat_dps for bucket in (parent, child, grandchild)))
        expected_dotph = sum(bucket.average.flat_dotph for bucket in (parent, child, grandchild))
        self.assertGreater(expected_dotph, 0)
        self.assertAlmostEqual(weapon.stats.average.flat_dotph, expected_dotph)
        self.assertAlmostEqual(weapon.stats.average.total_dph, expected_dph + expected_dotph)
        self.assertAlmostEqual(weapon.stats.average.flat_dotps, weapon.stats._effective_fire_rate(parent) * expected_dotph)

    def test_attack_relationship_cycles_are_detected_by_name(self):
        with self.assertRaisesRegex(ValueError, "cyclic attack relationship detected: parent"):
            Primary({"Cycle": {
                "type": "primary",
                "attacks": {
                    "parent": {"children": ["child"], "stats": {"damage": {"impact": 10}}},
                    "child": {"children": ["parent"], "stats": {"damage": {"impact": 20}}},
                },
            }})

    def test_beam_behavior_is_local_to_each_attack_bucket(self):
        weapon = Primary({"Mixed Delivery": {
            "type": "primary",
            "attacks": {
                "parent": {"delivery": "hitscan", "children": ["child"], "stats": {"damage": {"impact": 10}, "multishot": 2}},
                "child": {"delivery": "beam", "stats": {"damage": {"heat": 20}, "multishot": 3}},
            },
        }})
        parent = weapon.stats.parent
        child = weapon.stats.child[0]

        self.assertEqual(parent.average.beam_dot_multiplier, 1)
        self.assertEqual(child.average.beam_dot_multiplier, child.effective.multishot)
        self.assertEqual(parent.effective.ammo_efficiency, 0)
        self.assertEqual(child.effective.ammo_efficiency, 0.5)

    def test_multiple_child_attacks_are_combined_once(self):
        weapon = Primary({"Multiple Children": {
            "type": "primary",
            "attacks": {
                "parent": {"children": ["first", "second"], "stats": {"damage": {"impact": 10}}},
                "first": {"stats": {"damage": {"impact": 20}}},
                "second": {"stats": {"damage": {"impact": 30}}},
            },
        }})

        self.assertEqual(len(weapon.stats.child), 2)
        self.assertAlmostEqual(weapon.stats.average.flat_dph, 60)

    def test_melee_weapons_include_related_attacks(self):
        weapon = arsenal.get("Ceramic Dagger").set_mode("Spectral Dagger")

        self.assertIs(weapon.stats.child[0].attack, weapon.data.entry.attacks.spectral_dagger_explosion)
        self.assertGreater(weapon.stats.average.flat_dph, weapon.stats.parent.effective.damage.total_damage())

    def test_melee_duplicate_increases_condition_overload_status_acquisition(self):
        condition_overload = arsenal.get("Condition Overload")
        duplicate = Upgrade({"Duplicate": {
            "type": "arcane", "max_rank": 0, "compatibility": {"types": []},
            "stats": {"melee_duplicate": [{"value": 1}]},
        }})
        without_duplicate = arsenal.get("Skana").configure(Build(condition_overload))
        with_duplicate = arsenal.get("Skana").configure(Build(condition_overload, duplicate))

        self.assertGreater(
            with_duplicate.stats._average_condition_overload_bonus(with_duplicate.stats.parent),
            without_duplicate.stats._average_condition_overload_bonus(without_duplicate.stats.parent),
        )
        self.assertGreater(with_duplicate.stats.average.flat_dotph, without_duplicate.stats.average.flat_dotph)

    def test_build_configuration_copies_and_recomputes(self):
        build = galvanized_build()
        weapon = arsenal.get("Corinth Prime")
        base_multishot = weapon.stats.parent.effective.multishot
        base_damage = weapon.stats.parent.effective.damage.total_damage()

        self.assertIs(weapon.configure(build), weapon)
        self.assertIsNot(weapon.build, build)
        self.assertGreater(weapon.stats.parent.effective.multishot, base_multishot)
        self.assertGreater(weapon.stats.parent.effective.damage.total_damage(), base_damage)

        for upgrade in build.upgrades:
            upgrade.data.runtime.stacks = 0
        build.stats.resolve()
        self.assertGreater(weapon.stats.parent.effective.multishot, base_multishot)

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
        full_dps = weapon.stats.average.total_dps

        self.assertGreater(weapon.stats.contribution(serration), 0)
        self.assertAlmostEqual(weapon.stats.average.total_dps, full_dps)
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
        self.assertIsNot(copied.data.entry, upgrade.data.entry)
        copied.data.entry.stats.multishot = 99
        self.assertNotEqual(copied.data.entry.stats.multishot, upgrade.data.entry.stats.multishot)

    def test_configure_and_set_mode_are_order_independent(self):
        build = galvanized_build()
        first = arsenal.get("Corinth Prime").configure(build).set_mode("Air Burst Projectile")
        second = arsenal.get("Corinth Prime").set_mode("Air Burst Projectile").configure(build)

        self.assertEqual(first.stats.parent.effective, second.stats.parent.effective)
        self.assertAlmostEqual(first.stats.average.total_dps, second.stats.average.total_dps, places=6)

    def test_incarnon_evolution_selection_recomputes(self):
        weapon = arsenal.get("Telos Boltor")
        self.assertIsInstance(weapon.data.entry.evolutions, Evolutions)
        initial_damage = weapon.stats.parent.effective.damage.total_damage()

        self.assertIs(weapon.set_evolutions(evolution_2=1), weapon)
        self.assertEqual(weapon.evolutions, {"evolution_2": 1})
        self.assertGreater(weapon.stats.parent.effective.damage.total_damage(), initial_damage)

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
        self.assertEqual(weapon.stats.parent.effective.faction_damage, 1.55)

    def test_upgrade_stats_accept_scalar_and_single_record_shorthand(self):
        scalar = Upgrade({"Scalar": {"type": "mod", "max_rank": 0, "stats": {"base_damage": 1.5}}})
        record = Upgrade({"Record": {"type": "mod", "max_rank": 0, "stats": {"crit_damage": {"value": 2.5, "when": "active"}}}})

        self.assertEqual(scalar.stats.static.base_damage, 1.5)
        self.assertEqual(record.stats.conditional.crit_damage, 2.5)
        self.assertEqual(scalar.data.entry.stats.base_damage, 1.5)

    def test_upgrade_stats_accept_mixed_scalar_and_record_lists(self):
        upgrade = Upgrade({"Mixed": {
            "type": "mod",
            "max_rank": 0,
            "stats": {"base_damage": [1.5, {"value": 2.5, "when": "active"}]},
        }})

        self.assertEqual(upgrade.stats.static.base_damage, 1.5)
        self.assertEqual(upgrade.stats.conditional.base_damage, 2.5)
        self.assertEqual(upgrade.stats.total.base_damage, 4)

        cannonade = arsenal.get("Corinth Prime").configure(Build(
            arsenal.get("Semi-Shotgun Cannonade"),
            arsenal.get("Critical Delay"),
        ))
        self.assertTrue(cannonade.build.stats.total.fire_rate_lock)
        self.assertAlmostEqual(cannonade.stats.parent.effective.fire_rate, cannonade.stats.parent.base.fire_rate)

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

        conditional = Upgrade({"Conditional": {
            "type": "mod", "max_rank": 0, "compatibility": {"types": []},
            "stats": {"base_damage": [{"value": 1, "when": "kill"}]},
        }})
        self.assertEqual(conditional.stats.conditional.base_damage, 1)
        conditional.data.runtime.kill = False
        disabled = Build(conditional)
        self.assertEqual(disabled.stats.conditional.base_damage, 0)

    def test_condition_overload_uses_status_cap_and_attack_rules(self):
        condition_overload = Upgrade({"Condition Overload": {
            "type": "mod", "max_rank": 0, "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 1, "stacks": {"when": "status_type", "max": 2}}]},
        }})
        base_damage = Upgrade({"Base Damage": {"type": "mod", "max_rank": 0, "compatibility": {"types": []},
                               "stats": {"base_damage": [{"value": 1}]}}})
        build = Build(condition_overload, base_damage)

        additive = arsenal.get("Cernos").set_mode("Charged Shot").configure(build)
        additive_base = additive.stats.parent.base.damage.total_damage()
        self.assertEqual(additive.mode.stats.co_factor, 0.5)
        self.assertEqual(additive.mode.stats.co_effect, "adds")
        self.assertGreater(additive.stats.parent.effective.damage.total_damage(), additive_base * 2)
        self.assertLess(additive.stats.parent.effective.damage.total_damage(), additive_base * 3)

        multiplicative = arsenal.get("Coda Bassocyst").set_mode("Normal Attack").configure(build)
        multiplicative_base = multiplicative.stats.parent.base.damage.total_damage()
        self.assertEqual(multiplicative.mode.stats.co_effect, "multiplies")
        self.assertGreater(multiplicative.stats.parent.effective.damage.total_damage(), multiplicative_base * 2)
        self.assertLess(multiplicative.stats.parent.effective.damage.total_damage(), multiplicative_base * 6)

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
        condition_overload = Upgrade({"Condition Overload": {
            "type": "mod", "max_rank": 0, "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 0.8, "stacks": {"when": "status_type", "max": 2}}]},
        }})
        weapon = arsenal.get("Cernos").configure(Build(condition_overload))

        self.assertGreater(weapon.stats._average_condition_overload_bonus(weapon.stats.parent), 0)
        self.assertLess(weapon.stats._average_condition_overload_bonus(weapon.stats.parent), 1.6)

    def test_condition_overload_uses_each_attack_bucket(self):
        condition_overload = Upgrade({"Condition Overload": {
            "type": "mod", "max_rank": 0, "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 1, "stacks": {"when": "status_type", "max": 1}}]},
        }})
        weapon = Primary({"Bucketed CO": {
            "type": "primary",
            "attacks": {
                "parent": {"children": ["child"], "stats": {"damage": {"impact": 10}, "status_chance": 0}},
                "child": {"stats": {"damage": {"heat": 10}, "status_chance": 1}},
            },
        }}).configure(Build(condition_overload))
        parent = weapon.stats.parent
        child = weapon.stats.child[0]

        self.assertEqual(weapon.stats._average_condition_overload_bonus(parent), 0)
        self.assertGreater(weapon.stats._average_condition_overload_bonus(child), 0)
        self.assertEqual(parent.modded.base_damage, 1)
        self.assertGreater(child.modded.base_damage, 1)

    def test_condition_overload_mod_has_no_status_cap(self):
        heat = Upgrade({"Heat": {"type": "mod", "max_rank": 0, "compatibility": {"types": []},
                        "stats": {"heat": [{"value": 1}]}}})
        without_condition_overload = arsenal.get("Skana").configure(Build(heat))
        with_condition_overload = arsenal.get("Skana").configure(Build(heat, arsenal.get("Condition Overload")))

        elemental_damage = without_condition_overload.stats.parent.effective.damage.total_damage()
        self.assertEqual(set(with_condition_overload.stats.parent.effective.damage.data), {"impact", "puncture", "slash", "heat"})
        self.assertGreater(with_condition_overload.stats.parent.effective.damage.total_damage(), elemental_damage)
        self.assertLess(with_condition_overload.stats.parent.effective.damage.total_damage(), elemental_damage * (1 + 0.8 * 4))

    def test_formatter_summary_reads_current_state(self):
        weapon = arsenal.get("Corinth Prime").configure(galvanized_build()).set_mode("Buckshot")
        summary = weapon.format.summary()
        upgrades = weapon.format.upgrades()

        self.assertIn("Corinth Prime", summary)
        self.assertIn("Buckshot", summary)
        self.assertIn("TOTAL DPS", summary)
        self.assertIn("Galvanized Chamber", upgrades)

    def test_formatter_renders_related_attack_base_and_total_damage(self):
        weapon = arsenal.get("Corinth Prime").set_mode("Air Burst Projectile")
        summary = weapon.format.summary()
        blast = next(line for line in summary.splitlines() if line.startswith("Air Burst Explosion BLAST:"))
        total = next(line for line in summary.splitlines() if line.startswith("Air Burst Explosion TOTAL DAMAGE:"))

        self.assertRegex(blast, r"2200\.00\s+-> 2200\.00$")
        self.assertRegex(total, r"2200\.00\s+-> 2200\.00$")


if __name__ == "__main__":
    unittest.main()
