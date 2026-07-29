import unittest
import warnings
from copy import deepcopy

from warframe_damage_calculator import arsenal
from warframe_damage_calculator.schema import validate_database


class DatabaseTests(unittest.TestCase):
    def test_catalog_counts(self):
        self.assertEqual(arsenal.database["schema_version"], 8)
        self.assertEqual((len(arsenal.weapon), len(arsenal.upgrade), len(arsenal.enemy)), (656, 779, 877))

    def test_every_effect_channel_is_a_dictionary(self):
        effects = [effect for upgrade in arsenal.database["upgrades"].values() for values in upgrade.get("stats", {}).values() for effect in values]
        effects.extend(effect for weapon in arsenal.database["weapons"].values() for tier in weapon.get("evolutions", {}).values() for perk in tier.values() for values in perk.get("stats", {}).values() for effect in values)
        self.assertEqual(len(effects), 1792)
        for effect in effects:
            self.assertEqual(set(effect), {"properties", "manual", "automatic"})
            self.assertTrue(all(isinstance(effect[channel], dict) for channel in effect))
            self.assertFalse({"target", "if", "scope", "exclude", "apply_mode"} & effect["automatic"].keys())
            self.assertNotEqual(effect["automatic"].get("with"), "bow_multiplier")

    def test_proc_chances_and_conditions_use_flat_automatic_fields(self):
        hunter = arsenal.database["upgrades"]["Hunter Munitions"]["stats"]["slash_proc"]
        self.assertEqual(hunter, [{"properties": {"value": 1}, "manual": {}, "automatic": {"on": "crit", "chance": 0.3}}])
        hemorrhage = arsenal.database["upgrades"]["Hemorrhage"]["stats"]["slash_proc"]
        self.assertEqual(hemorrhage, [
            {"properties": {"value": 1}, "manual": {}, "automatic": {"on": "impact_proc", "chance": 0.35}},
            {"properties": {"value": 1}, "manual": {}, "automatic": {"on": "impact_proc", "when": "fire_rate_below_2.5", "chance": 0.35}},
        ])
        self.assertEqual(arsenal.database["weapons"]["Anku"]["evolutions"]["1"]["1"]["stats"]["slash_proc"][0]["properties"]["value"], 1)

    def test_bow_fire_rate_bonuses_are_separate_effects(self):
        names = {"Critical Delay", "Primed Shred", "Shred", "Speed Trigger", "Vigilante Fervor", "Vile Acceleration", "Vile Precision"}
        for name in names:
            effects = arsenal.database["upgrades"][name]["stats"]["fire_rate"]
            self.assertEqual(len(effects), 2)
            self.assertEqual(effects[0]["properties"], effects[1]["properties"])
            self.assertEqual(effects[0]["automatic"], {})
            self.assertEqual(effects[1]["automatic"], {"when": "bow"})

    def test_special_upgrades_use_domain_terms(self):
        doughty = arsenal.database["upgrades"]["Melee Doughty"]["stats"]["crit_damage"]
        self.assertEqual(doughty, [{"properties": {"value": 1, "mode": "flat", "max": 50}, "manual": {}, "automatic": {"with": "puncture_status_chance", "per": 0.1}}])
        synth = arsenal.database["upgrades"]["Synth Charge"]["stats"]["damage_bonus"]
        self.assertEqual(synth, [{"properties": {"value": 2, "family": "last_shot"}, "manual": {}, "automatic": {"on": "last_shot", "when": ["not_continuous", "not_incarnon", "magazine_5_plus"]}}])
        vigilante = arsenal.database["upgrades"]["Vigilante Supplies"]["stats"]
        self.assertNotIn("crit_chance", vigilante)
        self.assertEqual(vigilante["crit_tier"], [{"properties": {"value": 1, "mode": "flat"}, "manual": {}, "automatic": {"on": "crit", "chance": 0.05}}])

    def test_evolution_form_applicability_uses_when(self):
        form_conditions = []
        for weapon in arsenal.database["weapons"].values():
            for tier in weapon.get("evolutions", {}).values():
                for evolution in tier.values():
                    for effects in evolution.get("stats", {}).values():
                        for effect in effects:
                            conditions = effect["automatic"].get("when", [])
                            form_conditions.extend(conditions if isinstance(conditions, list) else [conditions])
        self.assertEqual(sum(condition in {"normal", "incarnon"} for condition in form_conditions), 145)

    def test_every_record_constructs_and_calculates(self):
        for name in arsenal.weapon: arsenal.weapon.get(name)
        for name in arsenal.enemy: arsenal.enemy.get(name)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for name in arsenal.upgrade:
                for weapon in ("Braton", "Lato", "Bo Prime"):
                    arsenal.weapon.get(weapon).configure(arsenal.upgrade.get(name))

    def test_every_evolution_choice_and_attack_calculates(self):
        count = 0
        for name in arsenal.weapon:
            weapon = arsenal.weapon.get(name)
            for tier, choices in weapon.evolutions.items():
                if tier == "1": continue
                for choice in choices:
                    weapon.set(evolutions={int(tier): int(choice)})
                    for attack in weapon.attacks: weapon.set(attack=attack)
                    count += 1
        self.assertEqual(count, 768)

    def test_schema_rejects_removed_upgrade_fields(self):
        database = deepcopy(arsenal.database)
        database["upgrades"]["Serration"]["conflict_groups"] = []
        with self.assertRaisesRegex(ValueError, "invalid fields"):
            validate_database(database)


if __name__ == "__main__": unittest.main()
