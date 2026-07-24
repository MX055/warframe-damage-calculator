"""Focused tests for calculator architecture and calculation domains."""

from __future__ import annotations

import unittest

from warframe_damage_calculator import Build, Melee, Primary, Upgrade, arsenal
from warframe_damage_calculator.calculators import formulas
from warframe_damage_calculator.calculators.attack_tree import needed_attack_names, validate_attack_cycles
from warframe_damage_calculator.calculators.effect_resolution import ResolutionContext, ResolvableEffect, raw_effects, resolve_and_aggregate, resolve_stack_scaled_effect, stack_count
from warframe_damage_calculator.calculators.evolution_calculator import EvolutionCalculator
from warframe_damage_calculator.calculators.stat_aggregation import UPGRADE_AGGREGATORS, merge_evolution_stat, merge_upgrade_stat
from warframe_damage_calculator.calculators.status_model import SustainedStatusModel, apply_condition_overload, build_sustained_status_model, condition_overload_bonus, per_attack_status_probabilities, status_effect_stack_bonuses, sustained_proc_chance
from warframe_damage_calculator.calculators.upgrade_calculator import UpgradeCalculator
from warframe_damage_calculator.calculators.weapon_calculator import WeaponCalculator
from warframe_damage_calculator.core.data import Data
from warframe_damage_calculator.core.dist import Dist
from warframe_damage_calculator.fields.calculated import ModdedStats
from warframe_damage_calculator.fields.evolution import ConversionBonus
from warframe_damage_calculator.fields.weapon_data import Attack


def selected(weapon):
    return weapon.results.main


class StatusModelTests(unittest.TestCase):
    def test_sustained_proc_chance_extremes(self):
        self.assertEqual(sustained_proc_chance(0, 10), 0.0)
        self.assertEqual(sustained_proc_chance(0.5, 0), 0.0)
        self.assertEqual(sustained_proc_chance(1, 3), 1.0)
        self.assertEqual(sustained_proc_chance(0.5, float("inf")), 1.0)

    def test_expected_unique_active_is_capped(self):
        model = SustainedStatusModel(per_attack_probabilities={"slash": 1.0, "heat": 1.0, "toxin": 1.0}, attacks_per_second=10, status_duration=6, max_unique_statuses=2)
        self.assertAlmostEqual(model.expected_unique_active_statuses(), 2.0)

    def test_zero_attack_rate_and_duration_yield_zero_uniques(self):
        self.assertEqual(SustainedStatusModel({"slash": 1.0}, 0, 6, 3).expected_unique_active_statuses(), 0.0)
        self.assertEqual(SustainedStatusModel({"slash": 1.0}, 10, 0, 3).expected_unique_active_statuses(), 0.0)

    def test_multiple_status_attempts_raise_per_attack_probability(self):
        weapon = Primary({"name": "Attempts", "type": "primary", "attacks": {"shot": {"stats": {"damage": {"heat": 100}, "status_chance": 0.5, "fire_rate": 1, "multishot": 1}}}})
        result = selected(weapon)
        one = per_attack_status_probabilities(attack=result.attack, base=result.base, build=result.build, evolution_status_chance=0, flat_status_chance=0, status_attempts_per_attack=1)
        two = per_attack_status_probabilities(attack=result.attack, base=result.base, build=result.build, evolution_status_chance=0, flat_status_chance=0, status_attempts_per_attack=2)
        self.assertGreater(two["heat"], one["heat"])

    def test_condition_overload_bonus_scales_expected_uniques(self):
        model = SustainedStatusModel(per_attack_probabilities={"slash": 1.0}, attacks_per_second=1, status_duration=6, max_unique_statuses=1)
        resolved = condition_overload_bonus(model, value_per_status=0.8, co_factor=1, co_effect="adds")
        self.assertAlmostEqual(resolved.expected_unique_active, 1.0)
        self.assertAlmostEqual(resolved.bonus, 0.8)
        self.assertEqual(resolved.effect, "adds")

    def test_expected_status_stacks_are_capped_mean_procs(self):
        model = SustainedStatusModel(per_attack_probabilities={"cold": 0.5}, attacks_per_second=10, status_duration=6, max_unique_statuses=1)
        self.assertAlmostEqual(model.expected_status_stacks("cold", 40), 30.0)
        self.assertAlmostEqual(model.expected_status_stacks("cold", 20), 20.0)
        self.assertEqual(model.expected_status_stacks("heat", 40), 0.0)

    def test_status_effect_stack_bonuses_use_model_or_runtime_override(self):
        model = SustainedStatusModel(per_attack_probabilities={"heat": 1.0}, attacks_per_second=1, status_duration=6, max_unique_statuses=1)
        entries = [{"value": 0.12, "stat": "damage_bonus", "mode": "additive", "status": "heat", "max_stacks": 40}]
        self.assertEqual(status_effect_stack_bonuses(model=model, entries=entries), [("additive", "damage_bonus", 0.72)])
        self.assertEqual(status_effect_stack_bonuses(model=model, entries=entries, runtime={"on_heat_status_effect": 10}), [("additive", "damage_bonus", 1.2)])

    def test_apply_condition_overload_only_needs_status_model(self):
        modded = ModdedStats()
        modded.additive.damage_bonus = 1.0
        model = SustainedStatusModel(per_attack_probabilities={"heat": 1.0}, attacks_per_second=1, status_duration=6, max_unique_statuses=1)
        apply_condition_overload(modded=modded, model=model, value_per_status=0.5, co_factor=1, co_effect="adds")
        self.assertAlmostEqual(modded.additive.damage_bonus, 1.5)

    def test_ranged_and_melee_sustained_rates_differ(self):
        ranged = Primary({"name": "R", "type": "primary", "ammo": {"magazine_size": 10, "reload_time": 2}, "attacks": {"shot": {"stats": {"damage": {"impact": 10}, "fire_rate": 10, "ammo_cost": 1}}}})
        melee = Melee({"name": "M", "type": "melee", "attacks": {"normal": {"stats": {"damage": {"slash": 10}, "fire_rate": 1}}}})
        # Melee defaults attack_speed from fire_rate; with no mods rates are close to base fire_rate.
        self.assertGreater(ranged.results._sustained_attack_rate(selected(ranged)), 0)
        self.assertGreater(melee.results._sustained_attack_rate(selected(melee)), 0)
        self.assertAlmostEqual(melee.results._sustained_attack_rate(selected(melee)), melee.results._effective_attacks_per_second(selected(melee)))


