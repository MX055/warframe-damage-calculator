import json
import unittest
from pathlib import Path

from database_constructor.reconstruct_database import build_database, build_weapons, serialize_database, validate_database
from warframe_damage_calculator import Primary, Upgrade, arsenal


class CanonicalDatabaseTests(unittest.TestCase):
    def test_single_file_is_deterministic_and_has_only_required_metadata(self):
        path = Path(__file__).parents[1] / "database" / "database.json"
        database = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(database["schema_version"], 1)
        self.assertEqual(set(database), {"schema_version", "weapons", "upgrades", "riven_stats"})
        validate_database(database)

        source_path = Path(__file__).parents[1] / "database_constructor" / "sources" / "underframe_api_data.json"
        source = json.loads(source_path.read_text(encoding="utf-8"))
        first = serialize_database(build_database(source))
        second = serialize_database(build_database(source))
        self.assertEqual(first, second)
        self.assertIn('{"value": 1.2}', first)
        self.assertIn('{"value": 1.5, "when": "weak_point_kill"}', first)
        self.assertIn('{"value": 0.35, "stacks": {"when": "kill", "max": 2}}', first)
        self.assertIn('{"value": 0.55, "equipped": ["Sacrificial Pressure"]}', first)
        self.assertIn('{"value": 0.3, "rank": 5}', first)
        self.assertIn('"types": ["primary"]', first)
        self.assertIn('"base_damage": [{"value": 1.65}]', first)
        self.assertEqual(database["riven_stats"]["rifle"]["base_damage"], 1.65)
        self.assertEqual(database["riven_stats"]["rifle"]["crit_chance"], 1.4999)
        self.assertEqual(database["riven_stats"]["rifle"]["toxin"], 0.9)
        self.assertEqual(database["riven_stats"]["rifle"]["corpus_damage"], 0.45)
        self.assertEqual(database["riven_stats"]["rifle"]["grineer_damage"], 0.45)
        self.assertEqual(database["riven_stats"]["rifle"]["infested_damage"], 0.45)
        self.assertNotIn("faction_damage", database["riven_stats"]["rifle"])
        self.assertEqual(database["riven_stats"]["rifle"]["punch_through"], 2.7)
        self.assertEqual(database["riven_stats"]["melee"]["combo_duration"], 8.1)
        self.assertEqual(database["riven_stats"]["melee"]["initial_combo"], 24.5)
        self.assertIn("attack_speed", database["riven_stats"]["melee"])
        self.assertIn("fire_rate", database["riven_stats"]["rifle"])
        self.assertFalse(any(
            isinstance(value, str)
            for stats in database["riven_stats"].values()
            for value in stats.values()
        ))

    def test_weapon_modes_use_identifiers_and_canonical_relationships(self):
        weapon = arsenal.weapons["Corinth Prime"]
        self.assertNotIn("context", weapon)
        self.assertNotIn("modes", weapon)
        self.assertIn("air_burst_projectile", weapon["attacks"])
        self.assertTrue(all("name" not in attack for attack in weapon["attacks"].values()))
        self.assertEqual(weapon["attacks"]["air_burst_projectile"]["children"], ["air_burst_explosion"])
        self.assertEqual(weapon["type"], "primary")
        self.assertEqual(weapon["subtype"], "shotgun")
        self.assertEqual(weapon["ammo"]["magazine_size"], 20)
        self.assertNotIn("children", weapon["attacks"]["buckshot"])
        self.assertNotIn("multishot", weapon["attacks"]["air_burst_projectile"]["stats"])
        for entry in arsenal.weapons.values():
            for mode in entry["attacks"].values():
                self.assertIn("co_factor", mode["stats"])
                self.assertIn("co_effect", mode["stats"])
        self.assertIsInstance(arsenal.get("Corinth Prime"), Primary)

    def test_models_accept_database_section_entries_as_their_only_argument(self):
        weapon = Primary({"Corinth Prime": arsenal.weapons["Corinth Prime"]})
        upgrade = Upgrade({"True Steel": arsenal.upgrades["True Steel"]})
        self.assertEqual(weapon.data.name, "Corinth Prime")
        self.assertEqual(weapon.data.entry.type, "primary")
        self.assertNotIn("context", weapon.data)
        self.assertEqual(upgrade.data.name, "True Steel")
        self.assertEqual(upgrade.data.entry.type, "mod")
        self.assertNotIn("context", upgrade.data)

    def test_duplicate_mode_names_receive_content_stable_ids(self):
        source = {"weapons": [{"name": "Duplicate", "type": "Primary", "subtype": "Rifle", "fire_modes": [
            {"mode_name": "Normal", "projectile_type": "Hit-Scan", "innate_elements": {"DT_IMPACT": 1}},
            {"mode_name": "Normal", "projectile_type": "Projectile", "innate_elements": {"DT_IMPACT": 2}},
        ]}]}
        modes = build_weapons(source)["Duplicate"]["attacks"]
        self.assertEqual(len(modes), 2)
        self.assertTrue(all(identifier.startswith("normal_") for identifier in modes))

    def test_beams_are_mode_properties(self):
        weapon = arsenal.weapons["Tenet Cycron"]
        self.assertTrue(any(mode["delivery"] == "beam" for mode in weapon["attacks"].values()))
        self.assertTrue(all("is_beam" not in mode for mode in weapon["attacks"].values()))
        explosion = arsenal.weapons["Corinth Prime"]["attacks"]["air_burst_explosion"]
        self.assertTrue(explosion["aoe"])
        self.assertEqual(explosion["delivery"], "projectile")

    def test_effect_shapes_conditions_stacking_and_overrides(self):
        upgrades = arsenal.upgrades
        self.assertEqual(upgrades["True Steel"]["stats"]["crit_chance"], [{"value": 1.2}])
        self.assertEqual(upgrades["Primary Deadhead"]["stats"]["weakpoint_damage"][0]["rank"], 5)
        self.assertEqual(upgrades["Sacrificial Steel"]["stats"]["crit_chance"][1]["equipped"], ["Sacrificial Pressure"])
        self.assertEqual(upgrades["Berserker Fury"]["stats"]["attack_speed"][0]["stacks"]["max"], 2)
        self.assertNotIn("max", upgrades["Condition Overload"]["stats"]["condition_overload"][0]["stacks"])
        self.assertEqual(upgrades["Acid Shells"]["compatibility"], {"names": ["Kuva Sobek", "Sobek"], "exilus": False})
        self.assertNotIn("Dual Skana", upgrades["Bright Purity"]["compatibility"]["names"])
        self.assertEqual(upgrades["Accelerated Blast"]["compatibility"], {"subtypes": ["shotgun"], "exilus": False})
        self.assertTrue(upgrades["Terminal Velocity"]["compatibility"]["exilus"])
        self.assertFalse(upgrades["Primary Deadhead"]["compatibility"]["exilus"])
        self.assertEqual(upgrades["Semi-Rifle Cannonade"]["compatibility"]["triggers"], ["semi"])
        self.assertFalse(upgrades["Semi-Rifle Cannonade"]["compatibility"]["aoe"])
        self.assertIn("Fury", upgrades["Berserker Fury"]["incompatibility"])
        self.assertEqual(upgrades["Melee Duplicate"]["stats"], {"melee_duplicate": [{"value": 1}]})
        self.assertEqual(upgrades["Melee Doughty"]["stats"], {"melee_doughty": [{"value": 1}]})
        self.assertEqual(upgrades["Secondary Encumber"]["stats"], {"secondary_encumber": [{"value": 0.24}]})
        self.assertEqual(upgrades["Secondary Enervate"]["stats"], {"secondary_enervate": [{"value": 6}]})
        self.assertEqual(upgrades["Primed Bane of Corpus"]["stats"]["corpus_damage"], [{"value": 0.55}])
        self.assertEqual(upgrades["Bane of Grineer"]["stats"]["grineer_damage"], [{"value": 0.3}])
        self.assertEqual(upgrades["Bane of Orokin"]["stats"]["orokin_damage"], [{"value": 0.3}])
        self.assertEqual(upgrades["Bane of The Murmur"]["stats"]["murmur_damage"], [{"value": 0.3}])
        self.assertEqual(upgrades["Sacrificial Pressure"]["stats"]["sentient_damage"], [{"value": 0.33}])
        for upgrade in upgrades.values():
            identity = set(upgrade["compatibility"]) & {"names", "subtypes", "types"}
            self.assertEqual(len(identity), 1)
        self.assertIsInstance(arsenal.get("Berserker Fury"), Upgrade)

    def test_incarnon_evolutions_use_numeric_tiers_and_perks(self):
        evolutions = arsenal.weapons["Telos Boltor"]["evolutions"]
        self.assertIn("2", evolutions)
        self.assertIn("1", evolutions["2"])
        self.assertIn("description", evolutions["2"]["1"])
        self.assertIn("stats", evolutions["2"]["1"])
        conditional = evolutions["2"]["1"]["stats"]["punch_through"][0]
        self.assertEqual(conditional["when"], "channeled_ability")
        self.assertNotIn("equipped", conditional)

    def test_invalid_entries_report_the_named_field(self):
        invalid = {"schema_version": 1, "weapons": {
            "Broken": {"type": "primary", "attacks": {"normal": {"trigger": "semi", "delivery": "hitscan", "stats": {"damage": {"impact": 1}, "co_factor": 1, "co_effect": "adds"}, "children": ["missing"]}}}
        }, "upgrades": {}, "riven_stats": {}}
        with self.assertRaisesRegex(ValueError, r"weapon 'Broken'.*children"):
            validate_database(invalid)


if __name__ == "__main__":
    unittest.main()
