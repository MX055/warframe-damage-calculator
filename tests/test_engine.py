import unittest
from math import pi

from warframe_damage_calculator import Attack, AttackStats, BodyPart, Build, Dist, Effect, Enemy, EnemyStats, Primary, Upgrade, UpgradeStats, arsenal


def weapon(*, damage=None, children=None, status=0, crit=0, fire_rate=1, multishot=1, aoe=False, punch_through=0, falloff=None):
    attacks = [Attack(name="shot", aoe=aoe, children=list(children or []), stats=AttackStats(damage=damage or Dist(impact=100), status_chance=status, crit_chance=crit, crit_damage=2, fire_rate=fire_rate, multishot=multishot, punch_through=punch_through, falloff=falloff or {}))]
    if children: attacks.append(Attack(name="blast", stats=AttackStats(damage=Dist(blast=100), fire_rate=fire_rate)))
    return Primary(name="Test", subtype="rifle", attacks=attacks, magazine_size=100)


class EngineTests(unittest.TestCase):
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

    def test_internal_bleeding_uses_an_additional_low_fire_rate_effect(self):
        upgrade = arsenal.upgrade.get("Internal Bleeding")
        low_rate = weapon(status=1, fire_rate=2).configure(upgrade).results.main.average.flat_dotph
        high_rate = weapon(status=1, fire_rate=3).configure(upgrade).results.main.average.flat_dotph
        self.assertAlmostEqual(low_rate, high_rate * 2)

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

    def test_target_hit_zones_and_armor(self):
        target = Enemy(name="Armored", stats=EnemyStats(health=100, armor=300), bodyparts={"body": BodyPart("normal", 1), "head": BodyPart("weakpoint", 2)})
        result = weapon().configure(target=target).results.main
        self.assertEqual(result.average.flat_dph, 70)
        self.assertEqual(result.average.flat_weakpoint_dph, 140)

    def test_fire_rate_and_multishot_locks(self):
        lock = Upgrade(name="Lock", stats=UpgradeStats(fire_rate_lock=Effect(properties={"value": True}), multishot_lock=Effect(properties={"value": True}), fire_rate=Effect(properties={"value": 2}), multishot=Effect(properties={"value": 2})))
        result = weapon(fire_rate=2, multishot=2).configure(lock).results.main
        self.assertEqual(result.effective.fire_rate, 2)
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
        self.assertAlmostEqual(result.density.damage_density_per_second, 100 * expected_mass * result.average.fire_rate)

    def test_punch_through_density_is_bounded_by_actual_punch_through(self):
        falloff = {"start_range": 2, "end_range": 4, "final_multiplier": 0.5}
        shallow = weapon(punch_through=1, falloff=falloff).results.main
        partial = weapon(punch_through=3, falloff=falloff).results.main
        excess = weapon(punch_through=10, falloff=falloff).results.main
        expected_partial = 3 - (1 - 0.5) * (3 - 2) ** 2 / (2 * (4 - 2))
        expected_full = (1 - 0.5) / 2 * 2 + (1 + 0.5) / 2 * 4
        self.assertEqual(shallow.density.damage_mass, 1)
        self.assertAlmostEqual(partial.density.damage_mass, expected_partial)
        self.assertAlmostEqual(excess.density.damage_mass, expected_full)
        self.assertAlmostEqual(partial.density.damage_density, 100 * expected_partial)
        self.assertEqual(partial.average.falloff_multiplier, 0.875)
        self.assertEqual(partial.final.flat_dph, 87.5)

    def test_punch_through_upgrades_add_meters_to_the_density_bound(self):
        upgrade = Upgrade(name="Punch Through", stats=UpgradeStats(punch_through=Effect(properties={"value": 3})))
        result = weapon(falloff={"start_range": 2, "end_range": 4, "final_multiplier": 0.5}).configure(upgrade).results.main
        expected_mass = 3 - (1 - 0.5) * (3 - 2) ** 2 / (2 * (4 - 2))
        self.assertEqual(result.effective.punch_through, 3)
        self.assertAlmostEqual(result.density.damage_mass, expected_mass)

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


if __name__ == "__main__": unittest.main()
