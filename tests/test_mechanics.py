import unittest
import warnings

from warframe_damage_calculator import Attack, AttackStats, BodyPart, Calculator, Dist, Enemy, EnemyStats, Loadout, Primary, arsenal


def perk(weapon, tier, choice):
    return weapon.perk_choices[tier][choice]


def loadout(*names, evolutions=()):
    return Loadout(upgrades=[arsenal.upgrade.get(name) for name in names], evolutions=evolutions)


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
        weapon = arsenal.weapon.get("Braton")
        result = selected(Calculator(weapon, loadout=loadout("Serration", "Split Chamber", "Point Strike", "Vital Sense", "Hunter Munitions")).calculate())
        self.assertAlmostEqual(result.effective.damage.total, 63.6)
        self.assertAlmostEqual(result.effective.crit_chance, 0.3722579268292683)
        self.assertAlmostEqual(result.effective.crit_damage, 3.52)
        self.assertAlmostEqual(result.effective.multishot, 1.9)
        self.assertAlmostEqual(result.average.direct_dph, 234.19879265268293)
        self.assertAlmostEqual(result.average.dot_dph, 109.7888138116019)
        self.assertAlmostEqual(result.average.total_dps, 2202.3596755335307)

    def test_melee_combo_status_duplicate_and_doughty(self):
        weapon = arsenal.weapon.get("Bo Prime")
        result = selected(Calculator(weapon, loadout=loadout("Condition Overload", "Blood Rush", "Weeping Wounds", "Melee Duplicate", "Melee Doughty")).calculate(state={"combo": 12}))
        self.assertAlmostEqual(result.effective.damage.total, 457.6)
        self.assertAlmostEqual(result.effective.crit_chance, 1.4886961152000002)
        self.assertAlmostEqual(result.effective.status_chance, 1.856)
        self.assertAlmostEqual(result.effective.crit_damage, 4.5)
        self.assertAlmostEqual(result.average.direct_dph, 4569.768282551748)
        self.assertAlmostEqual(result.average.total_dps, 4935.349745155888)

    def test_enervate_reset_expectation_and_encumber_random_proc(self):
        enervate = selected(Calculator(arsenal.weapon.get("Laetum"), loadout=loadout("Secondary Enervate")).calculate())
        self.assertGreater(enervate.average.secondary_enervate_bonus, 0)
        self.assertAlmostEqual(enervate.average.direct_dph, 378.6766179484155)
        self.assertAlmostEqual(enervate.average.total_dps, 906.835830831968)
        encumber = selected(Calculator(arsenal.weapon.get("Lato"), loadout=loadout("Secondary Encumber")).calculate())
        self.assertAlmostEqual(encumber.average.dot_dph, 3.5399275201480167)

    def test_magazine_position_effects_use_shot_class_mixture(self):
        charged = selected(Calculator(arsenal.weapon.get("Braton"), loadout=loadout("Charged Chamber")).calculate())
        self.assertAlmostEqual(charged.average.first_shot_damage_multiplier, 1.008888888888889)
        self.assertAlmostEqual(charged.average.direct_dph, 26.5092002601626)
        synth = selected(Calculator(arsenal.weapon.get("Lato"), loadout=loadout("Synth Charge")).calculate())
        self.assertAlmostEqual(synth.average.direct_dph, 49.555459459459456)

    def test_incarnon_form_condition_and_multishot_ammo_mechanics(self):
        weapon = arsenal.weapon.get("Braton")
        calculation = Calculator(weapon, loadout=Loadout(evolutions=[perk(weapon, 2, 2)])).calculate(attack="incarnon_form")
        result = selected(calculation)
        self.assertAlmostEqual(result.effective.multishot, 1.2)
        self.assertAlmostEqual(result.effective.ammo_cost, 1.2)
        self.assertAlmostEqual(result.effective.damage.total, 70.4)
        self.assertAlmostEqual(calculation.aggregate.average.total_dps, 1539.4027259436357)

    def test_target_pool_armor_status_and_bodypart_model(self):
        target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
        calculator = Calculator(arsenal.weapon.get("Braton"), target, loadout("Serration"))
        body = selected(calculator.calculate(bodypart="body"))
        head = selected(calculator.calculate(bodypart="head"))
        self.assertAlmostEqual(body.average.direct_dph, 8.111946657804877)
        self.assertAlmostEqual(head.average.direct_dph, 24.33583997341463)
        self.assertAlmostEqual(body.average.total_dps, 71.03451583153777)

    def test_health_shield_overguard_and_all_target_zones(self):
        target = Enemy(stats=EnemyStats(health=100, shields=100, overguard=100), bodyparts={"body": BodyPart("normal", 1), "head": BodyPart("weakpoint", 3), "shell": BodyPart("resistant", 0.5)})
        weapon = Primary(name="Pools", attacks=[Attack("shot", stats=AttackStats(damage=Dist(impact=100)))], reload_time=1)
        body = Calculator(weapon, target).calculate(bodypart="body").aggregate.average
        head = Calculator(weapon, target).calculate(bodypart="head").aggregate.average
        shell = Calculator(weapon, target).calculate(bodypart="shell").aggregate.average
        self.assertAlmostEqual(body.direct_dph, 100 * (1 + 0.5 + 1) / 3)
        self.assertAlmostEqual(head.direct_dph, body.direct_dph * 3)
        self.assertAlmostEqual(shell.direct_dph, body.direct_dph * 0.5)

    def test_evolution_base_stats_and_form_condition(self):
        weapon = arsenal.weapon.get("Braton")
        evolutions = [perk(weapon, 2, 1), perk(weapon, 3, 1), perk(weapon, 4, 1)]
        calculation = Calculator(weapon, loadout=Loadout(evolutions=evolutions)).calculate(attack="incarnon_form")
        result = selected(calculation)
        self.assertAlmostEqual(result.effective.damage.total, 104)
        self.assertAlmostEqual(result.effective.crit_chance, 0.46688995215311)
        self.assertAlmostEqual(result.effective.crit_damage, 3.4)
        self.assertAlmostEqual(result.effective.magazine_capacity, 200)
        self.assertAlmostEqual(calculation.aggregate.average.total_dps, 2556.784720408416)

    def test_equipped_dependencies_are_case_insensitive(self):
        weapon = arsenal.weapon.get("Bo Prime")
        pressure_only = selected(Calculator(weapon, loadout=loadout("Sacrificial Pressure")).calculate()).effective.damage.total
        paired = selected(Calculator(weapon, loadout=loadout("Sacrificial Pressure", "Sacrificial Steel")).calculate())
        bare = selected(Calculator(weapon).calculate())
        self.assertGreater(paired.effective.damage.total, pressure_only)
        self.assertGreater(paired.effective.crit_chance, bare.effective.crit_chance)

    def test_battery_reload_cycle_uses_capacity_and_recharge_rate(self):
        result = selected(Calculator(arsenal.weapon.get("Cycron")).calculate())
        self.assertAlmostEqual(result.effective.reload_time, 4)
        self.assertAlmostEqual(result.average.attack_rate, 7.559055118110237)
        self.assertAlmostEqual(result.average.total_dps, 254.06533493275685)

    def test_non_crit_family_uses_event_chance_without_changing_effective_damage(self):
        weapon = arsenal.weapon.get("Laetum")
        result = selected(Calculator(weapon, loadout=Loadout(evolutions=[perk(weapon, 5, 1)])).calculate())
        self.assertAlmostEqual(result.effective.damage.total, 160)
        self.assertAlmostEqual(result.average.direct_dph, 1450.24)
        self.assertAlmostEqual(result.average.dot_dph, 402.006528)
        self.assertAlmostEqual(result.average.total_dps, 3472.9622400000003)

    def test_not_continuous_condition_prevents_last_shot_overlay(self):
        weapon = arsenal.weapon.get("Amprex")
        bare = selected(Calculator(weapon).calculate()).average.direct_dph
        synth = selected(Calculator(weapon, loadout=loadout("Synth Charge")).calculate())
        self.assertAlmostEqual(synth.average.direct_dph, bare)
        self.assertEqual(synth.average.first_shot_damage_multiplier, 1)

    def test_synth_charge_requires_a_base_magazine_of_five(self):
        weapon = arsenal.weapon.get("Knell")
        bare = selected(Calculator(weapon).calculate()).average.direct_dph
        synth = selected(Calculator(weapon, loadout=loadout("Synth Charge")).calculate()).average.direct_dph
        self.assertAlmostEqual(synth, bare)

    def test_synth_charge_does_not_apply_to_incarnon_form(self):
        weapon = arsenal.weapon.get("Laetum")
        bare = selected(Calculator(weapon).calculate(attack="incarnon_form")).average.direct_dph
        synth = selected(Calculator(weapon, loadout=loadout("Synth Charge")).calculate(attack="incarnon_form")).average.direct_dph
        self.assertAlmostEqual(synth, bare)

    def test_bow_fire_rate_effect_is_an_additional_application(self):
        speed_trigger = loadout("Speed Trigger")
        bow = arsenal.weapon.get("Paris")
        rifle = arsenal.weapon.get("Braton")
        bare_bow_rate = selected(Calculator(bow).calculate()).effective.fire_rate
        bare_rifle_rate = selected(Calculator(rifle).calculate()).effective.fire_rate
        bow_rate = selected(Calculator(bow, loadout=speed_trigger).calculate()).effective.fire_rate
        rifle_rate = selected(Calculator(rifle, loadout=speed_trigger).calculate()).effective.fire_rate
        self.assertAlmostEqual(bow_rate / bare_bow_rate, 2.2)
        self.assertAlmostEqual(rifle_rate / bare_rifle_rate, 1.6)


if __name__ == "__main__": unittest.main()
