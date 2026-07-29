import unittest

from warframe_damage_calculator import Attack, AttackStats, BodyPart, Build, Dist, Effect, Enemy, EnemyStats, Primary, Upgrade, UpgradeStats, arsenal


def weapon(*, damage=None, children=None, status=0, crit=0, fire_rate=1, multishot=1):
    attacks = [Attack(name="shot", children=list(children or []), stats=AttackStats(damage=damage or Dist(impact=100), status_chance=status, crit_chance=crit, crit_damage=2, fire_rate=fire_rate, multishot=multishot))]
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
        condition_overload = Upgrade(name="CO", stats=UpgradeStats(damage_bonus=Effect(properties={"value": 1, "family": "status"}, automatic={"with": "unique_status_count"})))
        inactive = weapon(damage=Dist(impact=100), status=0).configure(condition_overload)
        active = weapon(damage=Dist(heat=100), status=1, fire_rate=10).configure(condition_overload)
        self.assertEqual(inactive.results.main.effective.damage.total, 100)
        self.assertGreater(active.results.main.effective.damage.total, 100)

    def test_hunter_munitions_adds_expected_slash_dot(self):
        hunter = Upgrade(name="Hunter", stats=UpgradeStats(slash_proc=Effect(properties={"value": 0.3}, automatic={"on": "crit"})))
        bare = weapon(crit=1)
        modded = weapon(crit=1).configure(hunter)
        self.assertGreater(modded.results.main.average.flat_dotph, bare.results.main.average.flat_dotph)

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

    def test_contributions_are_additive_to_total_gain(self):
        configured = weapon().configure(Build(arsenal.upgrade.get("Serration"), arsenal.upgrade.get("Point Strike")))
        values = configured.results.shapley_contributions()
        self.assertAlmostEqual(sum(values.values()), 1)
        self.assertEqual(set(values), {"Serration", "Point Strike"})


if __name__ == "__main__": unittest.main()
