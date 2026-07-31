import unittest

from warframe_damage_calculator import PLACEHOLDER, arsenal


METADATA_ONLY_PERKS = {
    "Armored Finisher",
    "Balanced Stagger",
    "Chain Shatter",
    "Devastating Mercy",
    "Echoes of Rage",
    "Explosive Growth",
    "Incarnon Imago",
    "Nimble Scythe",
    "Raging Drift",
    "Rapid Conclusion",
    "Silent Running",
    "Swift Transmute",
}


class DatabaseTests(unittest.TestCase):
    def test_repositories_load(self):
        self.assertEqual(sum(len(repository) for repository in (arsenal.primary, arsenal.secondary, arsenal.melee, arsenal.archgun)), 656)
        self.assertGreater(len(arsenal.mod), 700)
        self.assertGreater(len(arsenal.arcane), 50)
        self.assertGreater(len(arsenal.perk), 200)
        self.assertGreater(len(arsenal.enemy), 0)
        self.assertFalse(hasattr(arsenal, "upgrade"))
        self.assertFalse(hasattr(arsenal, "weapon"))

    def test_upgrade_collections_are_subdivided(self):
        self.assertIn("upgrades", arsenal.database)
        self.assertEqual(set(arsenal.database["upgrades"]), {"mod", "arcane", "perk"})
        self.assertTrue(all("kind" not in record for record in arsenal.database["upgrades"]["mod"].values()))
        self.assertTrue(all("kind" not in record for record in arsenal.database["upgrades"]["arcane"].values()))
        self.assertTrue(all(arsenal.mod.get(name).type == "mod" for name in arsenal.mod))
        self.assertTrue(all(arsenal.arcane.get(name).type == "arcane" for name in arsenal.arcane))

    def test_perks_are_loaded_from_database(self):
        self.assertEqual(arsenal.database["schema_version"], 18)
        self.assertIn("Devouring Attrition", arsenal.database["upgrades"]["perk"])
        self.assertEqual(arsenal.database["upgrades"]["perk"]["Devouring Attrition"]["stats"]["damage_bonus"][0]["value"], "$weapon")

    def test_weapon_records_contain_only_perk_values(self):
        record = arsenal.database["weapons"]["primary"]["Phenmor"]["evolutions"]["5"]["1"]
        self.assertEqual(record["perk"], "Devouring Attrition")
        self.assertNotIn("stats", record)
        self.assertEqual(record["values"]["damage_bonus"], [20])

    def test_repositories_are_case_insensitive(self):
        self.assertEqual(arsenal.primary.get("corinth prime").name, "Corinth Prime")
        self.assertEqual(arsenal.mod.get("serration").name, "Serration")
        self.assertEqual(arsenal.arcane.get("primary merciless").name, "Primary Merciless")
        self.assertEqual(arsenal.perk.get("devouring attrition").name, "Devouring Attrition")

    def test_global_perk_names_are_unique(self):
        normalized = [" ".join(name.split()).casefold() for name in arsenal.perk]
        self.assertEqual(len(normalized), len(set(normalized)))

    def test_metadata_only_perks_are_explicit(self):
        metadata_only = {name for name, record in arsenal.database["upgrades"]["perk"].items() if not record["stats"]}
        self.assertEqual(metadata_only, METADATA_ONLY_PERKS)

    def test_database_wide_perk_value_invariants(self):
        database = arsenal.database
        for category, weapons in database["weapons"].items():
            for weapon_name, weapon in weapons.items():
                for tier, choices in weapon.get("evolutions", {}).items():
                    for choice, record in choices.items():
                        with self.subTest(weapon=weapon_name, tier=tier, choice=choice):
                            template = database["upgrades"]["perk"][record["perk"]]["stats"]
                            self.assertEqual(set(record["values"]), set(template))
                            for stat, effects in template.items():
                                self.assertEqual(len(record["values"][stat]), len(effects))
                                self.assertNotIn("$weapon", record["values"][stat])

    def test_every_weapon_perk_resolves_to_concrete_effects(self):
        for repository in (arsenal.primary, arsenal.secondary, arsenal.melee, arsenal.archgun):
            for weapon_name in repository:
                weapon = repository.get(weapon_name)
                for perk in weapon.perks:
                    with self.subTest(weapon=weapon_name, perk=perk.name):
                        resolved = weapon.resolve_perk(perk)
                        self.assertTrue(all(effect.value is not PLACEHOLDER for effect in resolved.effects))


if __name__ == "__main__": unittest.main()
