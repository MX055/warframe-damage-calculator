import unittest
from typing import get_args

from warframe_damage_calculator import Build, Primary, Upgrade, arsenal
from warframe_damage_calculator.loader.bundled_names import MeleeName, PrimaryName, SecondaryName, UpgradeName
from warframe_damage_calculator.models.data import Data
from warframe_damage_calculator.models.fields import Attack, Attacks, Evolutions


def galvanized_build() -> Build:
    return Build(
        arsenal.get("Galvanized Chamber", context={"stacks": 5}),
        arsenal.get("Galvanized Aptitude", context={"stacks": 2}),
    )


class PublicApiTests(unittest.TestCase):
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
        self.assertTrue(hasattr(weapon, "stats"))
        self.assertFalse(hasattr(weapon, "attacks"))
        for attribute in ("type", "subtype", "base", "moded", "modded", "effective", "total_dps", "calculation_build"):
            self.assertFalse(hasattr(weapon, attribute))
        self.assertEqual(weapon.data.entry.ammo.reload_time, 3)
        self.assertEqual(weapon.data.entry.ammo.magazine_size, 20)
        self.assertNotIn("damage", weapon.data.entry.ammo)
        self.assertEqual(weapon.mode.stats.damage.total_damage(), 90)
        self.assertNotIn("reload_time", weapon.mode.stats)

    def test_default_mode_switching_and_invalid_mode_errors(self):
        weapon = arsenal.get("Corinth Prime")
        self.assertIs(weapon.mode, weapon.data.entry.attacks.buckshot)

        self.assertIs(weapon.set_mode("Air Burst Projectile"), weapon)
        self.assertEqual(weapon.mode.children, ["air_burst_explosion"])
        self.assertEqual(weapon.stats.base.damage.total_damage(), 100)
        self.assertEqual(weapon.stats.related["Air Burst Explosion"].damage.total_damage(), 2200)

        with self.assertRaises(ValueError) as raised:
            weapon.set_mode("Missing")
        self.assertIn("Buckshot", str(raised.exception))
        self.assertIn("Air Burst Projectile", str(raised.exception))

    def test_mode_specific_stats_and_global_ranged_stats(self):
        weapon = arsenal.get("Corinth Prime").set_mode("Buckshot")
        mode = weapon.mode.stats

        self.assertAlmostEqual(mode.crit_chance, 0.3)
        self.assertAlmostEqual(mode.status_chance, 0.09)
        self.assertAlmostEqual(mode.fire_rate, 1.42)
        self.assertEqual(mode.co_factor, 1)
        self.assertEqual(mode.co_effect, "adds")
        self.assertEqual(weapon.stats.base.magazine_capacity, 20)
        self.assertEqual(weapon.stats.base.reload_speed, 3)

        battery = arsenal.get("Tenet Cycron")
        self.assertIn("recharge_delay", battery.data.entry.ammo)
        self.assertAlmostEqual(battery.data.entry.ammo.recharge_rate, 26.66666667)
        self.assertAlmostEqual(battery.stats.base.recharge_rate, 26.66666667)

    def test_build_configuration_copies_and_recomputes(self):
        build = galvanized_build()
        weapon = arsenal.get("Corinth Prime")
        base_multishot = weapon.stats.effective.multishot
        base_damage = weapon.stats.effective.damage.total_damage()

        self.assertIs(weapon.configure(build), weapon)
        self.assertIsNot(weapon.build, build)
        self.assertGreater(weapon.stats.effective.multishot, base_multishot)
        self.assertGreater(weapon.stats.effective.damage.total_damage(), base_damage)

        for upgrade in build.upgrades:
            upgrade.data.runtime.stacks = 0
        build.stats.resolve()
        self.assertGreater(weapon.stats.effective.multishot, base_multishot)

    def test_build_iteration_addition_and_subtraction_remain_available(self):
        chamber = arsenal.get("Galvanized Chamber", context={"stacks": 5})
        aptitude = arsenal.get("Galvanized Aptitude")
        build = Build(chamber) + aptitude

        self.assertEqual(len(list(build)), 2)
        reduced = build - chamber
        self.assertEqual([upgrade.data.name for upgrade in reduced], ["Galvanized Aptitude"])

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

        self.assertEqual(first.stats.effective, second.stats.effective)
        self.assertAlmostEqual(first.stats.average.total_dps, second.stats.average.total_dps)

    def test_incarnon_evolution_selection_recomputes(self):
        weapon = arsenal.get("Telos Boltor")
        self.assertIsInstance(weapon.data.entry.evolutions, Evolutions)
        initial_damage = weapon.stats.effective.damage.total_damage()

        self.assertIs(weapon.set_evolutions(evolution_2=1), weapon)
        self.assertEqual(weapon.evolutions, {"evolution_2": 1})
        self.assertGreater(weapon.stats.effective.damage.total_damage(), initial_damage)

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
        self.assertEqual(weapon.stats.effective.faction_damage, 1.55)

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
        self.assertAlmostEqual(cannonade.stats.effective.fire_rate, cannonade.stats.base.fire_rate)

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
        additive_base = additive.stats.base.damage.total_damage()
        self.assertEqual(additive.mode.stats.co_factor, 0.5)
        self.assertEqual(additive.mode.stats.co_effect, "adds")
        self.assertAlmostEqual(additive.stats.effective.damage.total_damage(), additive_base * 3)

        multiplicative = arsenal.get("Coda Bassocyst").set_mode("Normal Attack").configure(build)
        multiplicative_base = multiplicative.stats.base.damage.total_damage()
        self.assertEqual(multiplicative.mode.stats.co_effect, "multiplies")
        self.assertAlmostEqual(multiplicative.stats.effective.damage.total_damage(), multiplicative_base * 6)

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

    def test_condition_overload_mod_has_no_status_cap(self):
        heat = Upgrade({"Heat": {"type": "mod", "max_rank": 0, "compatibility": {"types": []},
                        "stats": {"heat": [{"value": 1}]}}})
        without_condition_overload = arsenal.get("Skana").configure(Build(heat))
        with_condition_overload = arsenal.get("Skana").configure(Build(heat, arsenal.get("Condition Overload")))

        elemental_damage = without_condition_overload.stats.effective.damage.total_damage()
        self.assertEqual(set(with_condition_overload.stats.effective.damage.data), {"impact", "puncture", "slash", "heat"})
        self.assertAlmostEqual(with_condition_overload.stats.effective.damage.total_damage(), elemental_damage * (1 + 0.8 * 4))

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