class AggregationTests(unittest.TestCase):
    def test_damage_and_condition_overload_policies(self):
        stats = Data()
        merge_upgrade_stat(stats, "slash", 10)
        merge_upgrade_stat(stats, "heat", 5)
        self.assertIsInstance(stats.damage, Dist)
        self.assertAlmostEqual(stats.damage.total_damage(), 15)

        merge_upgrade_stat(stats, "condition_overload", {"value": 0.4, "max_stacks": 2})
        merge_upgrade_stat(stats, "condition_overload", {"value": 0.4, "max_stacks": "inf"})
        self.assertAlmostEqual(stats.condition_overload.value, 0.8)
        self.assertEqual(stats.condition_overload.max_stacks, "inf")

    def test_registry_used_for_declared_stats(self):
        self.assertIn("damage", UPGRADE_AGGREGATORS)
        self.assertIn("condition_overload", UPGRADE_AGGREGATORS)
        self.assertIn("fire_rate_lock", UPGRADE_AGGREGATORS)

    def test_boolean_lock_and_ordinary_additive(self):
        stats = Data()
        merge_upgrade_stat(stats, "fire_rate_lock", False)
        merge_upgrade_stat(stats, "fire_rate_lock", True)
        self.assertTrue(stats.fire_rate_lock)
        merge_upgrade_stat(stats, "crit_chance", 0.5)
        merge_upgrade_stat(stats, "crit_chance", 0.25)
        self.assertAlmostEqual(stats.crit_chance, 0.75)

    def test_forced_procs_and_mapping_aggregation(self):
        stats = Data()
        merge_upgrade_stat(stats, "forced_procs", {"slash": 1})
        merge_upgrade_stat(stats, "forced_procs", {"heat": 2})
        self.assertIsInstance(stats.forced_procs, Dist)
        self.assertAlmostEqual(stats.forced_procs.get("slash"), 1)
        self.assertAlmostEqual(stats.forced_procs.get("heat"), 2)
        merge_upgrade_stat(stats, "elements", {"heat": 0.3})
        merge_upgrade_stat(stats, "elements", {"toxin": 0.2})
        self.assertAlmostEqual(stats.elements["heat"], 0.3)
        self.assertAlmostEqual(stats.elements["toxin"], 0.2)

    def test_evolution_conversion_aggregation(self):
        stats = Data()
        merge_evolution_stat(stats, "crit_from_status", 0.25, conversion_max=0.35)
        merge_evolution_stat(stats, "crit_from_status", 0.1, conversion_max=0.4)
        bonus = stats.crit_from_status
        self.assertIsInstance(bonus, ConversionBonus)
        self.assertAlmostEqual(bonus.value, 0.35)
        self.assertAlmostEqual(bonus.max, 0.4)

    def test_evolution_flat_damage_stays_numeric(self):
        stats = Data()
        merge_evolution_stat(stats, "damage", 60)
        merge_evolution_stat(stats, "damage", 40)
        self.assertEqual(stats.damage, 100)


