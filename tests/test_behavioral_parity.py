import unittest
import warnings

from warframe_damage_calculator import Build, arsenal


class BehavioralParityTests(unittest.TestCase):
    def setUp(self):
        self.warning_context = warnings.catch_warnings()
        self.warning_context.__enter__()
        warnings.simplefilter("ignore")

    def tearDown(self):
        self.warning_context.__exit__(None, None, None)

    def test_ranged_damage_crit_multishot_and_hunter_munitions(self):
        build = Build(*(arsenal.upgrade.get(name) for name in ("Serration", "Split Chamber", "Point Strike", "Vital Sense", "Hunter Munitions")))
        result = arsenal.weapon.get("Braton").configure(build).results.main
        self.assertAlmostEqual(result.effective.damage.total, 63.6)
        self.assertAlmostEqual(result.effective.crit_chance, 0.3722579268292683)
        self.assertAlmostEqual(result.effective.crit_damage, 3.52)
        self.assertAlmostEqual(result.effective.multishot, 1.9)
        self.assertAlmostEqual(result.average.flat_dph, 234.19879265268293)
        self.assertAlmostEqual(result.average.flat_dotph, 109.7888138116019)
        self.assertAlmostEqual(result.final.total_dps, 2202.3596755335307)

    def test_melee_combo_status_duplicate_and_doughty(self):
        names = ("Condition Overload", "Blood Rush", "Weeping Wounds", "Melee Duplicate", "Melee Doughty")
        result = arsenal.weapon.get("Bo Prime").configure(Build(*(arsenal.upgrade.get(name) for name in names))).set(combo=12).results.main
        self.assertAlmostEqual(result.effective.damage.total, 457.6)
        self.assertAlmostEqual(result.effective.crit_chance, 1.4886961152000002)
        self.assertAlmostEqual(result.effective.status_chance, 1.856)
        self.assertAlmostEqual(result.effective.crit_damage, 4.5)
        self.assertAlmostEqual(result.average.flat_dph, 4569.768282551748)
        self.assertAlmostEqual(result.final.total_dps, 4935.349745155888)

    def test_enervate_reset_expectation_and_encumber_random_proc(self):
        enervate = arsenal.weapon.get("Laetum").configure(Build(arsenal.upgrade.get("Secondary Enervate"))).results.main
        self.assertGreater(enervate.average.secondary_enervate_bonus, 0)
        self.assertAlmostEqual(enervate.average.flat_dph, 378.6766179484155)
        self.assertAlmostEqual(enervate.final.total_dps, 906.835830831968)
        encumber = arsenal.weapon.get("Lato").configure(Build(arsenal.upgrade.get("Secondary Encumber"))).results.main
        self.assertAlmostEqual(encumber.average.flat_dotph, 3.5399275201480167)

    def test_magazine_position_effects_use_shot_class_mixture(self):
        charged = arsenal.weapon.get("Braton").configure(Build(arsenal.upgrade.get("Charged Chamber"))).results.main
        self.assertAlmostEqual(charged.average.first_shot_damage_multiplier, 1.008888888888889)
        self.assertAlmostEqual(charged.average.flat_dph, 26.5092002601626)
        synth = arsenal.weapon.get("Lato").configure(Build(arsenal.upgrade.get("Synth Charge"))).results.main
        self.assertAlmostEqual(synth.average.flat_dph, 49.555459459459456)

    def test_incarnon_form_condition_and_multishot_ammo_mechanics(self):
        result = arsenal.weapon.get("Braton").set(attack="incarnon_form", evolutions={2: 2}).results.main
        self.assertAlmostEqual(result.effective.multishot, 1.2)
        self.assertAlmostEqual(result.effective.ammo_cost, 1.2)
        self.assertAlmostEqual(result.effective.damage.total, 70.4)
        self.assertAlmostEqual(result.final.total_dps, 1539.4027259436357)

    def test_target_pool_armor_status_and_bodypart_model(self):
        target = arsenal.enemy.get("Heavy Gunner").set(level=100, steel_path=True)
        result = arsenal.weapon.get("Braton").configure(Build(arsenal.upgrade.get("Serration")), target).results.main
        self.assertAlmostEqual(result.average.flat_dph, 8.111946657804877)
        self.assertAlmostEqual(result.average.flat_weakpoint_dph, 24.33583997341463)
        self.assertAlmostEqual(result.final.total_dps, 71.03451583153777)

    def test_evolution_base_stats_and_form_condition(self):
        result = arsenal.weapon.get("Braton").set(attack="incarnon_form", evolutions={2: 1, 3: 1, 4: 1}).results.main
        self.assertAlmostEqual(result.effective.damage.total, 104)
        self.assertAlmostEqual(result.effective.crit_chance, 0.46688995215311)
        self.assertAlmostEqual(result.effective.crit_damage, 3.4)
        self.assertAlmostEqual(result.effective.magazine_capacity, 200)
        self.assertAlmostEqual(result.final.total_dps, 2556.784720408416)

    def test_equipped_dependencies_are_case_insensitive(self):
        weapon = arsenal.weapon.get("Bo Prime")
        pressure_only = weapon.configure(Build(arsenal.upgrade.get("Sacrificial Pressure"))).results.main.effective.damage.total
        paired = arsenal.weapon.get("Bo Prime").configure(Build(arsenal.upgrade.get("Sacrificial Pressure"), arsenal.upgrade.get("Sacrificial Steel"))).results.main
        self.assertGreater(paired.effective.damage.total, pressure_only)
        self.assertGreater(paired.effective.crit_chance, weapon.results.main.effective.crit_chance)

    def test_battery_reload_cycle_uses_capacity_and_recharge_rate(self):
        result = arsenal.weapon.get("Cycron").results.main
        self.assertAlmostEqual(result.effective.reload_time, 4)
        self.assertAlmostEqual(result.average.sustained_fire_rate, 7.559055118110237)
        self.assertAlmostEqual(result.final.total_dps, 254.06533493275685)

    def test_non_crit_family_uses_event_chance_without_changing_effective_damage(self):
        result = arsenal.weapon.get("Laetum").set(evolutions={5: 1}).results.main
        self.assertAlmostEqual(result.effective.damage.total, 160)
        self.assertAlmostEqual(result.average.flat_dph, 1450.24)
        self.assertAlmostEqual(result.average.flat_dotph, 402.006528)
        self.assertAlmostEqual(result.final.total_dps, 3472.9622400000003)

    def test_not_continuous_condition_prevents_last_shot_overlay(self):
        bare = arsenal.weapon.get("Amprex").results.main.average.flat_dph
        synth = arsenal.weapon.get("Amprex").configure(Build(arsenal.upgrade.get("Synth Charge"))).results.main
        self.assertAlmostEqual(synth.average.flat_dph, bare)
        self.assertEqual(synth.average.first_shot_damage_multiplier, 1)

    def test_synth_charge_requires_a_base_magazine_of_five(self):
        bare = arsenal.weapon.get("Knell").results.main.average.flat_dph
        synth = arsenal.weapon.get("Knell").configure(Build(arsenal.upgrade.get("Synth Charge"))).results.main.average.flat_dph
        self.assertAlmostEqual(synth, bare)

    def test_synth_charge_does_not_apply_to_incarnon_form(self):
        bare = arsenal.weapon.get("Laetum").set(attack="incarnon_form").results.main.average.flat_dph
        synth = arsenal.weapon.get("Laetum").set(attack="incarnon_form").configure(Build(arsenal.upgrade.get("Synth Charge"))).results.main.average.flat_dph
        self.assertAlmostEqual(synth, bare)

    def test_bow_fire_rate_effect_is_an_additional_application(self):
        speed_trigger = arsenal.upgrade.get("Speed Trigger")
        bow = arsenal.weapon.get("Paris")
        rifle = arsenal.weapon.get("Braton")
        bare_bow_rate = bow.results.main.effective.instantaneous_fire_rate
        bare_rifle_rate = rifle.results.main.effective.instantaneous_fire_rate
        bow_rate = bow.configure(speed_trigger).results.main.effective.instantaneous_fire_rate
        rifle_rate = rifle.configure(speed_trigger).results.main.effective.instantaneous_fire_rate
        self.assertAlmostEqual(bow_rate / bare_bow_rate, 2.2)
        self.assertAlmostEqual(rifle_rate / bare_rifle_rate, 1.6)
