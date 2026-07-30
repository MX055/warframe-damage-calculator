import unittest
from math import pi
from unittest.mock import patch

from warframe_damage_calculator import Attack, AttackStats, BodyPart, Build, Dist, Effect, Enemy, EnemyStats, Melee, Primary, Secondary, Upgrade, UpgradeStats, arsenal
from warframe_damage_calculator.engine import contributions
from warframe_damage_calculator.engine.formulas import cumulative_falloff, punch_through_falloff_multiplier
from warframe_damage_calculator.engine.status import StatusModel, attack_proc_chance


def weapon(*, damage=None, children=None, status=0, crit=0, fire_rate=1, multishot=1, aoe=False, punch_through=0, falloff=None, max_range=None):
    attacks = [Attack(name="shot", aoe=aoe, children=list(children or []), stats=AttackStats(damage=damage or Dist(impact=100), status_chance=status, crit_chance=crit, crit_damage=2, fire_rate=fire_rate, multishot=multishot, punch_through=punch_through, falloff=falloff or {}, max_range=max_range))]
    if children: attacks.append(Attack(name="blast", stats=AttackStats(damage=Dist(blast=100), fire_rate=fire_rate)))
    return Primary(name="Test", subtype="rifle", attacks=attacks, magazine_size=100)


class EngineTests(unittest.TestCase):
    def test_fractional_attempts_are_a_discrete_extra_hit(self):
        self.assertEqual(attack_proc_chance(0.5, 1.5), 0.625)

    def test_sustained_stacks_use_continuous_proc_rates(self):
        one = StatusModel(Dist(heat=100), Dist(), 1, 1, 0.2, 5)
        two = StatusModel(Dist(heat=100), Dist(), 1, 1, 0.4, 5)
        self.assertEqual(one.expected_stacks("heat", 10), 1)
        self.assertEqual(two.expected_stacks("heat", 10), 2)
        self.assertEqual(one.expected_active_stacks("heat"), 1)
        self.assertEqual(one.expected_active_types(), 1)
        rare = StatusModel(Dist(heat=100), Dist(), 0.1, 1, 0.4, 5)
        self.assertLess(rare.probability_active("heat"), rare.expected_active_types())

    def test_different_families_multiply(self):
        build = Build(
            Upgrade(name="First", stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1, "family": "first"}))),
            Upgrade(name="Second", stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1, "family": "second"}))),
        )
        result = weapon().configure(build).results.main
        self.assertEqual(result.effective.damage.total, 400)

    def test_condition_overload_is_engine_managed(self):
        condition_overload = Upgrade(name="CO", stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1, "family": "unique_status"}, automatic={"with": "unique_status_count"})))
        inactive = weapon(damage=Dist(impact=100), status=0).configure(condition_overload)
        active = weapon(damage=Dist(heat=100), status=1, fire_rate=10).configure(condition_overload)
        self.assertEqual(inactive.results.main.effective.damage.total, 100)
        self.assertGreater(active.results.main.effective.damage.total, 100)

    def test_hunter_munitions_adds_expected_slash_dot(self):
        hunter = Upgrade(name="Hunter", stats=UpgradeStats(slash_proc=Effect(properties={"value": 1}, automatic={"on": "critical_hit", "chance": 0.3})))
        bare = weapon(crit=1)
        modded = weapon(crit=1).configure(hunter)
        self.assertGreater(modded.results.main.average.flat_dotph, bare.results.main.average.flat_dotph)

    def test_dot_formulas_use_modded_base_damage(self):
        natural = weapon(damage=Dist(impact=100, slash=100), status=1).results.main
        forced = Primary(name="Forced", subtype="rifle", magazine_size=100, attacks=[Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), forced_procs=Dist(slash=1), fire_rate=1))]).results.main
        heat_mod = Upgrade(name="Heat", stats=UpgradeStats(heat=Effect(properties={"value": 1})))
        elemental = weapon(damage=Dist(impact=100), status=1).configure(heat_mod).results.main
        self.assertEqual(natural.average.flat_dotph, 210)
        self.assertEqual(forced.average.flat_dotph, 210)
        self.assertEqual(elemental.average.flat_dotph, 300)
        for kind in ("heat", "toxin", "electricity", "gas"):
            natural_element = weapon(damage=Dist({kind: 100}), status=1).results.main
            forced_element = Primary(name="Forced", subtype="rifle", magazine_size=100, attacks=[Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), forced_procs=Dist({kind: 1}), fire_rate=1))]).results.main
            self.assertEqual(natural_element.average.flat_dotph, 300)
            self.assertEqual(forced_element.average.flat_dotph, 300)

    def test_internal_bleeding_uses_an_additional_low_fire_rate_effect(self):
        upgrade = arsenal.upgrade.get("Internal Bleeding")
        low_rate = weapon(status=1, fire_rate=2).configure(upgrade).results.main.average.flat_dotph
        high_rate = weapon(status=1, fire_rate=3).configure(upgrade).results.main.average.flat_dotph
        self.assertAlmostEqual(low_rate, high_rate * 2)

    def test_random_procs_feed_every_status_consumer(self):
        attack = Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), status_chance=1, fire_rate=1))
        encumber = Upgrade(name="Encumber", stats=UpgradeStats(random_proc=Effect(properties={"value": 1}, automatic={"on": "any_status_proc", "chance": 0.24})))
        heat_bonus = Upgrade(name="Heat consumer", stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1}, automatic={"when": "heat_status_proc", "stacks": 40, "for": 10})))
        proc_result = Secondary(name="Proc", subtype="pistol", attacks=[attack], magazine_size=100).configure(encumber).results.main
        consumer_result = Secondary(name="Consumer", subtype="pistol", attacks=[attack], magazine_size=100).configure(Build(encumber, heat_bonus)).results.main
        self.assertAlmostEqual(proc_result.average.procs_per_shot, 1.24)
        self.assertGreater(proc_result.average.flat_dotph, 0)
        for kind in ("viral", "magnetic", "corrosive", "heat"): self.assertGreater(proc_result.status_effects[kind], 0)
        self.assertGreater(consumer_result.effective.damage.total, proc_result.effective.damage.total)

    def test_forced_procs_trigger_capped_random_procs(self):
        attack = Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), forced_procs=Dist(slash=1), status_chance=0, multishot=2))
        encumber = Upgrade(name="Encumber", stats=UpgradeStats(random_proc=Effect(properties={"value": 1}, automatic={"on": "any_status_proc", "chance": 0.24})))
        result = Secondary(name="Forced", subtype="pistol", attacks=[attack], magazine_size=100).configure(encumber).results.main
        expected_random_proc = 1 - (1 - 0.24) ** 2
        self.assertAlmostEqual(result.average.procs_per_shot, 2 + expected_random_proc)

    def test_random_impact_procs_feed_hemorrhage(self):
        attack = Attack(name="shot", stats=AttackStats(damage=Dist(heat=100), status_chance=1, fire_rate=1))
        encumber = Upgrade(name="Encumber", stats=UpgradeStats(random_proc=Effect(properties={"value": 1}, automatic={"on": "any_status_proc", "chance": 0.24})))
        hemorrhage = Upgrade(name="Hemorrhage", stats=UpgradeStats(slash_proc=Effect(properties={"value": 1}, automatic={"on": "impact_status_proc", "chance": 0.35})))
        encumber_only = Secondary(name="Encumber", subtype="pistol", attacks=[attack], magazine_size=100).configure(encumber).results.main
        chained = Secondary(name="Chained", subtype="pistol", attacks=[attack], magazine_size=100).configure(Build(encumber, hemorrhage)).results.main
        self.assertGreater(chained.average.procs_per_shot, encumber_only.average.procs_per_shot)
        self.assertGreater(chained.average.flat_dotph, encumber_only.average.flat_dotph)

    def test_supported_special_status_effects_use_the_shared_proc_model(self):
        bleeding = weapon(damage=Dist(impact=100), status=1).configure(Upgrade(name="Bleed", stats=UpgradeStats(bleed_on_impact=Effect(properties={"value": 0.4})))).results.main
        self.assertAlmostEqual(bleeding.average.procs_per_shot, 1.4)

    def test_cold_puncture_blast_void_and_status_vulnerability(self):
        puncture = weapon(damage=Dist(puncture=100), status=1).results.main
        cold = weapon(damage=Dist(cold=100), status=1, crit=1).results.main
        blast = weapon(damage=Dist(blast=100), status=1).results.main
        void = Primary(name="Void", subtype="rifle", magazine_size=100, attacks=[Attack(name="shot", stats=AttackStats(damage=Dist(impact=100), forced_procs=Dist(void=1), fire_rate=1))]).results.main
        vulnerable = weapon(status=1).configure(Upgrade(name="Vulnerability", stats=UpgradeStats(status_vulnerability=Effect(properties={"value": 0.5})))).results.main
        self.assertEqual(puncture.effective.crit_chance, 0.25)
        self.assertGreater(cold.effective.crit_damage, 2)
        self.assertEqual(blast.average.flat_dotph, 30)
        self.assertEqual(void.average.procs_per_shot, 1)
        self.assertEqual(vulnerable.effective.status_chance, 1.5)

    def test_vigilante_upgrades_existing_crits_without_creating_crits(self):
        vigilante = arsenal.upgrade.get("Vigilante Supplies")
        non_critical = weapon(crit=0).configure(vigilante).results.main
        critical = weapon(crit=0.2).configure(vigilante).results.main
        self.assertEqual(non_critical.average.crit_tier_bonus, 0)
        self.assertEqual(non_critical.average.flat_dph, 100)
        self.assertAlmostEqual(critical.effective.crit_chance, 0.2)
        self.assertAlmostEqual(critical.average.crit_tier_bonus, 0.01)
        self.assertAlmostEqual(critical.average.flat_dph, 121)

    def test_attack_children_fold_once(self):
        result = weapon(children=["blast"]).results.main
        self.assertEqual(result.average.total_dph, 100)
        self.assertEqual(result.final.total_dph, 200)

    def test_shared_attack_descendants_are_not_folded_twice(self):
        attacks = [
            Attack(name="root", children=["left", "right"], stats=AttackStats(damage=Dist(impact=100), fire_rate=1)),
            Attack(name="left", children=["shared"], stats=AttackStats(damage=Dist(impact=100), fire_rate=1)),
            Attack(name="right", children=["shared"], stats=AttackStats(damage=Dist(impact=100), fire_rate=1)),
            Attack(name="shared", stats=AttackStats(damage=Dist(impact=100), fire_rate=1)),
        ]
        result = Primary(name="Tree", subtype="rifle", attacks=attacks, magazine_size=100).results.main
        self.assertEqual(result.final.total_dph, 400)

    def test_parent_and_child_share_sustained_status_and_encumber_cap(self):
        attacks = [
            Attack(name="shot", children=["blast"], stats=AttackStats(damage=Dist(impact=100), status_chance=1, fire_rate=1)),
            Attack(name="blast", stats=AttackStats(damage=Dist(heat=100), status_chance=1, fire_rate=1)),
        ]
        bare = Secondary(name="Composite", subtype="pistol", attacks=attacks, magazine_size=100)
        encumbered = bare.copy().configure(arsenal.upgrade.get("Secondary Encumber")).results.main
        condition_overload = Upgrade(name="CO", stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1, "family": "unique_status"}, automatic={"with": "unique_status_count"})))
        overloaded = bare.copy().configure(condition_overload).results.main
        self.assertEqual(bare.results.main.average.procs_per_shot, 2)
        self.assertEqual(bare.results.main.status_effects["heat"], 1)
        self.assertAlmostEqual(encumbered.average.procs_per_shot, 2 + 1 - (1 - 0.24) ** 2)
        self.assertEqual(overloaded.effective.damage.total, 300)

    def test_siblings_share_statuses_from_deeper_descendants(self):
        attacks = [
            Attack(name="root", children=["left", "right"], stats=AttackStats(damage=Dist(impact=100), fire_rate=1)),
            Attack(name="left", children=["grandchild"], stats=AttackStats(damage=Dist(impact=100), fire_rate=1)),
            Attack(name="right", stats=AttackStats(damage=Dist(toxin=100), status_chance=1, fire_rate=1)),
            Attack(name="grandchild", stats=AttackStats(damage=Dist(heat=100), status_chance=1, fire_rate=1)),
        ]
        consumers = Build(
            Upgrade(name="Heat consumer", stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1, "family": "heat"}, automatic={"when": "heat_status_proc"}))),
            Upgrade(name="Toxin consumer", stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1, "family": "toxin"}, automatic={"when": "toxin_status_proc"}))),
        )
        shared = Primary(name="Tree", subtype="rifle", attacks=attacks, magazine_size=100).configure(consumers)
        isolated_right = weapon(damage=Dist(toxin=100), status=1).configure(consumers).results.main
        isolated_grandchild = weapon(damage=Dist(heat=100), status=1).configure(consumers).results.main
        self.assertGreater(shared.results.attacks["right"].effective.damage.total, isolated_right.effective.damage.total)
        self.assertGreater(shared.results.attacks["grandchild"].effective.damage.total, isolated_grandchild.effective.damage.total)
        self.assertAlmostEqual(shared.results.main.average.procs_per_shot, 2)

    def test_target_hit_zones_and_armor(self):
        target = Enemy(name="Armored", stats=EnemyStats(health=100, armor=300), bodyparts={"body": BodyPart("normal", 1), "head": BodyPart("weakpoint", 2)})
        result = weapon().configure(target=target).results.main
        self.assertEqual(result.average.flat_dph, 70)
        self.assertEqual(result.average.flat_weakpoint_dph, 140)

    def test_fire_rate_and_multishot_locks(self):
        lock = Upgrade(name="Lock", stats=UpgradeStats(fire_rate_lock=Effect(properties={"value": True}), multishot_lock=Effect(properties={"value": True}), fire_rate=Effect(properties={"value": 2}), multishot=Effect(properties={"value": 2})))
        result = weapon(fire_rate=2, multishot=2).configure(lock).results.main
        self.assertEqual(result.effective.instantaneous_fire_rate, 2)
        self.assertEqual(result.effective.multishot, 2)

    def test_aoe_density_uses_spherical_damage_mass_and_average_falloff(self):
        result = weapon(aoe=True, falloff={"start_range": 2, "end_range": 4, "final_multiplier": 0.5}).results.main
        expected_mass = 4 / 3 * pi * 4 ** 3 - pi / 3 * (1 - 0.5) * (4 - 2) * (3 * 4 ** 2 + 2 * 4 * 2 + 2 ** 2)
        expected_multiplier = (1 - 0.5) / 2 * 2 / 4 + (1 + 0.5) / 2
        self.assertAlmostEqual(result.average.falloff_multiplier, expected_multiplier)
        self.assertAlmostEqual(result.density.damage_mass, expected_mass)
        self.assertAlmostEqual(result.average.flat_dph, 100 * expected_multiplier)
        self.assertAlmostEqual(result.final.flat_dph, 100 * expected_multiplier)
        self.assertAlmostEqual(result.density.damage_density, 100 * expected_mass)
        self.assertAlmostEqual(result.density.damage_density_per_second, 100 * expected_mass * result.average.sustained_fire_rate)

    def test_punch_through_density_is_bounded_by_actual_punch_through(self):
        falloff = {"start_range": 2, "end_range": 4, "final_multiplier": 0.5}
        shallow = weapon(punch_through=1, falloff=falloff).results.main
        partial = weapon(punch_through=3, falloff=falloff).results.main
        excess = weapon(punch_through=10, falloff=falloff).results.main
        expected_shallow = 4 * punch_through_falloff_multiplier(2, 4, 4, 0.5, 1)
        expected_partial = 4 * punch_through_falloff_multiplier(2, 4, 4, 0.5, 3)
        expected_full = 4 * punch_through_falloff_multiplier(2, 4, 4, 0.5, 10)
        self.assertAlmostEqual(shallow.density.damage_mass, expected_shallow)
        self.assertAlmostEqual(partial.density.damage_mass, expected_partial)
        self.assertAlmostEqual(excess.density.damage_mass, expected_full)
        self.assertAlmostEqual(partial.density.damage_density, 100 * expected_partial)
        self.assertEqual(partial.average.falloff_multiplier, 0.875)
        self.assertEqual(partial.final.flat_dph, 87.5)

    def test_punch_through_upgrades_add_meters_to_the_density_bound(self):
        upgrade = Upgrade(name="Punch Through", stats=UpgradeStats(punch_through=Effect(properties={"value": 3})))
        result = weapon(falloff={"start_range": 2, "end_range": 4, "final_multiplier": 0.5}).configure(upgrade).results.main
        expected_mass = 4 * punch_through_falloff_multiplier(2, 4, 4, 0.5, 3)
        self.assertEqual(result.effective.punch_through, 3)
        self.assertAlmostEqual(result.density.damage_mass, expected_mass)

    def test_sliding_punch_through_density_and_range_scaling(self):
        self.assertEqual(cumulative_falloff(3, 3, 6, 0), 3)
        self.assertEqual(cumulative_falloff(4.5, 3, 6, 0), 4.125)
        self.assertEqual(cumulative_falloff(6, 3, 6, 0), 4.5)
        self.assertEqual(cumulative_falloff(9, 3, 6, 0), 4.5)
        self.assertEqual(punch_through_falloff_multiplier(3, 6, 6, 0, 3), 0.75)
        supplied = weapon(punch_through=3, falloff={"start_range": 3, "end_range": 6, "final_multiplier": 0}).results.main
        no_falloff = weapon(punch_through=3, max_range=10).results.main
        unbounded = weapon(punch_through=3).results.main
        speed = Upgrade(name="Speed", stats=UpgradeStats(projectile_speed=Effect(properties={"value": 0.5})))
        scaled = weapon(punch_through=3, falloff={"start_range": 3, "end_range": 6, "final_multiplier": 0}, max_range=9).configure(speed).results.main
        self.assertEqual(supplied.density.falloff_multiplier, 0.75)
        self.assertEqual(supplied.density.damage_mass, 4.5)
        self.assertEqual(no_falloff.density.falloff_multiplier, 1)
        self.assertEqual(no_falloff.density.damage_mass, 10)
        self.assertIsNone(unbounded.density.damage_mass)
        self.assertEqual(scaled.effective.end_range, 9)
        self.assertEqual(scaled.effective.max_range, 13.5)

    def test_malformed_spatial_ranges_are_rejected(self):
        with self.assertRaises(ValueError): AttackStats(punch_through=-1)
        with self.assertRaises(ValueError): AttackStats(max_range=5, falloff={"start_range": 3, "end_range": 6, "final_multiplier": 0.5})
        with self.assertRaises(ValueError): AttackStats(falloff={"start_range": 0, "end_range": 5, "final_multiplier": 1.1})

    def test_zero_final_falloff_multiplier_is_preserved(self):
        result = weapon(falloff={"start_range": 0, "end_range": 4, "final_multiplier": 0}).results.main
        self.assertEqual(result.effective.final_multiplier, 0)
        self.assertEqual(result.average.falloff_multiplier, 0.5)
        self.assertEqual(result.final.flat_dph, 50)

    def test_explosion_radius_scales_aoe_damage_mass(self):
        radius = Upgrade(name="Radius", stats=UpgradeStats(explosion_radius=Effect(properties={"value": 1})))
        bare = weapon(aoe=True, falloff={"start_range": 0, "end_range": 4, "final_multiplier": 1}).results.main
        modded = weapon(aoe=True, falloff={"start_range": 0, "end_range": 4, "final_multiplier": 1}).configure(radius).results.main
        self.assertAlmostEqual(modded.density.damage_mass, bare.density.damage_mass * 8)

    def test_contributions_are_additive_to_total_gain(self):
        configured = weapon().configure(Build(arsenal.upgrade.get("Serration"), arsenal.upgrade.get("Point Strike")))
        values = configured.results.shapley_contributions()
        self.assertAlmostEqual(sum(values.values()), 1)
        self.assertEqual(set(values), {"Serration", "Point Strike"})

    def test_nested_mutations_invalidate_results_on_access(self):
        configured = weapon().configure(Upgrade(name="Conditional", stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1}, manual={"when": "active"}))).set(active=False))
        baseline = configured.results.main.final.total_dps
        configured.build[0].set(active=True)
        upgraded = configured.results.main.final.total_dps
        configured.attacks["shot"].stats.damage = Dist(impact=200)
        mutated_attack = configured.results.main.final.total_dps
        configured.target.stats.armor = 1000
        armored = configured.results.main.final.total_dps
        self.assertGreater(upgraded, baseline)
        self.assertGreater(mutated_attack, upgraded)
        self.assertLess(armored, mutated_attack)

    def test_shapley_calculates_each_coalition_once(self):
        configured = weapon().configure(Build(
            Upgrade(name="Damage", stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1}))),
            Upgrade(name="Critical", stats=UpgradeStats(crit_chance=Effect(properties={"value": 1}))),
            Upgrade(name="Multishot", stats=UpgradeStats(multishot=Effect(properties={"value": 1}))),
        ))
        original = contributions._metric
        evaluations = 0

        def counted(source, upgrades, target):
            nonlocal evaluations
            evaluations += 1
            return original(source, upgrades, target)

        with patch.object(contributions, "_metric", counted):
            configured.results.shapley_contributions()
        self.assertEqual(evaluations, 8)


if __name__ == "__main__": unittest.main()
