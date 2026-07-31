import unittest

from warframe_damage_calculator import Attack, AttackStats, Calculator, Dist, Effect, ImplementationStatus, Loadout, Progenitor, PLACEHOLDER, Perk, PerkValues, Primary, ResultFormatter, UpgradeStats, arsenal, format_damage_result, format_loadout, format_perk, format_spatial, format_status, format_upgrade, format_weapon


class ApiTests(unittest.TestCase):
    def test_weapon_is_definition_only(self):
        weapon = arsenal.weapon.get("Phenmor")
        for field in ("build", "loadout", "target", "runtime", "results", "format", "evolutions"): self.assertFalse(hasattr(weapon, field))

    def test_loadout_contains_upgrades_and_global_perks(self):
        loadout = Loadout(upgrades=[arsenal.upgrade.get("Serration")], evolutions=[arsenal.perk.get("Elemental Excess")])
        self.assertEqual(loadout.upgrades[0].name, "Serration")
        self.assertEqual(loadout.evolutions[0].name, "Elemental Excess")

    def test_global_perk_contains_placeholder_stats(self):
        perk = arsenal.perk.get("Elemental Excess")
        self.assertTrue(any(effect.value is PLACEHOLDER for effect in perk.stats.status_chance))

    def test_same_perk_resolves_differently_for_two_weapons(self):
        perk = arsenal.perk.get("Elemental Balance")
        telos = arsenal.weapon.get("Telos Boltor").resolve_perk(perk)
        prime = arsenal.weapon.get("Boltor Prime").resolve_perk(perk)
        telos_values = tuple(effect.value for effect in telos.effects if effect.stat == "status_chance")
        prime_values = tuple(effect.value for effect in prime.effects if effect.stat == "status_chance")
        self.assertNotEqual(telos_values, prime_values)

    def test_placeholder_metadata_is_preserved_during_resolution(self):
        perk = arsenal.perk.get("Devouring Attrition")
        resolved = arsenal.weapon.get("Phenmor").resolve_perk(perk)
        template = perk.stats.damage_bonus[0]
        effect = resolved.effects[0]
        self.assertEqual((effect.stat, effect.mode, effect.family, effect.maximum, effect.automatic), ("damage_bonus", template.mode, template.family, template.maximum, template.automatic))
        self.assertIsNot(effect.value, PLACEHOLDER)

    def test_missing_and_unknown_weapon_values_are_rejected(self):
        perk = Perk("Test", stats=UpgradeStats(damage_bonus=Effect(PLACEHOLDER)))
        attack = Attack("shot", stats=AttackStats(damage=Dist(impact=1)))
        missing = Primary(name="Missing", attacks=[attack], perks=[PerkValues(perk, 2, 1, {})])
        with self.assertRaisesRegex(ValueError, "supplies no values"): missing.resolve_perk(perk)
        unknown = Primary(name="Unknown", attacks=[attack], perks=[PerkValues(perk, 2, 1, {"damage_bonus": (1,), "crit_chance": (1,)})])
        with self.assertRaisesRegex(ValueError, "unknown values"): unknown.resolve_perk(perk)

    def test_calculator_uses_resolved_global_template(self):
        perk = Perk("Flat Critical", stats=UpgradeStats(crit_chance=Effect(PLACEHOLDER, mode="flat")))
        weapon = Primary(name="Template", attacks=[Attack("shot", stats=AttackStats(damage=Dist(impact=10), crit_chance=0.1))], reload_time=1, perks=[PerkValues(perk, 2, 1, {"crit_chance": (0.4,)})])
        result = Calculator(weapon).calculate(Loadout(evolutions=[perk]))
        self.assertAlmostEqual(result.attacks["shot"].effective.crit_chance, 0.5)

    def test_result_navigation_distinguishes_aggregate_and_components(self):
        result = Calculator(arsenal.weapon.get("Corinth Prime")).calculate(attack="air_burst_projectile")
        root = result.attacks[result.selected_attack]
        self.assertFalse(hasattr(result.aggregate, "name"))
        self.assertFalse(hasattr(root, "name"))
        self.assertFalse(hasattr(root, "attack"))
        self.assertFalse(hasattr(root, "children"))
        self.assertFalse(hasattr(root, "original_damage"))
        self.assertFalse(hasattr(result.aggregate, "components"))
        self.assertFalse(hasattr(result.aggregate, "spatial"))
        self.assertGreater(result.aggregate.average.normal.total_dps, root.average.normal.total_dps)
        self.assertGreater(result.attacks["air_burst_explosion"].average.normal.total_dps, 0)
        self.assertFalse(hasattr(result, "main"))

    def test_prepared_and_ordinary_calculations_are_equal(self):
        weapon = arsenal.weapon.get("Phenmor")
        loadout = Loadout(evolutions=[arsenal.perk.get("Devouring Attrition")])
        calculator = Calculator(weapon)
        ordinary = calculator.calculate(loadout, attack="incarnon_form")
        prepared = calculator.prepare(attack="incarnon_form").calculate(loadout)
        self.assertEqual(prepared.aggregate.average, ordinary.aggregate.average)
        self.assertEqual(prepared.attacks.keys(), ordinary.attacks.keys())

    def test_calculation_does_not_mutate_weapon_definition(self):
        weapon = arsenal.weapon.get("Bo Prime")
        before = (repr(weapon.attacks), repr(weapon.perks), dict(weapon.calculation_defaults))
        Calculator(weapon).calculate(state={"combo": 5})
        self.assertEqual((repr(weapon.attacks), repr(weapon.perks), dict(weapon.calculation_defaults)), before)


    def test_implementation_status_and_progenitor_loadout(self):
        self.assertEqual(arsenal.weapon.get("Kuva Chakkhurr").implementation_status, ImplementationStatus("partial", ("multiplicative_weakpoint_crit_chance",)))
        loadout = Loadout(progenitor=Progenitor("heat", 0.6))
        result = Calculator(arsenal.weapon.get("Kuva Chakkhurr")).calculate(loadout)
        self.assertEqual(result.loadout.progenitor, loadout.progenitor)
        self.assertGreater(result.attacks[result.selected_attack].base.damage.total, Calculator(arsenal.weapon.get("Kuva Chakkhurr")).calculate().attacks["normal_attack"].base.damage.total)

    def test_formatter_coverage(self):
        weapon = arsenal.weapon.get("Corinth Prime")
        upgrade = arsenal.upgrade.get("Galvanized Hell")
        perk = arsenal.perk.get("Elemental Excess")
        loadout = Loadout(upgrades=[upgrade])
        result = Calculator(weapon).calculate(loadout)
        formatter = ResultFormatter(result)
        self.assertIn("Corinth Prime", format_weapon(weapon))
        self.assertIn("Galvanized Hell", format_upgrade(upgrade))
        self.assertIn("Elemental Excess", format_perk(perk))
        self.assertIn("Galvanized Hell", format_loadout(loadout))
        self.assertIn("TOTAL DPS", formatter.summary())
        fire_rate_result = Calculator(weapon).calculate(Loadout(upgrades=[arsenal.upgrade.get("Critical Deceleration")]))
        fire_rate_attack = fire_rate_result.attacks[fire_rate_result.selected_attack]
        self.assertAlmostEqual(fire_rate_attack.modded.fire_rate, fire_rate_attack.effective.instantaneous_fire_rate)
        self.assertIn("1.14", ResultFormatter(fire_rate_result).summary().split("Fire Rate", 1)[1].splitlines()[0])
        targeted = ResultFormatter(Calculator(weapon, arsenal.enemy.get("Heavy Gunner")).calculate(loadout))
        self.assertIn("Corinth Prime · Buckshot vs Heavy Gunner · TOTAL DPS Contributions", targeted.contributions())
        contribution_table = targeted.contributions()
        self.assertIn("\x1b[32m", contribution_table)
        self.assertIn("DPH", format_damage_result(result.aggregate.average))
        self.assertIn("Expected procs", format_status(result.aggregate.status))
        aoe = Calculator(weapon).calculate(attack="air_burst_explosion").attacks["air_burst_explosion"].spatial
        self.assertIsNotNone(aoe)
        self.assertIn("Damage mass", format_spatial(aoe))
        melee_result = Calculator(arsenal.weapon.get("Tenet Exec")).calculate()
        melee_summary = ResultFormatter(melee_result).summary()
        self.assertIn("Tenet Exec", melee_summary)
        self.assertIn("Reload Time", melee_summary)

    def test_contributions_include_upgrades_and_evolutions(self):
        from warframe_damage_calculator import removal_contributions, shapley_contributions

        weapon = arsenal.weapon.get("Phenmor")
        loadout = Loadout(upgrades=[arsenal.upgrade.get("Serration")], evolutions=[arsenal.perk.get("Devouring Attrition")])
        calculator = Calculator(weapon)
        removal = removal_contributions(calculator, loadout, attack="incarnon_form")
        shapley = shapley_contributions(calculator, loadout, attack="incarnon_form")
        self.assertEqual(set(removal), {"Serration", "Devouring Attrition"})
        self.assertEqual(set(shapley), set(removal))
        self.assertAlmostEqual(sum(shapley.values()), 1)


if __name__ == "__main__": unittest.main()
