import unittest
from copy import deepcopy

from warframe_damage_calculator import arsenal
from warframe_damage_calculator.database.schema import validate_database
from warframe_damage_calculator.domain.effects import Effect, Source
from warframe_damage_calculator.domain.scaled_values import ScaledValue, resolve_scalar
from warframe_damage_calculator.domain.upgrades import Mod, UpgradeStats


class ScaledValueTests(unittest.TestCase):
    def test_plain_numbers_scale_by_default(self):
        upgrade = Mod(name="Scaled", max_rank=5, stats=UpgradeStats(damage_bonus=Effect.from_record({"value": 0.9, "automatic": {}})))
        self.assertEqual(upgrade.stats.damage_bonus[0].value, ScaledValue(0.9, True))
        self.assertAlmostEqual(upgrade.set(rank=0).resolve_manual()[0].value, 0.15)
        self.assertAlmostEqual(upgrade.set(rank=5).resolve_manual()[0].value, 0.9)

    def test_wrapped_values_follow_rank_formula(self):
        wrapped_int = ScaledValue(6, True)
        wrapped_float = ScaledValue(0.9, True)
        self.assertEqual(resolve_scalar(wrapped_int, 0, 5), 1)
        self.assertEqual(resolve_scalar(wrapped_int, 5, 5), 6)
        self.assertEqual(resolve_scalar(wrapped_int, 2, 5), 3)
        self.assertAlmostEqual(resolve_scalar(wrapped_float, 0, 5), 0.15)
        self.assertAlmostEqual(resolve_scalar(wrapped_float, 5, 5), 0.9)
        self.assertAlmostEqual(resolve_scalar(wrapped_float, 2, 5), 0.45)

    def test_fixed_wrappers_do_not_scale(self):
        upgrade = Mod(name="Fixed", max_rank=5, stats=UpgradeStats(damage_bonus=Effect.from_record({"value": {"value": 0.9, "rank_scale": False}, "automatic": {}})))
        self.assertEqual(upgrade.stats.damage_bonus[0].value, ScaledValue(0.9, False))
        self.assertEqual(upgrade.set(rank=0).resolve_manual()[0].value, 0.9)
        self.assertEqual(upgrade.set(rank=5).resolve_manual()[0].value, 0.9)

    def test_invalid_scaled_wrappers_fail(self):
        with self.assertRaisesRegex(ValueError, "scaled value requires value"): ScaledValue.from_record({"rank_scale": True})
        with self.assertRaisesRegex(TypeError, "scaled value must be numeric"): ScaledValue.from_record({"value": "x", "rank_scale": True})
        with self.assertRaisesRegex(TypeError, "scaled value must be numeric"): ScaledValue.from_record({"value": {"value": 1, "rank_scale": True}, "rank_scale": True})
        with self.assertRaisesRegex(ValueError, "scaled value requires value"): ScaledValue.from_record({"value": 1, "rank_scale": True, "extra": 1})
        with self.assertRaisesRegex(ValueError, "entry-level rank_scale"): Effect.from_record({"value": 1, "rank_scale": True, "automatic": {}})

    def test_source_multiplier_can_scale_without_scaling_the_source(self):
        source = Source.from_record({"source": "$parent.stats.damage.total", "multiplier": {"value": 0.3, "rank_scale": True}})
        self.assertEqual(source.path, "$parent.stats.damage.total")
        self.assertEqual(source.multiplier, ScaledValue(0.3, True))
        self.assertAlmostEqual(source.resolve_multiplier(0, 5), 0.05)
        self.assertAlmostEqual(source.resolve_multiplier(5, 5), 0.3)
        fixed = Source.from_record({"source": "$parent.stats.falloff.end_range", "multiplier": 0.9})
        self.assertEqual(fixed.multiplier, 0.9)
        self.assertEqual(fixed.resolve_multiplier(0, 5), 0.9)

    def test_non_effect_values_do_not_scale_by_default(self):
        upgrade = Mod(name="Fixed Auto", max_rank=5, stats=UpgradeStats(damage_bonus=Effect.from_record({"value": 0.9, "automatic": {"chance": 0.2, "for": 10}})))
        self.assertEqual(upgrade.stats.damage_bonus[0].automatic["chance"], 0.2)
        self.assertEqual(upgrade.stats.damage_bonus[0].automatic["for"], 10)
        zero = upgrade.set(rank=0).resolve_manual()[0]
        maximum = upgrade.set(rank=5).resolve_manual()[0]
        self.assertEqual(zero.automatic["chance"], 0.2)
        self.assertEqual(maximum.automatic["chance"], 0.2)
        self.assertEqual(zero.automatic["for"], 10)
        self.assertEqual(maximum.automatic["for"], 10)
        omitted = ScaledValue.from_record({"value": 0.3}, default_rank_scale=False)
        self.assertEqual(omitted, ScaledValue(0.3, False))

    def test_multiplicative_mode_scales_from_identity(self):
        self.assertAlmostEqual(resolve_scalar(ScaledValue(0.2, True), 0, 5, mode="multiplicative"), 1 - 0.8 / 6)
        self.assertAlmostEqual(resolve_scalar(ScaledValue(0.2, True), 5, 5, mode="multiplicative"), 0.2)

    def test_integer_semantics_are_preserved(self):
        self.assertIsInstance(resolve_scalar(ScaledValue(18, True), 0, 5), int)
        self.assertEqual(resolve_scalar(ScaledValue(18, True), 0, 5), 3)
        self.assertEqual(resolve_scalar(ScaledValue(18, True), 5, 5), 18)

    def test_database_has_no_entry_level_rank_scale_or_nested_generated_attack(self):
        database = arsenal.database
        self.assertEqual(database["schema_version"], 24)
        for category in database["upgrades"].values():
            for upgrade in category.values():
                self.assertNotIn("extra_attack", upgrade.get("stats", {}))
                for effects in upgrade.get("stats", {}).values():
                    for effect in effects:
                        self.assertNotIn("rank_scale", effect)
                        if "name" in effect and "links" in effect:
                            self.assertIn("parents", effect["links"])
                            self.assertNotIn("kind", effect)
                            self.assertNotIn("parent", effect)
                            self.assertNotIn("attack", effect)
                            self.assertNotIn("value", effect)
        validate_database(deepcopy(database))

    def test_nightwatch_napalm_scales_only_the_damage_multiplier(self):
        napalm = arsenal.mod.get("Nightwatch Napalm")
        resolved_zero = napalm.set(rank=0).resolve_manual()[0].value
        resolved_max = napalm.set(rank=5).resolve_manual()[0].value
        self.assertAlmostEqual(resolved_zero["stats"]["damage"]["heat"]["multiplier"], 0.05)
        self.assertAlmostEqual(resolved_max["stats"]["damage"]["heat"]["multiplier"], 0.3)
        self.assertEqual(resolved_max["stats"]["falloff"]["end_range"]["multiplier"], 0.9)
        self.assertEqual(resolved_max["stats"]["multishot"], 5)

    def test_melee_influence_scales_duration_not_chance_or_range(self):
        influence = arsenal.arcane.get("Melee Influence")
        zero = influence.set(rank=0).resolve_manual()[0]
        maximum = influence.set(rank=5).resolve_manual()[0]
        self.assertEqual(zero.automatic["chance"], 0.2)
        self.assertEqual(maximum.automatic["chance"], 0.2)
        self.assertEqual(zero.automatic["for"], 3)
        self.assertEqual(maximum.automatic["for"], 18)
        self.assertEqual(maximum.value["stats"]["falloff"]["end_range"], 20)

    def test_melee_duplicate_chance_scales_linearly(self):
        duplicate = arsenal.arcane.get("Melee Duplicate")
        self.assertEqual(duplicate.stats.generated_attack[0].automatic["chance"], ScaledValue(1, True))
        for rank, chance in enumerate([1 / 6, 2 / 6, 3 / 6, 4 / 6, 5 / 6, 1]):
            self.assertAlmostEqual(duplicate.set(rank=rank).resolve_manual()[0].automatic["chance"], chance)


if __name__ == "__main__":
    unittest.main()