class EffectResolutionTests(unittest.TestCase):
    def test_raw_effects_normalizes_scalars_and_maps(self):
        self.assertEqual(raw_effects(0.5)[0].value, 0.5)
        self.assertEqual(raw_effects([{"value": 1, "when": "headshot"}])[0].when, "headshot")

    def test_stack_count_defaults_and_caps(self):
        self.assertEqual(stack_count(stacks_on="stacks", max_stacks=5, lookup={}, default_stacks=None, use_defaults=True), 5)
        self.assertEqual(stack_count(stacks_on="stacks", max_stacks=5, lookup={}, default_stacks=None, use_defaults=False), 0)
        self.assertEqual(stack_count(stacks_on="stacks", max_stacks=3, lookup={"stacks": 10}, default_stacks=None, use_defaults=False), 3)

    def test_resolve_and_aggregate_pipeline(self):
        recorded: list[int] = []

        def is_applicable(effect: int, _context: object) -> bool:
            return effect % 2 == 0

        def resolve_one(effect: int, _context: object) -> int | None:
            return effect * 10

        def aggregate(effects) -> None:
            recorded.extend(effects)

        resolve_and_aggregate([1, 2, 3, 4], None, is_applicable=is_applicable, resolve_one=resolve_one, aggregate=aggregate)
        self.assertEqual(recorded, [20, 40])

    def test_resolve_stack_scaled_effect_multiplies_stacks(self):
        effect = ResolvableEffect(stat="crit_chance", value=0.1, stacks_on="stacks", max_stacks=5)
        context = ResolutionContext(stacks_lookup={"stacks": 3}, use_defaults=False)
        resolved = resolve_stack_scaled_effect(effect, context)
        self.assertIsNotNone(resolved)
        self.assertAlmostEqual(resolved.value, 0.3)

    def test_upgrade_rank_locked_and_equipped_dependency(self):
        upgrade = Upgrade({
            "name": "Modular",
            "type": "mod",
            "max_rank": 5,
            "stats": {
                "crit_chance": [
                    {"value": 0.5, "rank": 3},
                    {"value": 0.2, "equipped": ["Other"], "when": None},
                ],
            },
        })
        calc = UpgradeCalculator(upgrade)
        calc.resolve(Data({"type": "rifle"}), Data({"equipped": []}))
        self.assertAlmostEqual(calc.rank_locked.additive.crit_chance, 0.5)
        self.assertEqual(calc.modular.additive.get("crit_chance", 0), 0)
        calc.resolve(Data({"type": "rifle"}), Data({"equipped": ["Other"]}))
        self.assertAlmostEqual(calc.modular.additive.crit_chance, 0.2)

    def test_upgrade_condition_and_rank_scaling(self):
        upgrade = Upgrade({"name": "Cond", "type": "mod", "max_rank": 1, "stats": {"crit_chance": [{"value": 1.0, "when": "rifle"}]}})
        upgrade.configure(context={"rank": 0})
        calc = UpgradeCalculator(upgrade)
        calc.resolve(Data({"type": "pistol"}), Data())
        self.assertEqual(calc.conditional.additive.get("crit_chance", 0), 0)
        calc.resolve(Data({"type": "rifle"}), Data())
        # Rank 0 of max 1 → multiplier (0+1)/(1+1) = 0.5
        self.assertAlmostEqual(calc.conditional.additive.crit_chance, 0.5)

    def test_evolution_uses_shared_resolvable_effect(self):
        weapon = arsenal.get("Dera Vandal")
        weapon.configure(context={"evolutions": {4: 2}})
        effects = EvolutionCalculator(weapon)._normalize_effects()
        self.assertTrue(all(isinstance(effect, ResolvableEffect) for effect in effects))
        self.assertTrue(any(effect.stat == "crit_from_status" for effect in effects))


class AttackTreeTests(unittest.TestCase):
    def test_needed_names_follow_children(self):
        attacks = {
            "parent": Attack({"children": ["child"]}),
            "child": Attack({"children": ["grandchild"]}),
            "grandchild": Attack({}),
            "unused": Attack({}),
        }
        self.assertEqual(needed_attack_names(attacks, "parent"), {"parent", "child", "grandchild"})

    def test_cycles_are_rejected(self):
        attacks = {
            "a": Attack({"children": ["b"]}),
            "b": Attack({"children": ["a"]}),
        }
        with self.assertRaisesRegex(ValueError, "cyclic attack relationship detected"):
            validate_attack_cycles(attacks)


