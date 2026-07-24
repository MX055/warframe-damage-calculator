import unittest

from warframe_damage_calculator.calculators.melee_calculator import MeleeCalculator
from warframe_damage_calculator.calculators.weapon_calculator import WeaponCalculator
from warframe_damage_calculator.fields.attack_result import AttackResult
from warframe_damage_calculator.fields.calculated import AverageStats
from warframe_damage_calculator.fields.weapon_data import Attack


class HelperTests(unittest.TestCase):
    def test_crit_multiplier(self):
        self.assertAlmostEqual(WeaponCalculator._crit_multiplier(0.5, 3.0), 2.0)
        self.assertAlmostEqual(WeaponCalculator._crit_multiplier(0.0, 3.0), 1.0)
        self.assertAlmostEqual(WeaponCalculator._crit_multiplier(2.0, 2.0), 3.0)

    def test_combo_multiplier_from_hits(self):
        self.assertEqual(MeleeCalculator._combo_multiplier_from_hits(0), 1)
        self.assertEqual(MeleeCalculator._combo_multiplier_from_hits(19), 1)
        self.assertEqual(MeleeCalculator._combo_multiplier_from_hits(20), 2)
        self.assertEqual(MeleeCalculator._combo_multiplier_from_hits(220), 12)
        self.assertEqual(MeleeCalculator._combo_multiplier_from_hits(999), 12)

    def test_hit_multiplier_includes_non_crit_bonus(self):
        # 12% crit @ 2.2x, Attrition +2000% @ 50% → expected non-crit bonus 10
        self.assertAlmostEqual(WeaponCalculator._hit_multiplier(0.12, 2.2, 20, 0.5), 9.944)
        self.assertAlmostEqual(WeaponCalculator._hit_multiplier(0.0, 2.0, 2.4), 3.4)
        self.assertAlmostEqual(WeaponCalculator._hit_multiplier(1.5, 2.0, 20, 0.5), WeaponCalculator._crit_multiplier(1.5, 2.0))

    def test_refresh_dps_from_dph(self):
        average = AverageStats({
            "fire_rate": 2.0,
            "flat_dph": 100.0,
            "flat_weakpoint_dph": 200.0,
            "flat_dotph": 10.0,
            "flat_weakpoint_dotph": 20.0,
            "flat_dotps": 20.0,
            "flat_weakpoint_dotps": 40.0,
        })
        WeaponCalculator._refresh_dps_from_dph(average)
        self.assertAlmostEqual(average.flat_dps, 200.0)
        self.assertAlmostEqual(average.flat_weakpoint_dps, 400.0)
        self.assertAlmostEqual(average.total_dph, 110.0)
        self.assertAlmostEqual(average.total_weakpoint_dph, 220.0)
        self.assertAlmostEqual(average.total_dps, 220.0)
        self.assertAlmostEqual(average.total_weakpoint_dps, 440.0)

    def test_flat_dotph_zero_when_no_damage(self):
        result = AttackResult({
            "name": "test",
            "attack": Attack({"name": "test", "stats": {"damage": {}}}),
        })
        self.assertEqual(WeaponCalculator._flat_dotph(None, result, faction_damage=1), 0.0)

    def test_status_hits_uses_multishot(self):
        result = AttackResult({
            "name": "test",
            "attack": Attack({"name": "test", "stats": {"multishot": 1, "crit_chance": 0.1}}),
            "modded": {
                "additive": {"multishot": 2.5},
                "multiplicative": {"crit_chance": 1},
                "flat": {"crit_chance": 0},
            },
        })
        self.assertAlmostEqual(WeaponCalculator._status_hits(result), 2.5)


if __name__ == "__main__":
    unittest.main()
