import unittest

from warframe_damage_calculator import Calculator, Build, arsenal
from warframe_damage_calculator.domain.damage import Dist
from warframe_damage_calculator.domain.weapons import Attack, AttackStats, Primary


class EngineTests(unittest.TestCase):
    def test_direct_attack_has_no_spatial_damage_mass(self):
        weapon = Primary(name="Direct", attacks=[Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), punch_through=5))], reload_time=1)
        result = Calculator(weapon).resolve()
        self.assertIsNone(result.attacks["shot"].spatial.damage_mass)
        self.assertEqual(result.aggregate.damage.total_dph, 100)

    def test_punch_through_does_not_scale_ordinary_damage(self):
        without = Primary(name="Without", attacks=[Attack(name="shot", stats=AttackStats(damage=Dist(impact=100)))], reload_time=1)
        with_punch_through = Primary(name="With", attacks=[Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), punch_through=10))], reload_time=1)
        self.assertEqual(Calculator(without).resolve().aggregate.damage, Calculator(with_punch_through).resolve().aggregate.damage)

    def test_aoe_exposes_raw_spatial_damage_mass(self):
        weapon = Primary(name="AOE", attacks=[Attack(name="blast", aoe=True, stats=AttackStats(damage=Dist(impact=100), falloff={"start_range": 0, "end_range": 5, "final_multiplier": 0.5}))], reload_time=1)
        result = Calculator(weapon).resolve()
        spatial = result.attacks["blast"].spatial
        self.assertIsNotNone(spatial.damage_mass)
        self.assertEqual(spatial.dimension, 3)
        self.assertGreater(spatial.total_dph_mass, result.aggregate.damage.total_dph)

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
        evolved = Calculator(weapon, build=Build(perks=[arsenal.perk.get("Elemental Excess")])).resolve(attack="incarnon_form")
        self.assertNotEqual(baseline.attacks["incarnon_form"].effective.status_chance, evolved.attacks["incarnon_form"].effective.status_chance)

    def test_resolve_perks_rejects_unknown_weapon_perks(self):
        from warframe_damage_calculator.engine.perks import resolve_perks

        weapon = arsenal.primary.get("Vectis Prime")
        with self.assertRaisesRegex(ValueError, "not compatible with Vectis Prime"):
            resolve_perks(weapon, [arsenal.perk.get("Devouring Attrition")])

    def test_resolve_perks_warns_on_wrong_list_position_but_pairs_correctly(self):
        import warnings

        from warframe_damage_calculator.domain.warnings import PerkCompatibilityWarning
        from warframe_damage_calculator.engine.perks import resolve_perks

        weapon = arsenal.primary.get("Vectis Prime")
        inciting = weapon.perk_choices[2]["Inciting Incident"]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", PerkCompatibilityWarning)
            resolved = resolve_perks(weapon, [inciting])
        self.assertTrue(any(issubclass(item.category, PerkCompatibilityWarning) for item in caught))
        self.assertTrue(any("position 1" in str(item.message) for item in caught))
        matched = next(item for item in resolved if item.perk.name == "Inciting Incident")
        self.assertEqual(matched.tier, 2)
        self.assertEqual(matched.effects, weapon.resolve_perk(inciting).effects)

    def test_resolve_perks_warns_on_duplicate_tier_and_keeps_first(self):
        import warnings

        from warframe_damage_calculator.domain.warnings import PerkCompatibilityWarning
        from warframe_damage_calculator.engine.perks import resolve_perks

        weapon = arsenal.primary.get("Vectis Prime")
        inciting = weapon.perk_choices[2]["Inciting Incident"]
        lone = weapon.perk_choices[2]["Lone Enforcer"]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", PerkCompatibilityWarning)
            resolved = resolve_perks(weapon, [inciting, lone])
        self.assertTrue(any("keeping Inciting Incident" in str(item.message) for item in caught))
        self.assertEqual([item.perk.name for item in resolved if item.tier == 2], ["Inciting Incident"])


if __name__ == "__main__": unittest.main()
