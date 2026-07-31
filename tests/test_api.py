import unittest

from warframe_damage_calculator import Attack, AttackStats, BodyPart, Calculator, Dist, Effect, Enemy, ImplementationStatus, Loadout, Progenitor, PLACEHOLDER, Perk, PerkValues, Primary, ResultFormatter, UpgradeStats, arsenal, format_damage_result, format_loadout, format_perk, format_spatial, format_status, format_upgrade, format_weapon


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
        result = Calculator(weapon, loadout=Loadout(evolutions=[perk])).calculate()
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
        self.assertGreater(result.aggregate.average.total_dps, root.average.total_dps)
        self.assertGreater(result.attacks["air_burst_explosion"].average.total_dps, 0)
        self.assertFalse(hasattr(result, "main"))

    def test_prepared_and_ordinary_calculations_are_equal(self):
        weapon = arsenal.weapon.get("Phenmor")
        loadout = Loadout(evolutions=[arsenal.perk.get("Devouring Attrition")])
        calculator = Calculator(weapon, loadout=loadout)
        ordinary = calculator.calculate(attack="incarnon_form")
        repeated = calculator.calculate(attack="incarnon_form")
        self.assertEqual(repeated.aggregate.average, ordinary.aggregate.average)
        self.assertEqual(repeated.attacks.keys(), ordinary.attacks.keys())

    def test_calculation_does_not_mutate_weapon_definition(self):
        weapon = arsenal.weapon.get("Bo Prime")
        before = (repr(weapon.attacks), repr(weapon.perks), dict(weapon.calculation_defaults))
        Calculator(weapon).calculate(state={"combo": 5})
        self.assertEqual((repr(weapon.attacks), repr(weapon.perks), dict(weapon.calculation_defaults)), before)


    def test_implementation_status_and_progenitor_loadout(self):
        self.assertEqual(arsenal.weapon.get("Kuva Chakkhurr").implementation_status, ImplementationStatus("partial", ("multiplicative_weakpoint_crit_chance",)))
        loadout = Loadout(progenitor=Progenitor("heat", 0.6))
        result = Calculator(arsenal.weapon.get("Kuva Chakkhurr"), loadout=loadout).calculate()
        self.assertEqual(result.loadout.progenitor, loadout.progenitor)
        attack = result.attacks[result.selected_attack]
        without_progenitor = Calculator(arsenal.weapon.get("Kuva Chakkhurr")).calculate().attacks["normal_attack"]
        self.assertEqual(attack.base.damage, without_progenitor.base.damage)
        self.assertGreater(attack.modded.damage.total, without_progenitor.modded.damage.total)

    def test_progenitor_is_excluded_from_base_and_included_in_modded_damage(self):
        weapon = arsenal.weapon.get("Tenet Exec")
        result = Calculator(weapon, loadout=Loadout(progenitor=Progenitor("electricity", 0.6))).calculate(attack="heavy_slam_attack")
        attack = result.attacks["heavy_slam_attack"]
        self.assertEqual(attack.base.damage, Dist(impact=570))
        self.assertEqual(attack.modded.damage, Dist(impact=570, electricity=342))
        self.assertEqual(attack.effective.damage, attack.modded.damage)
        modded = Calculator(weapon, loadout=Loadout(upgrades=[arsenal.upgrade.get("Fever Strike")], progenitor=Progenitor("electricity", 0.6))).calculate(attack="heavy_slam_attack").attacks["heavy_slam_attack"]
        self.assertEqual(modded.base.damage, Dist(impact=570))
        self.assertEqual(modded.modded.damage, Dist(impact=570, corrosive=855))


    def test_modded_stats_exclude_stance_and_combo_scaling(self):
        weapon = arsenal.weapon.get("Tenet Exec")
        target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
        loadout = Loadout(upgrades=[arsenal.upgrade.get("Rending Crane"), arsenal.upgrade.get("Galvanized Steel"), arsenal.upgrade.get("Primed Pressure Point")], progenitor=Progenitor("electricity", 0.6))
        attack = Calculator(weapon, target, loadout).calculate(attack="heavy_slam_attack", state={"stance_combo": "heavy"}).attacks["heavy_slam_attack"]
        self.assertEqual(attack.base.damage, Dist(impact=570))
        self.assertEqual(attack.modded.damage, Dist(impact=1510.5, electricity=906.3))
        self.assertEqual(attack.effective.damage, Dist(impact=6042, electricity=3625.2))
        self.assertAlmostEqual(attack.modded.crit_chance, 1.216)
        self.assertAlmostEqual(attack.modded.crit_damage, 5.28)

    def test_formatter_coverage(self):
        weapon = arsenal.weapon.get("Corinth Prime")
        upgrade = arsenal.upgrade.get("Galvanized Hell")
        perk = arsenal.perk.get("Elemental Excess")
        loadout = Loadout(upgrades=[upgrade])
        result = Calculator(weapon, loadout=loadout).calculate()
        formatter = ResultFormatter(result)
        self.assertIn("Corinth Prime", format_weapon(weapon))
        self.assertIn("Galvanized Hell", format_upgrade(upgrade))
        self.assertIn("Elemental Excess", format_perk(perk))
        self.assertIn("Galvanized Hell", format_loadout(loadout))
        summary = formatter.summary()
        self.assertIn("Total DPS", summary)
        self.assertTrue(summary.startswith("┌"))
        self.assertTrue(summary.endswith("┘"))
        self.assertIn("├", summary)
        self.assertIn("┬", summary.splitlines()[2])
        self.assertIn("┼", summary)
        fire_rate_result = Calculator(weapon, loadout=Loadout(upgrades=[arsenal.upgrade.get("Critical Deceleration")])).calculate()
        fire_rate_attack = fire_rate_result.attacks[fire_rate_result.selected_attack]
        self.assertAlmostEqual(fire_rate_attack.modded.fire_rate, fire_rate_attack.effective.instantaneous_fire_rate)
        self.assertIn("1.14", ResultFormatter(fire_rate_result).summary().split("Fire Rate", 1)[1].splitlines()[0])
        targeted = ResultFormatter(Calculator(weapon, arsenal.enemy.get("Heavy Gunner"), loadout).calculate())
        self.assertIn("Total DPS Contributions: Corinth Prime Buckshot vs Heavy Gunner Body", targeted.contributions())
        self.assertIn("Total DPS Contributions: Corinth Prime Buckshot vs Heavy Gunner Head", targeted.contributions(bodypart="head"))
        resistant_target = Enemy(name="Heavy Gunner", bodyparts={"armor": BodyPart("resistant", 0.5)})
        resistant = ResultFormatter(Calculator(weapon, resistant_target, loadout).calculate())
        self.assertIn("Total DPS Contributions: Corinth Prime Buckshot vs Heavy Gunner Armor", resistant.contributions(bodypart="armor"))
        self.assertEqual(ResultFormatter._metric_name("dot_dps"), "DoT DPS")
        contribution_table = targeted.contributions()
        self.assertNotIn("\x1b[", contribution_table)
        self.assertIn("+100.00%", contribution_table)
        self.assertIn("+460.51", contribution_table)
        self.assertIn("··········│", contribution_table)
        self.assertIn("Contribution Rank", contribution_table)
        self.assertIn("Regular Mod", contribution_table)
        self.assertIn("Regular Arcane", ResultFormatter(Calculator(arsenal.weapon.get("Phenmor"), arsenal.enemy.get("Heavy Gunner"), Loadout(upgrades=[arsenal.upgrade.get("Primary Merciless")])).calculate()).contributions())
        self.assertIn("DPH", format_damage_result(result.aggregate.average))
        self.assertIn("Expected procs", format_status(result.aggregate.status))
        aoe = Calculator(weapon).calculate(attack="air_burst_explosion").attacks["air_burst_explosion"].spatial
        self.assertIsNotNone(aoe)
        self.assertIn("Damage mass", format_spatial(aoe))
        melee_result = Calculator(arsenal.weapon.get("Tenet Exec")).calculate()
        melee_summary = ResultFormatter(melee_result).summary()
        self.assertIn("Tenet Exec", melee_summary)
        self.assertIn("Attack Speed", melee_summary)
        self.assertNotIn("Fire Rate", melee_summary)
        self.assertIn("Reload Time", melee_summary)

    def test_contributions_include_upgrades_and_evolutions(self):
        from warframe_damage_calculator import removal_contributions, shapley_contributions

        weapon = arsenal.weapon.get("Phenmor")
        loadout = Loadout(upgrades=[arsenal.upgrade.get("Serration")], evolutions=[arsenal.perk.get("Devouring Attrition")])
        calculator = Calculator(weapon)
        removal = removal_contributions(calculator, loadout, attack="incarnon_form")
        shapley = shapley_contributions(calculator, loadout, attack="incarnon_form")
        weakpoint_removal = removal_contributions(Calculator(weapon, arsenal.enemy.get("Heavy Gunner")), loadout, attack="incarnon_form", bodypart="head")
        weakpoint_shapley = shapley_contributions(Calculator(weapon, arsenal.enemy.get("Heavy Gunner")), loadout, attack="incarnon_form", bodypart="head")
        self.assertEqual(set(removal), {"Serration", "Devouring Attrition"})
        self.assertEqual(set(shapley), set(removal))
        self.assertAlmostEqual(sum(shapley.values()), 1)
        self.assertEqual(set(weakpoint_removal), set(removal))
        self.assertEqual(set(weakpoint_shapley), set(removal))
        self.assertAlmostEqual(sum(weakpoint_shapley.values()), 1)

        progenitor_loadout = Loadout(upgrades=[arsenal.upgrade.get("Primed Pressure Point")], progenitor=Progenitor("electricity", 0.6))
        progenitor_calculator = Calculator(arsenal.weapon.get("Tenet Exec"))
        progenitor_removal = removal_contributions(progenitor_calculator, progenitor_loadout, attack="heavy_slam_attack", state={"stance_combo": "heavy"})
        progenitor_shapley = shapley_contributions(progenitor_calculator, progenitor_loadout, attack="heavy_slam_attack", state={"stance_combo": "heavy"})
        progenitor_name = "Electricity Progenitor (60%)"
        self.assertIn(progenitor_name, progenitor_removal)
        self.assertIn(progenitor_name, progenitor_shapley)
        progenitor_table = ResultFormatter(Calculator(progenitor_calculator.weapon, loadout=progenitor_loadout).calculate(attack="heavy_slam_attack", state={"stance_combo": "heavy"})).contributions()
        self.assertIn("Progenitor", progenitor_table)
        self.assertIn(progenitor_name, progenitor_table)


if __name__ == "__main__": unittest.main()
