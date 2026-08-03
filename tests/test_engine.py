import unittest

from warframe_damage_calculator import Calculator, Build, arsenal
from warframe_damage_calculator.domain.damage import Dist
from warframe_damage_calculator.domain.weapons import Attack, AttackStats, Primary


class EngineTests(unittest.TestCase):
    def test_direct_attack_has_no_spatial_damage_mass(self):
        weapon = Primary(name="Direct", attacks=[Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), punch_through=5))], reload_time=1)
        result = Calculator(weapon).resolve()
        self.assertIsNone(result.attacks["shot"].spatial)
        self.assertEqual(result.aggregate.average.total_dph, 100)

    def test_punch_through_does_not_scale_ordinary_damage(self):
        without = Primary(name="Without", attacks=[Attack(name="shot", stats=AttackStats(damage=Dist(impact=100)))], reload_time=1)
        with_punch_through = Primary(name="With", attacks=[Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), punch_through=10))], reload_time=1)
        self.assertEqual(Calculator(without).resolve().aggregate.average, Calculator(with_punch_through).resolve().aggregate.average)

    def test_aoe_exposes_raw_spatial_damage_mass(self):
        weapon = Primary(name="AOE", attacks=[Attack(name="blast", aoe=True, stats=AttackStats(damage=Dist(impact=100), falloff={"start_range": 0, "end_range": 5, "final_multiplier": 0.5}))], reload_time=1)
        result = Calculator(weapon).resolve()
        spatial = result.attacks["blast"].spatial
        self.assertIsNotNone(spatial)
        self.assertEqual(spatial.dimension, 3)
        self.assertGreater(spatial.total_dph_mass, result.aggregate.average.total_dph)

    def test_evolution_values_are_weapon_specific(self):
        perk = arsenal.perk.get("Elemental Balance")
        telos = arsenal.primary.get("Telos Boltor").resolve_perk(perk)
        prime = arsenal.primary.get("Boltor Prime").resolve_perk(perk)
        telos_value = next(effect.value for effect in telos.effects if effect.stat == "status_chance")
        prime_value = next(effect.value for effect in prime.effects if effect.stat == "status_chance")
        self.assertNotEqual(telos_value, prime_value)

    def test_build_evolutions_change_results(self):
        weapon = arsenal.primary.get("Phenmor")
        baseline = Calculator(weapon).resolve(attack="incarnon_form")
        evolved = Calculator(weapon, build=Build(evolutions=[arsenal.perk.get("Elemental Excess")])).resolve(attack="incarnon_form")
        self.assertNotEqual(baseline.attacks["incarnon_form"].effective.status_chance, evolved.attacks["incarnon_form"].effective.status_chance)


if __name__ == "__main__": unittest.main()
