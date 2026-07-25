import unittest

from warframe_damage_calculator.calculators import formulas
from warframe_damage_calculator.calculators.damage_calculator import flat_dotph, flat_dotph_from_result
from warframe_damage_calculator.calculators.melee_calculator import MeleeCalculator
from warframe_damage_calculator.calculators.weapon_calculator import WeaponCalculator
from warframe_damage_calculator.core.dist import Dist
from warframe_damage_calculator.fields.attack_result import AttackResult
from warframe_damage_calculator.fields.calculated import AverageStats, CalculatedStats
from warframe_damage_calculator.fields.weapon_data import Attack


def _dot_stats(*, heat: float = 100.0, status_chance: float = 1.0, multishot: float = 2.0, forced_heat: float = 0.0):
    base = CalculatedStats({"damage": Dist({"heat": heat}), "forced_procs": Dist({"heat": forced_heat})})
    effective = CalculatedStats({"damage": Dist({"heat": heat}), "status_chance": status_chance, "status_duration": 6.0, "status_damage": 1.0, "multishot": multishot, "crit_chance": 0.0, "crit_damage": 2.0, "non_crit_bonus_damage": 0.0, "non_crit_bonus_chance": 0.0})
    average = AverageStats({"crit_chance": 0.0, "weakpoint_crit_chance": 0.0, "corpus_damage": 1.0, "grineer_damage": 1.0, "infested_damage": 1.0, "orokin_damage": 1.0, "murmur_damage": 1.0, "sentient_damage": 1.0})
    return base, effective, average


class HelperTests(unittest.TestCase):
    def test_crit_multiplier(self):
        self.assertAlmostEqual(formulas.crit_multiplier(0.5, 3.0), 2.0)
        self.assertAlmostEqual(formulas.crit_multiplier(0.0, 3.0), 1.0)
        self.assertAlmostEqual(formulas.crit_multiplier(2.0, 2.0), 3.0)

    def test_combo_multiplier_from_hits(self):
        self.assertEqual(MeleeCalculator._combo_multiplier_from_hits(0), 1)
        self.assertEqual(MeleeCalculator._combo_multiplier_from_hits(19), 1)
        self.assertEqual(MeleeCalculator._combo_multiplier_from_hits(20), 2)
        self.assertEqual(MeleeCalculator._combo_multiplier_from_hits(220), 12)
        self.assertEqual(MeleeCalculator._combo_multiplier_from_hits(999), 12)

    def test_hit_multiplier_includes_non_crit_bonus(self):
        # 12% crit @ 2.2x, Attrition +2000% @ 50% → expected non-crit bonus 10
        self.assertAlmostEqual(formulas.hit_multiplier(0.12, 2.2, 20, 0.5), 9.944)
        self.assertAlmostEqual(formulas.hit_multiplier(0.0, 2.0, 2.4), 3.4)
        self.assertAlmostEqual(formulas.hit_multiplier(1.5, 2.0, 20, 0.5), formulas.crit_multiplier(1.5, 2.0))

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
        formulas.refresh_dps_from_dph(average)
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
        self.assertAlmostEqual(WeaponCalculator._status_hits(None, result), 2.5)

    def test_beam_random_dot_double_dips_multishot(self):
        base, effective, average = _dot_stats(multishot=2.0)
        kwargs = dict(base=base, effective=effective, average=average, status_attempts_per_attack=1.0, faction_damage=1.0)
        hitscan = flat_dotph(**kwargs, continuous=False)
        beam = flat_dotph(**kwargs, continuous=True)
        # Heat DoT factor 0.5 → regular = 50; shared = 6 → hitscan 600, beam 1200 (MS²).
        self.assertAlmostEqual(hitscan, 600.0)
        self.assertAlmostEqual(beam, 1200.0)
        self.assertAlmostEqual(beam / hitscan, 2.0)

    def test_beam_forced_dot_scales_once_with_multishot(self):
        base, effective, average = _dot_stats(status_chance=0.0, multishot=3.0, forced_heat=1.0)
        kwargs = dict(base=base, effective=effective, average=average, status_attempts_per_attack=1.0, faction_damage=1.0)
        hitscan = flat_dotph(**kwargs, continuous=False)
        beam = flat_dotph(**kwargs, continuous=True)
        # Forced heat only: 0.5 * 100 * MS * 6 = 900 for both (no second MS on forced).
        self.assertAlmostEqual(hitscan, 900.0)
        self.assertAlmostEqual(beam, 900.0)

    def test_flat_dotph_from_result_uses_beam_delivery(self):
        base, effective, average = _dot_stats(multishot=2.0)
        hitscan = AttackResult({"name": "hitscan", "attack": Attack({"name": "hitscan", "delivery": "hitscan"}), "base": base, "effective": effective, "average": average})
        beam = AttackResult({"name": "beam", "attack": Attack({"name": "beam", "delivery": "beam"}), "base": base, "effective": effective, "average": average})
        self.assertAlmostEqual(flat_dotph_from_result(hitscan, status_attempts_per_attack=1.0, faction_damage=1.0), 600.0)
        self.assertAlmostEqual(flat_dotph_from_result(beam, status_attempts_per_attack=1.0, faction_damage=1.0), 1200.0)


if __name__ == "__main__":
    unittest.main()
