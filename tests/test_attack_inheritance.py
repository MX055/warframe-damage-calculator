import unittest
from copy import deepcopy

from warframe_damage_calculator import Attack, AttackStats, Automatic, Calculator, Compatibility, Dist, GeneratedAttack, Inheritance, Build, Melee, Mod, RelatedAttacks, UpgradeStats, UpgradeValue, arsenal
from warframe_damage_calculator.database.schema import validate_database
from warframe_damage_calculator.engine.weapon_calculator import _resolve_attack_expressions, resolve_attack_inheritance


class AttackInheritanceTests(unittest.TestCase):
    def setUp(self):
        self.parent = Attack(
            "Parent",
            trigger="semi",
            delivery="projectile",
            form="incarnon",
            category="heavy",
            aoe=True,
            children=["native_child"],
            stats=AttackStats(damage=Dist(heat=20, cold=5), forced_procs=Dist(heat=1), crit_chance=0.8, crit_damage=4, status_chance=0.6, multishot=3, co_factor=2, co_effect="multiplies", falloff={"start_range": 2, "end_range": 10, "final_multiplier": 0.5}),
        )

    def test_no_inheritance_by_default(self):
        self.assertEqual(resolve_attack_inheritance({"name": "Generated"}, self.parent), {"name": "Generated"})

    def test_explicit_complete_inheritance_copies_every_listed_field(self):
        resolved = resolve_attack_inheritance({"inheritance": {"include": ["trigger", "delivery", "aoe", "form", "category", "stats"]}, "name": "Generated"}, self.parent)
        self.assertEqual(resolved["trigger"], "semi")
        self.assertEqual(resolved["stats"]["crit_chance"], 0.8)
        self.assertNotIn("children", resolved)
        resolved["stats"]["damage"]["heat"] = 100
        self.assertEqual(self.parent.children, ["native_child"])
        self.assertEqual(self.parent.stats.damage["heat"], 20)

    def test_unlisted_parent_fields_are_not_copied(self):
        parent = Attack("Parent", trigger="semi", delivery="projectile", stats=AttackStats(damage=Dist(impact=10), crit_chance=0.5, fire_rate=1))
        resolved = resolve_attack_inheritance({"inheritance": {"include": ["trigger"]}, "name": "Generated"}, parent)
        self.assertEqual(resolved, {"trigger": "semi", "name": "Generated"})
        parent.stats.crit_chance = 0.9
        self.assertEqual(resolved.get("stats"), None)

    def test_selective_top_level_and_nested_inheritance(self):
        top_level = resolve_attack_inheritance({"inheritance": {"include": ["trigger", "aoe"]}, "name": "Generated"}, self.parent)
        self.assertEqual(top_level, {"trigger": "semi", "aoe": True, "name": "Generated"})
        nested = resolve_attack_inheritance({"inheritance": {"include": ["stats.damage"]}, "name": "Generated"}, self.parent)
        self.assertEqual(nested["stats"]["damage"], {"heat": 20.0, "cold": 5.0})
        self.assertNotIn("crit_chance", nested["stats"])

    def test_explicit_values_recursively_override_mappings_and_replace_lists(self):
        definition = {
            "inheritance": {
                "include": ["stats"],
                "override": {
                    "stats.damage.heat": 10,
                    "stats.falloff.end_range": 20,
                },
            },
            "name": "Generated",
            "children": ["replacement"],
        }
        resolved = resolve_attack_inheritance(definition, self.parent)
        self.assertEqual(resolved["children"], ["replacement"])
        self.assertEqual(resolved["stats"]["damage"], {"heat": 10, "cold": 5.0})
        self.assertEqual(resolved["stats"]["falloff"], {"start_range": 2, "end_range": 20, "final_multiplier": 0.5})
        self.assertEqual(resolved["stats"]["crit_chance"], 0.8)

    def test_include_exclude_removes_nested_fields(self):
        resolved = resolve_attack_inheritance({"inheritance": {"include": ["stats"], "exclude": ["stats.forced_procs"]}, "name": "Generated"}, self.parent)
        self.assertIn("damage", resolved["stats"])
        self.assertNotIn("forced_procs", resolved["stats"])

    def test_children_are_not_inherited(self):
        resolved = resolve_attack_inheritance({"inheritance": {"include": ["trigger"]}, "name": "Generated"}, self.parent)
        self.assertNotIn("children", resolved)

    def test_invalid_inheritance_field_and_wildcard_fail(self):
        with self.assertRaisesRegex(ValueError, "invalid attack inheritance field"): resolve_attack_inheritance({"inheritance": {"include": ["stats.unknown"]}}, self.parent)
        with self.assertRaisesRegex(ValueError, "does not exist"): resolve_attack_inheritance({"inheritance": {"include": ["stats.falloff.start_range"]}}, Attack("Bare", stats=AttackStats(damage=Dist(heat=1))))
        with self.assertRaisesRegex(ValueError, "wildcard is not supported"): Inheritance(include=["*"])
        with self.assertRaisesRegex(ValueError, "wildcard is not supported"): Inheritance(include=["trigger", "*"])
        self.assertEqual(resolve_attack_inheritance({"inheritance": {"include": ["stats.damage.toxin"]}, "name": "Generated"}, self.parent), {"name": "Generated"})

    def test_dynamic_source_default_and_missing_value(self):
        self.assertEqual(_resolve_attack_expressions({"source": "$parent.stats.damage.toxin", "default": 0}, self.parent), 0)
        with self.assertRaisesRegex(ValueError, "does not exist"): _resolve_attack_expressions({"source": "$parent.stats.damage.toxin"}, self.parent)

    def test_schema_rejects_old_inheritance_and_kind_envelope(self):
        database = deepcopy(arsenal.database)
        database["upgrades"]["arcanes"]["Melee Duplicate"]["stats"]["generated_attack"][0]["inheritance"] = "$parent"
        with self.assertRaisesRegex(ValueError, "inheritance"): validate_database(database)
        database = deepcopy(arsenal.database)
        database["upgrades"]["arcanes"]["Melee Duplicate"]["stats"]["generated_attack"][0]["kind"] = "echo"
        with self.assertRaisesRegex(ValueError, "invalid fields"): validate_database(database)

    def test_melee_duplicate_is_a_full_copy_without_recursive_children(self):
        duplicate = arsenal.arcane.get("Melee Duplicate")
        weapon = Melee(name="Duplicate Test", subtype="sword", attacks={
            "parent": Attack("Parent", trigger="melee", delivery="melee", children=["native_child"], stats=AttackStats(damage=Dist(slash=10), crit_chance=1, crit_damage=3, status_chance=0.5, fire_rate=1)),
            "native_child": Attack("Native Child", trigger="melee", delivery="melee", stats=AttackStats(damage=Dist(impact=2), fire_rate=1)),
        })
        result = Calculator(weapon, build=Build(arcanes=[duplicate])).resolve(attack="parent")
        parent = result.weapon.attacks["parent"]
        generated = result.weapon.attacks["melee_duplicate"]
        self.assertEqual(generated.stats, parent.stats)
        self.assertEqual(generated.children, [])
        self.assertEqual((result.attacks["melee_duplicate"].generated_by, result.attacks["melee_duplicate"].generated_from), ("Melee Duplicate", "parent"))
        self.assertNotIn("melee_duplicate", generated.children)

    def test_melee_influence_definition_is_selective_but_uses_resolved_parent_status(self):
        influence = arsenal.arcane.get("Melee Influence")
        weapon = Melee(name="Influence Test", subtype="sword", attacks=[Attack("Heavy", trigger="melee", delivery="melee", category="heavy", stats=AttackStats(damage=Dist(slash=10, electricity=10), forced_procs=Dist(slash=1), crit_chance=0.8, crit_damage=4, status_chance=1, multishot=3, co_factor=2, co_effect="multiplies", fire_rate=1))])
        result = Calculator(weapon, build=Build(arcanes=[influence])).resolve(state={"combo_multiplier": 5})
        generated = result.weapon.attacks["melee_influence"]
        self.assertEqual(generated.stats.damage, Dist(electricity=10))
        self.assertEqual(generated.stats.forced_procs, Dist())
        self.assertEqual((generated.stats.crit_chance, generated.stats.crit_damage, generated.stats.status_chance, generated.stats.multishot), (0.8, 4, 0, 1))
        self.assertEqual((generated.stats.co_factor, generated.stats.co_effect, generated.children), (2, "multiplies", []))
        self.assertEqual(generated.category, "heavy")
        self.assertFalse(generated.hits_source)
        self.assertEqual(result.attacks["melee_influence"].generated_from, "heavy")
        self.assertEqual(result.attacks["melee_influence"].damage.combo_multiplier, 5)
        self.assertNotIn("slash", result.attacks["melee_influence"].status.sustained_procs)

    def test_nightwatch_napalm_has_explicit_combat_stats(self):
        result = Calculator(arsenal.primary.get("Kuva Ogris"), build=Build(mods=[arsenal.mod.get("Nightwatch Napalm")])).resolve(attack="rocket_impact")
        generated = result.weapon.attacks["nightwatch_napalm_linger"]
        self.assertEqual((generated.stats.crit_chance, generated.stats.crit_damage, generated.stats.status_chance), (0, 0, 0))
        self.assertEqual((generated.stats.multishot, generated.stats.co_factor, generated.stats.co_effect), (5, 1, "adds"))
        self.assertEqual(generated.stats.forced_procs, Dist(heat=1))
        self.assertEqual((result.attacks["nightwatch_napalm_linger"].generated_by, result.attacks["nightwatch_napalm_linger"].generated_from), ("Nightwatch Napalm", "rocket_explosion"))
        self.assertAlmostEqual(generated.stats.damage["heat"], 687 * 0.3)
        self.assertAlmostEqual(generated.stats.falloff.end_range, 7.9 * 0.9)

    def test_generated_attack_parent_context_is_deterministic(self):
        influence = arsenal.arcane.get("Melee Influence")
        weapon = Melee(name="Two Parents", subtype="sword", attacks={
            "first": Attack("First", trigger="melee", delivery="melee", stats=AttackStats(damage=Dist(electricity=10), status_chance=1, fire_rate=1)),
            "second": Attack("Second", trigger="melee", delivery="melee", category="heavy", stats=AttackStats(damage=Dist(electricity=30), status_chance=1, fire_rate=1)),
        })
        first = Calculator(weapon, build=Build(arcanes=[influence])).resolve(attack="first")
        second = Calculator(weapon, build=Build(arcanes=[influence])).resolve(attack="second")
        self.assertEqual(first.attacks["melee_influence"].generated_from, "first")
        self.assertEqual(second.attacks["melee_influence"].generated_from, "second")
        self.assertEqual(first.attacks["melee_influence"].effective.damage, Dist(electricity=2))
        self.assertEqual(second.attacks["melee_influence"].effective.damage, Dist(electricity=6))

    def test_generated_attack_contributions_are_deterministic_and_do_not_mutate_the_weapon(self):
        weapon = arsenal.primary.get("Kuva Ogris")
        calculator = Calculator(weapon, build=Build(mods=[arsenal.mod.get("Nightwatch Napalm")]))
        first = calculator.contributions(attack="rocket_impact")
        second = calculator.contributions(attack="rocket_impact")
        self.assertEqual(first, second)
        self.assertEqual(first.contribution, {"Nightwatch Napalm": 1.0})
        self.assertNotIn("nightwatch_napalm_linger", weapon.attacks)
        self.assertNotIn("nightwatch_napalm_linger", Calculator(weapon).resolve(attack="rocket_impact").attacks)

    def test_formatter_contributions_rebuild_event_generated_attacks(self):
        from warframe_damage_calculator import Formatter
        mod = Mod(
            name="Recursive Echo",
            max_rank=2,
            compatibility=Compatibility(subtypes=["rifle"]),
            stats=UpgradeStats(
                generated_attack=GeneratedAttack(
                    name="Generated Attack",
                    parent=RelatedAttacks(names=["Normal Attack"]),
                    children=["Generated Attack"],
                    inheritance=Inheritance(include=["trigger", "delivery", "form", "category", "stats"]),
                    automatic=Automatic(on="hit", chance=UpgradeValue(0.3, False)),
                )
            ),
        )
        result = Calculator(arsenal.primary.get("Karak"), build=Build(mods=[mod])).resolve()
        self.assertIn("generated_attack", result.weapon.attacks)
        contributions = Calculator(result.weapon, result.target, result.build).contributions()
        self.assertEqual(set(contributions.contribution), {"Recursive Echo"})
        self.assertAlmostEqual(contributions.contribution["Recursive Echo"], 1.0)
        table = Formatter(result).build_summary()
        self.assertIn("Recursive Echo", table)

    def test_contributions_on_result_weapon_do_not_keep_stale_generated_attacks(self):
        weapon = arsenal.melee.get("Bo Prime")
        mods = [arsenal.mod.get(name) for name in ("Blood Rush", "True Steel", "Organ Shatter", "Condition Overload", "Weeping Wounds", "Primed Pressure Point", "Vicious Frost", "North Wind")]
        build = Build(mods=mods, arcanes=[arsenal.arcane.get("Melee Duplicate")])
        without = Build(mods=mods)
        enemy = arsenal.enemy.get("Heavy Gunner")
        state = {"combo_multiplier": 4}
        fresh_with = Calculator(weapon, enemy, build).resolve(state=state).aggregate.damage.total_dps
        fresh_without = Calculator(weapon, enemy, without).resolve(state=state).aggregate.damage.total_dps
        self.assertGreater(fresh_with, fresh_without)
        result = Calculator(weapon, enemy, build).resolve(state=state)
        self.assertIn("melee_duplicate", result.weapon.attacks)
        contributions = Calculator(result.weapon, result.target, result.build).contributions(attack=result.selected_attack, state=result.state)
        self.assertLess(contributions.removal["Melee Duplicate"], 0)
        self.assertGreater(contributions.contribution["Melee Duplicate"], 0)

    def test_typed_construction_api(self):
        attack = GeneratedAttack(
            name="Aftershock",
            parent=RelatedAttacks(names=["Rocket Explosion"]),
            inheritance=Inheritance(include=["trigger", "delivery"], exclude=[], override={"aoe": True}),
            automatic=Automatic(on="hit", chance=UpgradeValue(0.3, True)),
        )
        self.assertEqual(attack.parent.names, ["Rocket Explosion"])
        self.assertTrue(attack.inheritance.override["aoe"])
        self.assertEqual(attack.automatic.chance, UpgradeValue(0.3, True))

    def test_generated_attack_on_hit_scales_by_chance(self):
        mod = Mod(
            name="Hit Echo",
            max_rank=2,
            compatibility=Compatibility(subtypes=["rifle"]),
            stats=UpgradeStats(
                generated_attack=GeneratedAttack(
                    name="Hit Echo",
                    parent=RelatedAttacks(names=["Normal Attack"]),
                    inheritance=Inheritance(include=["trigger", "delivery", "form", "category", "stats"]),
                    automatic=Automatic(on="hit", chance=UpgradeValue(0.3, False)),
                )
            ),
        )
        weapon = arsenal.primary.get("Karak")
        result = Calculator(weapon, build=Build(mods=[mod])).resolve()
        self.assertIn("hit_echo", result.attacks)
        parent = result.attacks["normal_attack"].damage.direct_dph
        child = result.attacks["hit_echo"].damage.direct_dph
        self.assertAlmostEqual(float(child), float(parent) * 0.3)

    def test_recursive_generated_attack_uses_geometric_expectation(self):
        mod = Mod(
            name="Recursive Echo",
            max_rank=2,
            compatibility=Compatibility(subtypes=["rifle"]),
            stats=UpgradeStats(
                generated_attack=GeneratedAttack(
                    name="Recursive Echo",
                    parent=RelatedAttacks(names=["Normal Attack"]),
                    children=["Recursive Echo"],
                    inheritance=Inheritance(include=["trigger", "delivery", "form", "category", "stats"]),
                    automatic=Automatic(on="hit", chance=UpgradeValue(0.3, False)),
                )
            ),
        )
        weapon = arsenal.primary.get("Karak")
        result = Calculator(weapon, build=Build(mods=[mod])).resolve()
        parent = result.attacks["normal_attack"].damage.direct_dph
        child = result.attacks["recursive_echo"].damage.direct_dph
        self.assertAlmostEqual(float(child), float(parent) * (0.3 / (1 - 0.3)))


if __name__ == "__main__": unittest.main()