class PipelineOrderTests(unittest.TestCase):
    def test_conversions_apply_before_modded_scalars(self):
        status_mod = Upgrade({"name": "Status", "type": "mod", "max_rank": 0, "stats": {"status_chance": [{"value": 1.0}]}})
        weapon = arsenal.get("Dera Vandal")
        raw_crit = selected(weapon).base.crit_chance
        weapon.configure(Build(status_mod), context={"evolutions": {4: 2}})
        result = selected(weapon)
        self.assertGreater(result.base.crit_chance, raw_crit)
        self.assertAlmostEqual(result.modded.additive.crit_chance, result.base.crit_chance)
        self.assertAlmostEqual(result.effective.crit_chance, result.modded.additive.crit_chance)

    def test_manual_phase_order_matches_resolve(self):
        weapon = arsenal.get("Braton").configure(Build(arsenal.get("Serration")))
        resolved = selected(weapon)
        calculator = weapon.results
        fresh = type(resolved)({"name": resolved.name, "attack": resolved.attack, "build": resolved.build.copy(), "evolutions": resolved.evolutions.copy(), "children": list(resolved.children)})
        calculator._compute_base(fresh)
        calculator._apply_evolution_conversions(fresh)
        calculator._compute_modded_scalars(fresh)
        model = calculator._sustained_status_model(fresh)
        calculator._apply_status_effect_stacks(fresh, model)
        calculator._apply_condition_overload(fresh, model)
        calculator._compute_modded_damage(fresh)
        calculator._compute_effective(fresh)
        calculator._compute_average(fresh)
        self.assertAlmostEqual(fresh.effective.damage.total_damage(), resolved.effective.damage.total_damage())
        self.assertAlmostEqual(fresh.average.flat_dph, resolved.average.flat_dph)

    def test_condition_overload_uses_status_model_not_modded_damage(self):
        condition_overload = Upgrade({
            "name": "CO",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 1, "stacks": {"when": "status_type", "max": 1}}]},
        })
        weapon = Primary({
            "name": "CO Model",
            "type": "primary",
            "attacks": {"shot": {"stats": {"damage": {"heat": 100}, "status_chance": 1, "fire_rate": 1, "multishot": 1}}},
        }).configure(Build(condition_overload))
        result = selected(weapon)
        model = weapon.results._sustained_status_model(result)
        self.assertIsNotNone(model)
        self.assertIn("heat", model.per_attack_probabilities)
        self.assertGreater(weapon.results._average_condition_overload_bonus(result), 0)
        self.assertGreater(result.modded.additive.damage.total_damage(), 0)

    def test_build_sustained_status_model_from_layers(self):
        condition_overload = Upgrade({
            "name": "CO",
            "type": "mod",
            "max_rank": 0,
            "compatibility": {"types": []},
            "stats": {"condition_overload": [{"value": 1, "stacks": {"when": "status_type", "max": 2}}]},
        })
        weapon = Primary({
            "name": "CO Layers",
            "type": "primary",
            "attacks": {"shot": {"stats": {"damage": {"heat": 50, "slash": 50}, "status_chance": 1, "fire_rate": 2, "multishot": 1}}},
        }).configure(Build(condition_overload))
        result = selected(weapon)
        model = build_sustained_status_model(attack=result.attack, base=result.base, modded=result.modded, build=result.build, evolution_status_chance=0, status_attempts_per_attack=1, sustained_attack_rate=2)
        self.assertIsNotNone(model)
        self.assertEqual(model.attacks_per_second, 2)
        self.assertLessEqual(model.expected_unique_active_statuses(), 2)


class ContributionArchitectureTests(unittest.TestCase):
    def test_shapley_still_available_on_weapon_results(self):
        weapon = arsenal.get("Braton").configure(Build(arsenal.get("Serration"), arsenal.get("Split Chamber")))
        shares = weapon.results.shapley_contributions()
        self.assertAlmostEqual(sum(shares.values()), 1.0)
        removals = weapon.results.removal_contributions()
        self.assertEqual(set(removals), set(shares))


class FormulaBoundaryTests(unittest.TestCase):
    REMOVED_WRAPPERS = (
        "_crit_multiplier",
        "_non_crit_bonus",
        "_hit_multiplier",
        "_combine_chance",
        "_refresh_dps_from_dph",
        "_distribute_flat_damage",
    )

    def test_weapon_calculator_has_no_formula_wrappers(self):
        for name in self.REMOVED_WRAPPERS:
            self.assertFalse(hasattr(WeaponCalculator, name), f"WeaponCalculator must not reintroduce {name}")

    def test_formulas_module_exposes_stateless_entry_points(self):
        for name in ("crit_multiplier", "non_crit_bonus", "hit_multiplier", "combine_chance", "refresh_dps_from_dph", "distribute_flat_damage"):
            self.assertTrue(callable(getattr(formulas, name)))


if __name__ == "__main__":
    unittest.main()
