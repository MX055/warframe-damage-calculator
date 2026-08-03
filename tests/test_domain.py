import unittest
import pickle

from warframe_damage_calculator import Attack, AttackStats, Calculator, Dist, Build, Melee, PerkValues, Primary, Source, State, arsenal
from warframe_damage_calculator.domain.effects import Effect
from warframe_damage_calculator.domain.perks import Perk, resolve_perk
from warframe_damage_calculator.domain.state import combo_multiplier_from_hits
from warframe_damage_calculator.domain.upgrades import Compatibility, Mod, UpgradeStats


class DomainTests(unittest.TestCase):
    def test_compatibility_rejects_non_boolean_aoe_values(self):
        with self.assertRaisesRegex(TypeError, "aoe must be a bool"): Compatibility.from_record({"aoe": "false"})

    def test_multiplicative_effects_scale_from_the_identity(self):
        upgrade = Mod(name="Multiplier", max_rank=5, stats=UpgradeStats(explosion_radius=Effect(0.2, mode="multiplicative")))
        self.assertAlmostEqual(upgrade.set(rank=0).resolve_manual()[0].value, 1 - 0.8 / 6)
        self.assertAlmostEqual(upgrade.set(rank=5).resolve_manual()[0].value, 0.2)
        with self.assertRaisesRegex(TypeError, "must be numeric"): Effect("invalid", mode="multiplicative")
        with self.assertRaisesRegex(ValueError, "damage_bonus does not support"): UpgradeStats(damage_bonus=Effect(2, mode="multiplicative"))

    def test_source_expressions_round_trip_through_effect_records(self):
        source = Source("$values.damage_bonus[0]", multiplier=0.5)
        effect = Effect(source, mode="flat")
        restored = Effect.from_record(effect.to_record())
        self.assertEqual(restored.value.path, source.path)
        self.assertEqual(restored.value.multiplier, 0.5)
        self.assertEqual(restored.mode, "flat")

    def test_build_rejects_combined_upgrades_argument(self):
        with self.assertRaises(TypeError): Build(upgrades=[])

    def test_build_copies_upgrades(self):
        upgrade = Mod(name="Damage", stats=UpgradeStats(damage_bonus=Effect(1)))
        build = Build(mods=[upgrade])
        self.assertIsNot(build.upgrades[0], upgrade)

    def test_build_copies_evolutions(self):
        perk = Perk("Example", stats=UpgradeStats(damage_bonus=Effect(Source("$values.damage_bonus[0]"), when="charged")))
        build = Build(evolutions=[perk])
        self.assertIsNot(build.evolutions[0], perk)
        self.assertTrue(build.evolutions[0].runtime.charged)

    def test_build_rejects_duplicate_perks(self):
        perk = Perk("Example")
        with self.assertRaises(ValueError): Build(evolutions=[perk, perk])

    def test_build_addition_preserves_evolutions(self):
        perk = Perk("Example")
        first = Build(evolutions=[perk])
        combined = first + Mod(name="Damage")
        self.assertEqual(combined.evolutions, [perk])
        self.assertEqual([upgrade.name for upgrade in combined.upgrades], ["Damage", "Example"])
        self.assertEqual([upgrade.name for upgrade in combined.ranked_upgrades], ["Damage"])

    def test_build_operators_support_perks(self):
        perk = Perk("Example")
        build = Build(mods=[Mod(name="Damage")]) + perk
        self.assertEqual(len(build), 2)
        self.assertEqual((build - perk).evolutions, [])

    def test_state_rejects_unknown_fields_and_conditions(self):
        with self.assertRaises(TypeError): State(combo=5)
        with self.assertRaises(TypeError): State._from_values({"headshot": True})
        with self.assertRaises(TypeError): State._from_values({"combo": 5})

    def test_combo_multiplier_from_hits(self):
        self.assertEqual(combo_multiplier_from_hits(0), 1)
        self.assertEqual(combo_multiplier_from_hits(19), 1)
        self.assertEqual(combo_multiplier_from_hits(20), 2)
        self.assertEqual(combo_multiplier_from_hits(40), 3)
        self.assertEqual(combo_multiplier_from_hits(1000, max_combo=12), 12)

    def test_calculation_defaults_exclude_combo_and_conditions(self):
        weapon = arsenal.melee.get("Xoris")
        self.assertEqual(dict(weapon.calculation_defaults), {"stance_combo": "neutral", "ability_strength": 1.0})
        self.assertNotIn("combo", weapon.calculation_defaults)
        self.assertNotIn("combo_multiplier", weapon.calculation_defaults)

    def test_perk_conditions_use_runtime_defaults_and_set(self):
        perk = Perk("Conditional", stats=UpgradeStats(damage_bonus=Effect(Source("$values.damage_bonus[0]"), when="charged", stacks=3)))
        values = PerkValues(perk, 1, 1, {"damage_bonus": (0.5,)})
        weapon = Primary(name="Test", attacks=[Attack("shot", stats=AttackStats(damage=Dist(impact=1)))], perks=[values])
        self.assertEqual(perk.runtime.charged, 3)
        self.assertEqual(len(weapon.resolve_perk(perk).effects), 1)
        self.assertEqual(weapon.resolve_perk(perk).effects[0].value, 1.5)
        disabled = perk.copy().set(charged=False)
        self.assertEqual(resolve_perk(values, weapon_name=weapon.name, perk=disabled).effects, ())
        build = Build(evolutions=[perk]).set(charged=0)
        self.assertEqual(build.evolutions[0].runtime.charged, 0)

    def test_omitted_combo_multiplier_uses_initial_combo(self):
        weapon = Melee(name="Test Blade", attacks=[Attack("heavy_attack", category="heavy", stats=AttackStats(damage=Dist(slash=100), initial_combo=40, fire_rate=1))], combo={"max_combo": 12})
        result = Calculator(weapon).resolve(attack="heavy_attack")
        self.assertEqual(result.attacks["heavy_attack"].average.combo_multiplier, 3)
        explicit = Calculator(weapon).resolve(attack="heavy_attack", state=State(combo_multiplier=5))
        self.assertEqual(explicit.attacks["heavy_attack"].average.combo_multiplier, 5)

    def test_weapon_definitions_are_picklable_for_parallel_optimization(self):
        weapon = pickle.loads(pickle.dumps(arsenal.primary.get("Vectis Prime")))
        self.assertEqual((weapon.name, list(weapon.attacks), list(weapon.perk_choices)), ("Vectis Prime", ["normal_attack", "incarnon_form", "incarnon_form_aoe", "incarnon_form_embed"], [1, 2, 3, 4]))
        perk = next(iter(weapon.perks))
        self.assertTrue(all(isinstance(effect.value, Source) for effects in perk.stats.values() for effect in effects))


if __name__ == "__main__": unittest.main()
