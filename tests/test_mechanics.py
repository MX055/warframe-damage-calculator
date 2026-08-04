import unittest
import warnings

from warframe_damage_calculator import Calculator, Build, arsenal
from warframe_damage_calculator.domain.damage import Dist
from warframe_damage_calculator.domain.enemies import BodyPart, Enemy, EnemyStats
from warframe_damage_calculator.domain.weapons import Attack, AttackStats, Primary


def perk(weapon, tier, name):
    return weapon.perk_choices[tier][name]


def build(*names, perks=()):
    return Build(mods=[arsenal.mod.get(name) for name in names if name not in arsenal.arcane.names], arcanes=[arsenal.arcane.get(name) for name in names if name in arsenal.arcane.names], perks=perks)


def selected(calculation):
    return calculation.attacks[calculation.selected_attack]


class MechanicsTests(unittest.TestCase):
    def setUp(self):
        self.warning_context = warnings.catch_warnings()
        self.warning_context.__enter__()
        warnings.simplefilter("ignore")

    def tearDown(self):
        self.warning_context.__exit__(None, None, None)

    def test_ranged_damage_crit_multishot_and_hunter_munitions(self):
        weapon = arsenal.primary.get("Braton")
        result = selected(Calculator(weapon, build=build("Serration", "Split Chamber", "Point Strike", "Vital Sense", "Hunter Munitions")).resolve())
        self.assertAlmostEqual(result.effective.damage.total, 63.6)
        self.assertAlmostEqual(result.effective.crit_chance, 0.3722579268292683)
        self.assertAlmostEqual(result.effective.crit_damage, 3.52)
        self.assertAlmostEqual(result.effective.multishot, 1.9)
        self.assertAlmostEqual(result.damage.direct_dph, 234.19879265268293)
        self.assertAlmostEqual(result.damage.dot_dph, 109.7888138116019)
        self.assertAlmostEqual(result.damage.total_dps, 2202.3596755335307)

    def test_melee_combo_status_duplicate_and_doughty(self):
        weapon = arsenal.melee.get("Bo Prime")
        calculation = Calculator(weapon, build=build("Condition Overload", "Blood Rush", "Weeping Wounds", "Melee Duplicate", "Melee Doughty")).resolve(state={"combo_multiplier": 12})
        result = selected(calculation)
        self.assertAlmostEqual(result.effective.damage.total, 457.6)
        self.assertAlmostEqual(result.effective.crit_chance, 1.4886961152000002)
        self.assertAlmostEqual(result.effective.status_chance, 1.856)
        self.assertAlmostEqual(result.effective.crit_damage, 4.5)
        self.assertAlmostEqual(result.critical.puncture_status_crit_damage_bonus, 1.9)
        self.assertAlmostEqual(result.damage.direct_dph, 2841.8956981043207)
        self.assertIn("melee_duplicate", calculation.attacks)
        self.assertAlmostEqual(calculation.attacks["melee_duplicate"].damage.direct_dph, 1727.8725844474266)
        self.assertAlmostEqual(calculation.aggregate.damage.total_dps, 4935.349745155888)

    def test_resolve_status_stack_bonus_caps_and_scales(self):
        from warframe_damage_calculator.engine.formulas import resolve_status_stack_bonus

        self.assertEqual(resolve_status_stack_bonus(0, 1, 50), 0)
        self.assertEqual(resolve_status_stack_bonus(2.5, 1, 50), 2.5)
        self.assertEqual(resolve_status_stack_bonus(50, 1, 50), 50)
        self.assertEqual(resolve_status_stack_bonus(80, 1, 50), 50)
        self.assertEqual(resolve_status_stack_bonus(3, 1.5, None), 4.5)

    def test_melee_doughty_uses_puncture_status_stack_bonus(self):
        weapon = arsenal.melee.get("Bo Prime")
        without = selected(Calculator(weapon, build=build("Condition Overload", "Blood Rush", "Weeping Wounds")).resolve(state={"combo_multiplier": 12}))
        with_doughty = selected(Calculator(weapon, build=build("Condition Overload", "Blood Rush", "Weeping Wounds", "Melee Doughty")).resolve(state={"combo_multiplier": 12}))
        self.assertEqual(without.critical.puncture_status_crit_damage_bonus, 0)
        self.assertGreater(with_doughty.critical.puncture_status_crit_damage_bonus, 0)
        self.assertAlmostEqual(with_doughty.effective.crit_damage, without.effective.crit_damage + with_doughty.critical.puncture_status_crit_damage_bonus)
        status = with_doughty.effective.status_model
        puncture_chance = min(status.proc_count_per_attack("puncture") / max(status.attempts_per_attack, 1), 1)
        from warframe_damage_calculator.engine.formulas import resolve_status_stack_bonus
        self.assertAlmostEqual(with_doughty.critical.puncture_status_crit_damage_bonus, resolve_status_stack_bonus(puncture_chance / 0.1, 1, 50))

    def test_enervate_reset_expectation_and_encumber_random_proc(self):
        enervate = selected(Calculator(arsenal.secondary.get("Laetum"), build=build("Secondary Enervate")).resolve())
        self.assertGreater(enervate.critical.secondary_enervate_bonus, 0)
        self.assertAlmostEqual(enervate.damage.direct_dph, 378.6766179484155)
        self.assertAlmostEqual(enervate.damage.total_dps, 906.835830831968)
        encumber = selected(Calculator(arsenal.secondary.get("Lato"), build=build("Secondary Encumber")).resolve())
        self.assertAlmostEqual(encumber.damage.dot_dph, 3.456118444195631)

    def test_magazine_position_effects_use_shot_class_mixture(self):
        charged = selected(Calculator(arsenal.primary.get("Braton"), build=build("Charged Chamber")).resolve())
        self.assertAlmostEqual(charged.damage.first_shot_damage_multiplier, 1.008888888888889)
        self.assertAlmostEqual(charged.damage.direct_dph, 26.5092002601626)
        synth = selected(Calculator(arsenal.secondary.get("Lato"), build=build("Synth Charge")).resolve())
        self.assertAlmostEqual(synth.damage.direct_dph, 49.555459459459456)

    def test_incarnon_form_condition_and_multishot_ammo_mechanics(self):
        weapon = arsenal.primary.get("Braton")
        calculation = Calculator(weapon, build=Build(perks=[perk(weapon, 2, "Munitions Grit")])).resolve(attack="incarnon_form")
        result = selected(calculation)
        self.assertAlmostEqual(result.effective.multishot, 1.2)
        self.assertAlmostEqual(result.effective.ammo_cost, 1.2)
        self.assertAlmostEqual(result.modded.multishot, 1.2)
        self.assertAlmostEqual(result.modded.ammo_cost, 1.2)
        self.assertAlmostEqual(result.effective.damage.total, 70.4)
        self.assertAlmostEqual(calculation.aggregate.damage.total_dps, 1539.4027259436357)

    def test_ammo_efficiency_combines_into_modded_ammo_cost(self):
        from warframe_damage_calculator.domain.upgrades import Mod, UpgradeStats

        weapon = arsenal.primary.get("Braton")
        without = selected(Calculator(weapon).resolve())
        efficiency = Mod(name="Ammo Efficiency", max_rank=0, stats=UpgradeStats(ammo_efficiency=0.5))
        with_efficiency = selected(Calculator(weapon, build=Build(mods=[efficiency])).resolve())
        self.assertAlmostEqual(without.modded.ammo_cost, 1.0)
        self.assertAlmostEqual(with_efficiency.modded.ammo_efficiency, 0.5)
        self.assertAlmostEqual(with_efficiency.modded.ammo_cost, 0.5)
        self.assertAlmostEqual(with_efficiency.effective.ammo_cost, 0.5)
        self.assertGreater(with_efficiency.timing.attack_rate, without.timing.attack_rate)

    def test_target_pool_armor_status_and_body_part_model(self):
        target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
        calculator = Calculator(arsenal.primary.get("Braton"), target, build("Serration"))
        body = selected(calculator.resolve(body_part="body"))
        head = selected(calculator.resolve(body_part="head"))
        self.assertAlmostEqual(body.damage.direct_dph, 8.111946657804877)
        self.assertAlmostEqual(head.damage.direct_dph, 24.33583997341463)
        self.assertAlmostEqual(body.damage.total_dps, 71.03451583153777)

    def test_health_shield_overguard_and_all_target_zones(self):
        target = Enemy(stats=EnemyStats(health=100, shields=100, overguard=100), body_parts={"body": BodyPart("normal", 1), "head": BodyPart("weak_point", 3), "shell": BodyPart("resistant", 0.5)})
        weapon = Primary(name="Pools", attacks=[Attack("shot", stats=AttackStats(damage=Dist(impact=100)))], reload_time=1)
        body = Calculator(weapon, target).resolve(body_part="body").aggregate.damage
        head = Calculator(weapon, target).resolve(body_part="head").aggregate.damage
        shell = Calculator(weapon, target).resolve(body_part="shell").aggregate.damage
        self.assertAlmostEqual(body.direct_dph, 100 * (1 + 0.5 + 1) / 3)
        self.assertAlmostEqual(head.direct_dph, body.direct_dph * 3)
        self.assertAlmostEqual(shell.direct_dph, body.direct_dph * 0.5)

    def test_evolution_base_stats_and_form_condition(self):
        weapon = arsenal.primary.get("Braton")
        evolutions = [perk(weapon, 2, "Daring Reverie Increase Damage by +24 (Braton) / +28 (MK1) / +4 (Prime) / +12 (Vandal). With Channeled Ability active"), perk(weapon, 3, "Mercenary Chamber"), perk(weapon, 4, "Critical Parallel")]
        calculation = Calculator(weapon, build=Build(perks=evolutions)).resolve(attack="incarnon_form")
        result = selected(calculation)
        self.assertAlmostEqual(result.effective.damage.total, 104)
        self.assertAlmostEqual(result.effective.crit_chance, 0.46688995215311)
        self.assertAlmostEqual(result.effective.crit_damage, 3.4)
        self.assertAlmostEqual(result.effective.magazine_capacity, 200)
        self.assertAlmostEqual(calculation.aggregate.damage.total_dps, 2556.784720408416)

    def test_equipped_dependencies_are_case_insensitive(self):
        weapon = arsenal.melee.get("Bo Prime")
        pressure_only = selected(Calculator(weapon, build=build("Sacrificial Pressure")).resolve()).effective.damage.total
        paired = selected(Calculator(weapon, build=build("Sacrificial Pressure", "Sacrificial Steel")).resolve())
        bare = selected(Calculator(weapon).resolve())
        self.assertGreater(paired.effective.damage.total, pressure_only)
        self.assertGreater(paired.effective.crit_chance, bare.effective.crit_chance)

    def test_battery_reload_cycle_uses_capacity_and_recharge_rate(self):
        result = selected(Calculator(arsenal.secondary.get("Cycron")).resolve())
        self.assertAlmostEqual(result.effective.reload_time, 4)
        self.assertAlmostEqual(result.timing.attack_rate, 7.559055118110237)
        self.assertAlmostEqual(result.damage.total_dps, 254.06533493275685)

    def test_non_crit_family_uses_event_chance_without_changing_effective_damage(self):
        weapon = arsenal.secondary.get("Laetum")
        result = selected(Calculator(weapon, build=Build(perks=[perk(weapon, 5, "Devouring Attrition")])).resolve())
        self.assertAlmostEqual(result.effective.damage.total, 160)
        self.assertAlmostEqual(result.damage.direct_dph, 1450.24)
        self.assertAlmostEqual(result.damage.dot_dph, 402.006528)
        self.assertAlmostEqual(result.damage.total_dps, 3472.9622400000003)

    def test_not_continuous_condition_prevents_last_shot_overlay(self):
        weapon = arsenal.primary.get("Amprex")
        bare = selected(Calculator(weapon).resolve()).damage.direct_dph
        synth = selected(Calculator(weapon, build=build("Synth Charge")).resolve())
        self.assertAlmostEqual(synth.damage.direct_dph, bare)
        self.assertEqual(synth.damage.first_shot_damage_multiplier, 1)

    def test_synth_charge_requires_a_base_magazine_of_five(self):
        weapon = arsenal.secondary.get("Knell")
        bare = selected(Calculator(weapon).resolve()).damage.direct_dph
        synth = selected(Calculator(weapon, build=build("Synth Charge")).resolve()).damage.direct_dph
        self.assertAlmostEqual(synth, bare)

    def test_synth_charge_does_not_apply_to_incarnon_form(self):
        weapon = arsenal.secondary.get("Laetum")
        bare = selected(Calculator(weapon).resolve(attack="incarnon_form")).damage.direct_dph
        synth = selected(Calculator(weapon, build=build("Synth Charge")).resolve(attack="incarnon_form")).damage.direct_dph
        self.assertAlmostEqual(synth, bare)

    def test_bow_fire_rate_effect_is_an_additional_application(self):
        speed_trigger = build("Speed Trigger")
        bow = arsenal.primary.get("Paris")
        rifle = arsenal.primary.get("Braton")
        bare_bow_rate = selected(Calculator(bow).resolve()).effective.fire_rate
        bare_rifle_rate = selected(Calculator(rifle).resolve()).effective.fire_rate
        bow_rate = selected(Calculator(bow, build=speed_trigger).resolve()).effective.fire_rate
        rifle_rate = selected(Calculator(rifle, build=speed_trigger).resolve()).effective.fire_rate
        self.assertAlmostEqual(bow_rate / bare_bow_rate, 2.2)
        self.assertAlmostEqual(rifle_rate / bare_rifle_rate, 1.6)


if __name__ == "__main__": unittest.main()
