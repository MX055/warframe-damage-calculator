import unittest

from warframe_damage_calculator import Build, Compatibility, Dist, Effect, Upgrade, UpgradeStats


class DistTests(unittest.TestCase):
    def test_damage_is_ordered_and_combines_elements(self):
        damage = Dist(impact=100).apply_modifiers({"toxin": 0.9, "cold": 0.9})
        self.assertEqual(list(damage), ["impact", "viral"])
        self.assertEqual(damage.total, 280)


class EffectTests(unittest.TestCase):
    def test_effect_fields_are_flat_and_automation_is_separate(self):
        effect = Effect(0.4, mode="flat", family="unique_status", when="kill", stacks=2, duration=20).automate(with_="unique_status_count", stacks="inf")
        self.assertEqual(effect.value, 0.4)
        self.assertEqual(effect.mode, "flat")
        self.assertEqual(effect.family, "unique_status")
        self.assertEqual(effect.stacks, 2)
        self.assertEqual(effect.duration, 20)
        self.assertEqual(effect.automatic["with"], "unique_status_count")

    def test_manual_and_automatic_fields_are_separate(self):
        with self.assertRaises(TypeError): Effect(1, with_="weapon_combo")
        with self.assertRaises(TypeError): Effect(1).automate(requires_rank=5)
        with self.assertRaises(TypeError): Effect(1).automate(target="slash")
        with self.assertRaisesRegex(ValueError, "must omit"): Effect(1, when="on_kill")

    def test_fields_preserve_native_scalar_types(self):
        effect = Effect(1, stacks=2, duration=20).automate(on="CRITICAL_HIT")
        self.assertEqual(effect.stacks, 2)
        self.assertEqual(effect.duration, 20)
        self.assertEqual(effect.automatic, {"on": "critical_hit"})

    def test_repeatable_automatic_fields_use_lists(self):
        effect = Effect(2).automate(when=['NON_CONTINUOUS_FIRE', 'NORMAL_FORM'], on='MAGAZINE_LAST_SHOT')
        self.assertEqual(effect.automatic, {"when": ["non_continuous_fire", "normal_form"], "on": "magazine_last_shot"})

    def test_scalar_upgrade_stats_are_wrapped_as_effects(self):
        scalar = UpgradeStats(damage_bonus=1.5)
        explicit = UpgradeStats(damage_bonus=Effect(1.5))
        self.assertEqual(scalar.damage_bonus, explicit.damage_bonus)


class UpgradeTests(unittest.TestCase):
    def test_runtime_retains_raw_stacks_while_each_effect_caps_itself(self):
        upgrade = Upgrade(
            name="Galvanized",
            max_rank=10,
            compatibility=Compatibility(types=["primary"]),
            stats=UpgradeStats(
                damage_bonus=Effect(0.4, when='kill', stacks=2),
                multishot=Effect(0.1, when='kill', stacks=4),
            ),
        ).set(kill=4)
        resolved = {effect.stat: effect.value for effect in upgrade.resolve_manual()}
        self.assertEqual(upgrade.runtime.kill, 4)
        self.assertAlmostEqual(resolved["damage_bonus"], 0.8)
        self.assertAlmostEqual(resolved["multishot"], 0.4)

    def test_build_distributes_only_declared_manual_state(self):
        first = Upgrade(name="First", stats=UpgradeStats(damage_bonus=Effect(1, when='hit')))
        second = Upgrade(name="Second")
        build = Build(first, second).set(hit=False)
        self.assertFalse(build.upgrades[0].runtime.hit)
        with self.assertRaises(TypeError): build.set(kill=1)

    def test_build_addition_and_subtraction_return_independent_builds(self):
        first = Upgrade(name="First")
        second = Upgrade(name="Second")
        combined = Build(first) + second
        reduced = combined - first
        self.assertEqual([upgrade.name for upgrade in combined], ["First", "Second"])
        self.assertEqual([upgrade.name for upgrade in reduced], ["Second"])
        self.assertIsNot(combined[1], second)


if __name__ == "__main__": unittest.main()
