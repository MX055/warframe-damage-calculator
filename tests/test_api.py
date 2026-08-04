import unittest
from warframe_damage_calculator import Arcane, Attack, AttackStats, Automatic, BodyPart, Calculator, Combo, Compatibility, Dist, Effect, Enemy, Formatter, ImplementationStatus, Inheritance, Links, Build, Mod, Perk, PerkValues, Primary, Progenitor, RelatedAttacks, Source, State, Upgrade, UpgradeStats, UpgradeValue, arsenal
from warframe_damage_calculator.formatting.objects import format_build, format_perk, format_upgrade, format_weapon
from warframe_damage_calculator.formatting.results import format_damage_result, format_spatial, format_status


class ApiTests(unittest.TestCase):
    def test_root_api_exposes_definition_types_and_hides_internal_classes(self):
        import warframe_damage_calculator as package
        expected = ("Arcane", "Archgun", "Attack", "AttackStats", "Automatic", "BodyPart", "Build", "Calculator", "Combo", "Compatibility", "Dist", "Effect", "Enemy", "EnemyStats", "Falloff", "Formatter", "ImplementationStatus", "Inheritance", "Links", "Melee", "Mod", "OptimizationProgress", "Optimizer", "Perk", "PerkValues", "Primary", "Progenitor", "RelatedAttacks", "Secondary", "Source", "State", "Upgrade", "UpgradeStats", "UpgradeValue", "arsenal", "balanced_damage_metric")
        self.assertEqual(package.__all__, expected)
        for name in ("AggregateResult", "CalculationResult", "ImplementationWarning", "Metric", "ProgressCallback", "ResolvedPerk", "format_result"): self.assertFalse(hasattr(package, name))
        self.assertIs(package.Formatter, Formatter)

    def test_root_api_can_define_custom_mods_arcanes_perks_and_weapons(self):
        compatibility = Compatibility(types=["primary"])
        generated = Attack(
            name="Aftershock",
            aoe=True,
            inheritance=Inheritance(include=["trigger", "delivery", "form", "category"]),
            links=Links(parents=RelatedAttacks(names=["shot"])),
            stats={"damage": {"heat": {"source": "$parent.stats.damage.total", "multiplier": 0.1}}, "falloff": {"end_range": 2}},
        )
        mod = Mod(name="Custom Mod", max_rank=5, compatibility=compatibility, stats=UpgradeStats(damage_bonus=0.2, generated_attack=generated))
        arcane = Arcane(name="Primary Custom Arcane", max_rank=5, compatibility=compatibility, stats=UpgradeStats(multishot=0.3))
        perk = Perk(name="Custom Perk", stats=UpgradeStats(crit_chance=Effect(Source("$values.crit_chance.flat", default=0), mode="flat")))
        weapon = Primary(name="Custom Primary", attacks=[Attack("shot", stats=AttackStats(damage=Dist(impact=100), fire_rate=1))], reload_time=1, perks=[PerkValues(perk, 1, 1, {"crit_chance": {"flat": 0.2}})])
        result = Calculator(weapon, build=Build(mods=[mod], arcanes=[arcane], evolutions=[perk])).resolve()
        self.assertGreater(result.aggregate.damage.total_dps, 0)
        self.assertIn("aftershock", result.attacks)
        self.assertEqual(result.attacks["aftershock"].base.damage, Dist(heat=10))

    def test_weapon_is_definition_only(self):
        weapon = arsenal.primary.get("Phenmor")
        for field in ("build", "build", "target", "runtime", "results", "format", "evolutions"): self.assertFalse(hasattr(weapon, field))

    def test_state_is_a_public_mapping_for_calculators(self):
        state = State(combo_multiplier=5, stance_combo="heavy")
        result = Calculator(arsenal.melee.get("Xoris")).resolve(state=state)
        self.assertIsInstance(result.state, State)
        self.assertEqual(result.state, {"combo_multiplier": 5, "stance_combo": "heavy"})

    def test_build_contains_upgrades_and_global_perks(self):
        build = Build(mods=[arsenal.mod.get("Serration")], evolutions=[arsenal.perk.get("Elemental Excess")])
        self.assertEqual([upgrade.name for upgrade in build.upgrades], ["Serration", "Elemental Excess"])
        self.assertTrue(all(isinstance(upgrade, Upgrade) for upgrade in build.upgrades))
        self.assertEqual(build.evolutions[0].name, "Elemental Excess")

    def test_global_perk_contains_value_sources(self):
        perk = arsenal.perk.get("Elemental Excess")
        self.assertTrue(all(isinstance(effect.value, Source) and effect.value.path.startswith("$values.") for effect in perk.stats.status_chance))

    def test_same_perk_resolves_differently_for_two_weapons(self):
        perk = arsenal.perk.get("Elemental Balance")
        telos = arsenal.primary.get("Telos Boltor").resolve_perk(perk)
        prime = arsenal.primary.get("Boltor Prime").resolve_perk(perk)
        telos_values = tuple(effect.value for effect in telos.effects if effect.stat == "status_chance")
        prime_values = tuple(effect.value for effect in prime.effects if effect.stat == "status_chance")
        self.assertNotEqual(telos_values, prime_values)

    def test_source_metadata_is_preserved_during_resolution(self):
        perk = arsenal.perk.get("Devouring Attrition")
        resolved = arsenal.primary.get("Phenmor").resolve_perk(perk)
        template = perk.stats.damage_bonus[0]
        effect = resolved.effects[0]
        self.assertEqual((effect.stat, effect.mode, effect.family, effect.maximum), ("damage_bonus", template.mode, template.family, template.maximum))
        self.assertEqual(effect.automatic["on"], "non_critical_hit")
        self.assertEqual(effect.automatic["chance"], 0.5)
        self.assertNotIsInstance(effect.value, Source)

    def test_missing_and_unknown_weapon_values_are_rejected(self):
        perk = Perk(name="Test", stats=UpgradeStats(damage_bonus=Effect(Source("$values.damage_bonus.base", default=0))))
        attack = Attack("shot", stats=AttackStats(damage=Dist(impact=1)))
        ok_missing = Primary(name="Missing", attacks=[attack], perks=[PerkValues(perk, 2, 1, {})])
        self.assertEqual(ok_missing.resolve_perk(perk).effects[0].value, 0)
        unknown = Primary(name="Unknown", attacks=[attack], perks=[PerkValues(perk, 2, 1, {"damage_bonus": {"base": 1}, "crit_chance": {"base": 1}})])
        with self.assertRaisesRegex(ValueError, "unknown values"): unknown.resolve_perk(perk)
        bad_key = Primary(name="BadKey", attacks=[attack], perks=[PerkValues(perk, 2, 1, {"damage_bonus": {"nope": 1}})])
        with self.assertRaisesRegex(ValueError, "unknown .* value keys"): bad_key.resolve_perk(perk)

    def test_calculator_uses_resolved_global_template(self):
        perk = Perk(name="Flat Critical", stats=UpgradeStats(crit_chance=Effect(Source("$values.crit_chance.flat", default=0), mode="flat")))
        weapon = Primary(name="Template", attacks=[Attack("shot", stats=AttackStats(damage=Dist(impact=10), crit_chance=0.1))], reload_time=1, perks=[PerkValues(perk, 2, 1, {"crit_chance": {"flat": 0.4}})])
        result = Calculator(weapon, build=Build(evolutions=[perk])).resolve()
        self.assertAlmostEqual(result.attacks["shot"].effective.crit_chance, 0.5)

    def test_result_navigation_distinguishes_aggregate_and_components(self):
        result = Calculator(arsenal.primary.get("Corinth Prime")).resolve(attack="air_burst_projectile")
        root = result.attacks[result.selected_attack]
        self.assertFalse(hasattr(result.aggregate, "name"))
        self.assertFalse(hasattr(root, "name"))
        self.assertFalse(hasattr(root, "attack"))
        self.assertFalse(hasattr(root, "children"))
        self.assertFalse(hasattr(root, "original_damage"))
        self.assertFalse(hasattr(result.aggregate, "components"))
        self.assertFalse(hasattr(result.aggregate, "spatial"))
        self.assertGreater(result.aggregate.damage.total_dps, root.damage.total_dps)
        self.assertGreater(result.attacks["air_burst_explosion"].damage.total_dps, 0)
        self.assertFalse(hasattr(result, "main"))

    def test_prepared_and_ordinary_calculations_are_equal(self):
        weapon = arsenal.primary.get("Phenmor")
        build = Build(evolutions=[arsenal.perk.get("Devouring Attrition")])
        calculator = Calculator(weapon, build=build)
        ordinary = calculator.resolve(attack="incarnon_form")
        repeated = calculator.resolve(attack="incarnon_form")
        self.assertEqual(repeated.aggregate.damage, ordinary.aggregate.damage)
        self.assertEqual(repeated.attacks.keys(), ordinary.attacks.keys())

    def test_calculation_does_not_mutate_weapon_definition(self):
        weapon = arsenal.melee.get("Bo Prime")
        before = (repr(weapon.attacks), repr(weapon.perks), dict(weapon.calculation_defaults))
        Calculator(weapon).resolve(state={"combo_multiplier": 5})
        self.assertEqual((repr(weapon.attacks), repr(weapon.perks), dict(weapon.calculation_defaults)), before)


    def test_maiming_strike_only_scales_slide_crit_chance(self):
        weapon = arsenal.melee.get("Skana")
        maiming = arsenal.mod.get("Maiming Strike").copy()
        baseline = Calculator(weapon).resolve(attack="slide_attack")
        modded = Calculator(weapon, build=Build(mods=[maiming])).resolve(attack="slide_attack")
        normal = Calculator(weapon, build=Build(mods=[maiming])).resolve(attack="normal_attack")
        base_normal = Calculator(weapon).resolve(attack="normal_attack")
        self.assertAlmostEqual(modded.attacks["slide_attack"].modded.crit_chance, baseline.attacks["slide_attack"].modded.crit_chance * 2.5)
        self.assertAlmostEqual(normal.attacks["normal_attack"].modded.crit_chance, base_normal.attacks["normal_attack"].modded.crit_chance)

    def test_implementation_status_and_progenitor_build(self):
        self.assertEqual(arsenal.primary.get("Kuva Chakkhurr").implementation_status, ImplementationStatus("partial", ("multiplicative_weak_point_crit_chance",)))
        build = Build(progenitor=Progenitor(element="heat", bonus=0.6))
        result = Calculator(arsenal.primary.get("Kuva Chakkhurr"), build=build).resolve()
        self.assertEqual(result.build.progenitor, build.progenitor)
        attack = result.attacks[result.selected_attack]
        without_progenitor = Calculator(arsenal.primary.get("Kuva Chakkhurr")).resolve().attacks["normal_attack"]
        self.assertEqual(attack.base.damage, without_progenitor.base.damage)
        self.assertGreater(attack.modded.damage.total, without_progenitor.modded.damage.total)

    def test_progenitor_is_excluded_from_base_and_included_in_modded_damage(self):
        weapon = arsenal.melee.get("Tenet Exec")
        result = Calculator(weapon, build=Build(progenitor=Progenitor(element="electricity", bonus=0.6))).resolve(attack="heavy_slam_attack")
        attack = result.attacks["heavy_slam_attack"]
        self.assertEqual(attack.base.damage, Dist(impact=570))
        self.assertEqual(attack.base.status_chance, 0.22)
        self.assertEqual(attack.modded.damage, Dist(impact=570, electricity=342))
        self.assertEqual(attack.effective.damage, attack.modded.damage)
        modded = Calculator(weapon, build=Build(mods=[arsenal.mod.get("Fever Strike")], progenitor=Progenitor(element="electricity", bonus=0.6))).resolve(attack="heavy_slam_attack").attacks["heavy_slam_attack"]
        self.assertEqual(modded.base.damage, Dist(impact=570))
        self.assertEqual(modded.modded.damage, Dist(impact=570, corrosive=855))


    def test_modded_stats_exclude_stance_and_combo_scaling(self):
        weapon = arsenal.melee.get("Tenet Exec")
        target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
        build = Build(mods=[arsenal.mod.get("Rending Crane"), arsenal.mod.get("Galvanized Steel"), arsenal.mod.get("Primed Pressure Point")], progenitor=Progenitor(element="electricity", bonus=0.6))
        attack = Calculator(weapon, target, build).resolve(attack="heavy_slam_attack", state={"stance_combo": "heavy"}).attacks["heavy_slam_attack"]
        self.assertEqual(attack.base.damage, Dist(impact=570))
        self.assertEqual(attack.modded.damage, Dist(impact=1510.5, electricity=906.3))
        self.assertEqual(attack.effective.damage, Dist(impact=6042, electricity=3625.2))
        self.assertAlmostEqual(attack.modded.crit_chance, 1.216)
        self.assertAlmostEqual(attack.modded.crit_damage, 5.28)

    def test_formatter_coverage(self):
        weapon = arsenal.primary.get("Corinth Prime")
        upgrade = arsenal.mod.get("Galvanized Hell")
        perk = arsenal.perk.get("Elemental Excess")
        build = Build(mods=[upgrade])
        result = Calculator(weapon, build=build).resolve()
        formatter = Formatter(result)
        self.assertIn("Corinth Prime", format_weapon(weapon))
        self.assertIn("Galvanized Hell", format_upgrade(upgrade))
        self.assertIn("Elemental Excess", format_perk(perk))
        self.assertIn("Galvanized Hell", format_build(build))
        summary = formatter.stat_summary()
        self.assertIn("Total DPS", summary)
        self.assertTrue(summary.startswith("┌"))
        self.assertTrue(summary.endswith("┘"))
        self.assertIn("├", summary)
        self.assertIn("┬", summary.splitlines()[2])
        self.assertIn("┼", summary)
        long_title = Formatter._table(("A", "B"), [("x", "y")], title="This is a very long title that should stretch the whole table border")
        self.assertEqual(len({len(line) for line in long_title.splitlines()}), 1)
        fire_rate_result = Calculator(weapon, build=Build(mods=[arsenal.mod.get("Critical Deceleration")])).resolve()
        fire_rate_attack = fire_rate_result.attacks[fire_rate_result.selected_attack]
        self.assertAlmostEqual(fire_rate_attack.modded.fire_rate, fire_rate_attack.effective.fire_rate)
        fire_rate_summary = Formatter(fire_rate_result).stat_summary()
        self.assertIn("1.14a/s", fire_rate_summary.split("Fire Rate", 1)[1].splitlines()[0])
        self.assertIn("Attack Rate", fire_rate_summary)
        self.assertIn(f"{fire_rate_attack.timing.attack_rate:,.2f}a/s", fire_rate_summary.split("Attack Rate", 1)[1].splitlines()[0])
        self.assertEqual(fire_rate_attack.damage.damage, fire_rate_attack.effective.damage)
        self.assertEqual(fire_rate_attack.critical.crit_damage, fire_rate_attack.effective.crit_damage)
        self.assertEqual(fire_rate_attack.status.status_chance, fire_rate_attack.effective.status_chance)
        self.assertEqual(fire_rate_attack.timing.multishot, fire_rate_attack.effective.multishot)
        self.assertEqual(fire_rate_attack.timing.fire_rate, fire_rate_attack.effective.fire_rate)
        self.assertIn(f"{fire_rate_attack.critical.crit_damage:.2f}×", fire_rate_summary.split("Critical Damage", 1)[1].splitlines()[0])
        spatial_summary = Formatter(Calculator(weapon).resolve(attack="air_burst_explosion")).stat_summary()
        self.assertIn("Damage Mass", spatial_summary)
        self.assertIn("m³", spatial_summary.split("Damage Mass", 1)[1].splitlines()[0])
        self.assertNotIn("Damage Mass (m³)", spatial_summary)
        calculator = Calculator(weapon, arsenal.enemy.get("Heavy Gunner"), build)
        targeted = Formatter(calculator.resolve())
        self.assertIn("Balanced Damage Contributions: Corinth Prime Buckshot vs Heavy Gunner Body", targeted.build_summary())
        self.assertIn("Balanced Damage Contributions: Corinth Prime Buckshot vs Heavy Gunner Head", Formatter(calculator.resolve(body_part="head")).build_summary())
        resistant_target = Enemy(name="Heavy Gunner", body_parts={"armor": BodyPart("resistant", 0.5)})
        resistant = Formatter(Calculator(weapon, resistant_target, build).resolve(body_part="armor"))
        self.assertIn("Balanced Damage Contributions: Corinth Prime Buckshot vs Heavy Gunner Armor", resistant.build_summary())
        from warframe_damage_calculator.engine.metrics import balanced_damage_metric as balanced_metric
        self.assertEqual(Formatter._metric_label(balanced_metric), "Balanced Damage")
        self.assertEqual(Formatter._metric_label(lambda result: result.aggregate.damage.dot_dps), "<lambda>")
        contribution_table = targeted.build_summary(metric=lambda result: result.aggregate.damage.total_dps)
        self.assertNotIn("\x1b[", contribution_table)
        self.assertIn("+100.00%", contribution_table)
        self.assertIn("-460.51", contribution_table)
        self.assertIn("Removal Difference", contribution_table)
        self.assertIn("··········│", contribution_table)
        self.assertIn("Contribution Rank", contribution_table)
        self.assertIn("Regular Mod", contribution_table)
        self.assertIn("Regular Arcane", Formatter(Calculator(arsenal.primary.get("Phenmor"), arsenal.enemy.get("Heavy Gunner"), Build(arcanes=[arsenal.arcane.get("Primary Merciless")])).resolve()).build_summary())
        self.assertIn("DPH", format_damage_result(result.aggregate.damage))
        self.assertIn("Expected procs", format_status(result.aggregate.status))
        aoe = Calculator(weapon).resolve(attack="air_burst_explosion").attacks["air_burst_explosion"].spatial
        self.assertIsNotNone(aoe)
        self.assertIn("Damage mass", format_spatial(aoe))
        melee_result = Calculator(arsenal.melee.get("Tenet Exec")).resolve()
        melee_summary = Formatter(melee_result).stat_summary()
        self.assertIn("Tenet Exec", melee_summary)
        self.assertIn("Attack Speed", melee_summary)
        self.assertNotIn("Fire Rate", melee_summary)
        self.assertIn("a/s", melee_summary.split("Attack Speed", 1)[1].splitlines()[0])
        self.assertNotIn("Multishot", melee_summary)
        self.assertNotIn("Magazine Capacity", melee_summary)
        self.assertNotIn("Reload Time", melee_summary)
        self.assertNotIn("Ammo Cost", melee_summary)
        self.assertNotIn("Punch Through", melee_summary)
        self.assertNotIn("Burst Count", melee_summary)
        self.assertNotIn("Burst Delay", melee_summary)
        self.assertNotIn("Charge Time", melee_summary)
        self.assertIn("×", melee_summary.split("Expected Procs", 1)[1].splitlines()[0])

    def test_formatter_status_table_lists_damage_types_per_attack(self):
        result = Calculator(arsenal.primary.get("Corinth Prime")).resolve(attack="air_burst_projectile")
        table = Formatter(result).status_summary()
        lines = table.splitlines()
        self.assertTrue(table.startswith("┌"))
        self.assertTrue(table.endswith("┘"))
        self.assertEqual(len({len(line) for line in lines}), 1)
        self.assertIn("Damage Type", table)
        self.assertIn("Air Burst Projectile", table)
        self.assertIn("Air Burst Explosion", table)
        self.assertIn("Damage", table)
        self.assertIn("Weight", table)
        self.assertIn("Forced Procs", table)
        self.assertIn("Proc Rate", table)
        self.assertIn("Impact", table)
        self.assertIn("Blast", table)
        projectile = result.attacks["air_burst_projectile"]
        explosion = result.attacks["air_burst_explosion"]
        self.assertIn(f"{projectile.effective.damage['impact']:,.2f}", table)
        self.assertIn(f"{explosion.effective.damage['blast']:,.2f}", table)
        self.assertIn("1.00", table)
        impact_procs = projectile.effective.status_model.proc_count_per_attack("impact")
        if impact_procs: self.assertIn(f"{impact_procs:.2%}", table)
        braton = Formatter(Calculator(arsenal.primary.get("Braton")).resolve()).status_summary()
        self.assertIn("Impact", braton)
        self.assertIn("Puncture", braton)
        self.assertIn("Slash", braton)
        self.assertEqual(len({len(line) for line in braton.splitlines()}), 1)

    def test_contributions_include_upgrades_and_evolutions(self):
        weapon = arsenal.primary.get("Phenmor")
        build = Build(mods=[arsenal.mod.get("Serration")], evolutions=[arsenal.perk.get("Devouring Attrition")])
        contributions = Calculator(weapon, build=build).contributions(attack="incarnon_form")
        removal = contributions.removal
        contribution = contributions.contribution
        weak_point_contributions = Calculator(weapon, arsenal.enemy.get("Heavy Gunner"), build).contributions(attack="incarnon_form", body_part="head")
        weak_point_removal = weak_point_contributions.removal
        weak_point_contribution = weak_point_contributions.contribution
        self.assertEqual(set(removal), {"Serration", "Devouring Attrition"})
        self.assertEqual(set(contribution), set(removal))
        self.assertAlmostEqual(sum(contribution.values()), 1)
        self.assertLess(removal["Serration"], 0)
        self.assertLess(removal["Devouring Attrition"], 0)
        self.assertEqual(set(weak_point_removal), set(removal))
        self.assertEqual(set(weak_point_contribution), set(removal))
        self.assertAlmostEqual(sum(weak_point_contribution.values()), 1)
        self.assertLessEqual(contributions.evaluations, 4)
    
        locked_fire_rate = Build(mods=[arsenal.mod.get("Semi-Rifle Cannonade"), arsenal.mod.get("Vile Precision")])
        locked_contributions = Calculator(arsenal.primary.get("Vectis Prime"), build=locked_fire_rate).contributions()
        self.assertEqual(locked_contributions.contribution["Vile Precision"], 0)
        self.assertEqual(locked_contributions.removal["Vile Precision"], 0)
        self.assertIn("Balanced Damage Contributions", Formatter(Calculator(arsenal.primary.get("Vectis Prime"), build=locked_fire_rate).resolve()).build_summary())
        self.assertNotIn("Shapley", Formatter(Calculator(arsenal.primary.get("Vectis Prime"), build=locked_fire_rate).resolve()).build_summary())

        riven = Mod(name="Riven", stats=UpgradeStats(crit_chance=1.0, multishot=1.0))
        riven_table = Formatter(Calculator(arsenal.primary.get("Vectis Prime"), build=Build(mods=[riven])).resolve()).build_summary()
        self.assertIn("Riven", riven_table)
        self.assertNotIn("crit_chance=", riven_table)
        self.assertNotIn("multishot=", riven_table)

        progenitor_build = Build(mods=[arsenal.mod.get("Primed Pressure Point")], progenitor=Progenitor(element="electricity", bonus=0.6))
        progenitor_calculator = Calculator(arsenal.melee.get("Tenet Exec"), build=progenitor_build)
        progenitor_contributions = progenitor_calculator.contributions(attack="heavy_slam_attack", state={"stance_combo": "heavy"})
        progenitor_removal = progenitor_contributions.removal
        progenitor_contribution = progenitor_contributions.contribution
        progenitor_name = "Electricity Progenitor (60%)"
        self.assertIn(progenitor_name, progenitor_removal)
        self.assertIn(progenitor_name, progenitor_contribution)
        progenitor_table = Formatter(Calculator(progenitor_calculator.weapon, build=progenitor_build).resolve(attack="heavy_slam_attack", state={"stance_combo": "heavy"})).build_summary()
        self.assertIn("Progenitor", progenitor_table)
        self.assertIn("Electricity Progenitor", progenitor_table)
        self.assertNotIn("(60%)", progenitor_table)


if __name__ == "__main__": unittest.main()
