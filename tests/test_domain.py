import unittest

from warframe_damage_calculator import Build, Compatibility, Dist, Effect, Upgrade, UpgradeStats


class DistTests(unittest.TestCase):
    def test_damage_is_ordered_and_combines_elements(self):
        damage = Dist(impact=100).apply_modifiers({"toxin": 0.9, "cold": 0.9})
        self.assertEqual(list(damage), ["impact", "viral"])
        self.assertEqual(damage.total, 280)


class EffectTests(unittest.TestCase):
    def test_channels_compile_into_a_typed_program(self):
        effect = Effect(properties=["VALUE:0.4", "MODE:FLAT", "FAMILY:STATUS"], manual=["WHEN:ON_KILL", "STACKS:2", "FOR:20"], automatic=["WITH:UNIQUE_STATUS_COUNT", "STACKS:INF"])
        self.assertEqual(effect.program.value, 0.4)
        self.assertEqual(effect.program.mode, "flat")
        self.assertEqual(effect.program.family, "status")
        self.assertEqual(effect.program.manual_value("STACKS"), "2")
        self.assertEqual(effect.program.automatic_values("WITH"), ("UNIQUE_STATUS_COUNT",))

    def test_manual_and_automatic_opcodes_are_separate(self):
        with self.assertRaises(ValueError): Effect(properties=["VALUE:1"], manual=["WITH:WEAPON_COMBO"])
        with self.assertRaises(ValueError): Effect(properties=["VALUE:1"], automatic=["REQUIRES_RANK:5"])

    def test_unit_suffixes_are_not_part_of_numeric_operands(self):
        self.assertEqual(Effect(properties=["VALUE:1"], manual=["STACKS:2", "FOR:20"]).manual, ["STACKS:2", "FOR:20"])


class UpgradeTests(unittest.TestCase):
    def test_runtime_retains_raw_stacks_while_each_effect_caps_itself(self):
        upgrade = Upgrade(
            name="Galvanized",
            max_rank=10,
            compatibility=Compatibility(types=["primary"]),
            stats=UpgradeStats(
                damage_bonus=Effect(properties=["VALUE:0.4"], manual=["WHEN:ON_KILL", "STACKS:2"]),
                multishot=Effect(properties=["VALUE:0.1"], manual=["WHEN:ON_KILL", "STACKS:4"]),
            ),
        ).set(on_kill=4)
        resolved = {effect.stat: effect.value for effect in upgrade.resolve_manual()}
        self.assertEqual(upgrade.runtime.on_kill, 4)
        self.assertAlmostEqual(resolved["damage_bonus"], 0.8)
        self.assertAlmostEqual(resolved["multishot"], 0.4)

    def test_build_distributes_only_declared_manual_state(self):
        first = Upgrade(name="First", stats=UpgradeStats(damage_bonus=Effect(properties=["VALUE:1"], manual=["WHEN:HIT"])))
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
