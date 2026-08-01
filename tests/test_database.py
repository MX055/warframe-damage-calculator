import unittest
import warnings

from warframe_damage_calculator import Calculator, Loadout, arsenal
from warframe_damage_calculator.database.compatibility import is_upgrade_compatible
from warframe_damage_calculator.domain.damage import Dist
from warframe_damage_calculator.domain.effects import PLACEHOLDER
from warframe_damage_calculator.domain.warnings import LoadoutCompatibilityWarning
from warframe_damage_calculator.domain.weapons import Attack, AttackStats, Secondary


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

AOE_RESTRICTED_UPGRADES = {"Energizing Shot", "Mending Shot", "Semi-Pistol Cannonade", "Semi-Rifle Cannonade", "Semi-Shotgun Cannonade"}


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
        self.assertEqual(set(arsenal.database["upgrades"]), {"mods", "arcanes", "perks"})
        self.assertTrue(all("kind" not in record for record in arsenal.database["upgrades"]["mods"].values()))
        self.assertTrue(all("kind" not in record for record in arsenal.database["upgrades"]["arcanes"].values()))
        self.assertTrue(all(arsenal.mod.get(name).type == "mod" for name in arsenal.mod))
        self.assertTrue(all(arsenal.arcane.get(name).type == "arcane" for name in arsenal.arcane))

    def test_perks_are_loaded_from_database(self):
        self.assertEqual(arsenal.database["schema_version"], 19)
        self.assertIn("Devouring Attrition", arsenal.database["upgrades"]["perks"])
        self.assertEqual(arsenal.database["upgrades"]["perks"]["Devouring Attrition"]["stats"]["damage_bonus"][0]["value"], "$weapon")

    def test_weapon_records_contain_only_perk_values(self):
        record = arsenal.database["weapons"]["primaries"]["Phenmor"]["evolutions"]["5"]["1"]
        self.assertEqual(record["perk"], "Devouring Attrition")
        self.assertNotIn("stats", record)
        self.assertEqual(record["values"]["damage_bonus"], [20])

    def test_repositories_are_case_insensitive(self):
        self.assertEqual(arsenal.primary.get("corinth prime").name, "Corinth Prime")
        self.assertEqual(arsenal.mod.get("serration").name, "Serration")
        self.assertEqual(arsenal.arcane.get("primary merciless").name, "Primary Merciless")
        self.assertEqual(arsenal.perk.get("devouring attrition").name, "Devouring Attrition")

    def test_upgrade_repositories_filter_by_weapon_compatibility(self):
        vectis = arsenal.primary.get("Vectis Prime")
        filtered_mods = {mod.name for mod in arsenal.mod.filter(weapon=vectis, implemented=True)}
        filtered_arcanes = {arcane.name for arcane in arsenal.arcane.filter(weapon=vectis, implemented=True)}
        self.assertNotIn("Tainted Mag", filtered_mods)
        self.assertNotIn("Sinister Reach", filtered_mods)
        self.assertNotIn("Shotgun Vendetta", filtered_arcanes)
        self.assertIn("Primary Overcharge", filtered_arcanes)

    def test_aoe_compatibility_metadata_contains_only_intentional_restrictions(self):
        restricted = {name for repository in (arsenal.mod, arsenal.arcane) for name in repository if repository.get(name).compatibility.aoe is False}
        self.assertEqual(restricted, AOE_RESTRICTED_UPGRADES)
        stug = arsenal.secondary.get("Stug")
        self.assertTrue(all(attack.aoe for attack in stug.attacks.values()))
        self.assertTrue(is_upgrade_compatible(arsenal.mod.get("Hornet Strike"), stug))
        self.assertFalse(is_upgrade_compatible(arsenal.mod.get("Energizing Shot"), stug))
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            Calculator(stug, loadout=Loadout(mods=[arsenal.mod.get("Hornet Strike")])).resolve()
        self.assertFalse(any(isinstance(item.message, LoadoutCompatibilityWarning) for item in captured))

    def test_attack_compatibility_constraints_must_match_the_same_attack(self):
        weapon = Secondary(name="Mixed", subtype="pistol", attacks=[
            Attack(name="semi_aoe", trigger="semi", aoe=True, stats=AttackStats(damage=Dist(impact=10))),
            Attack(name="auto_direct", trigger="auto", stats=AttackStats(damage=Dist(impact=10))),
        ])
        cannonade = arsenal.mod.get("Semi-Pistol Cannonade")
        self.assertFalse(is_upgrade_compatible(cannonade, weapon))
        self.assertFalse(is_upgrade_compatible(cannonade, weapon, attack="semi_aoe"))
        self.assertFalse(is_upgrade_compatible(cannonade, weapon, attack="auto_direct"))

    def test_upgrade_repository_supports_attack_slot_and_conflict_filters(self):
        ignis = arsenal.primary.get("Ignis Wraith")
        beam_exilus = {mod.name for mod in arsenal.mod.filter(weapon=ignis, slot="exilus_mod", implemented=True)}
        self.assertIn("Sinister Reach", beam_exilus)
        vectis = arsenal.primary.get("Vectis Prime")
        self.assertFalse(arsenal.mod.is_compatible("Tainted Mag", weapon=vectis))
        self.assertTrue(arsenal.arcane.is_compatible("Primary Overcharge", weapon=vectis))

    def test_global_perk_names_are_unique(self):
        normalized = [" ".join(name.split()).casefold() for name in arsenal.perk]
        self.assertEqual(len(normalized), len(set(normalized)))

    def test_metadata_only_perks_are_explicit(self):
        metadata_only = {name for name, record in arsenal.database["upgrades"]["perks"].items() if not record["stats"]}
        self.assertEqual(metadata_only, METADATA_ONLY_PERKS)

    def test_database_wide_perk_value_invariants(self):
        database = arsenal.database
        for category, weapons in database["weapons"].items():
            for weapon_name, weapon in weapons.items():
                for tier, choices in weapon.get("evolutions", {}).items():
                    for choice, record in choices.items():
                        with self.subTest(weapon=weapon_name, tier=tier, choice=choice):
                            template = database["upgrades"]["perks"][record["perk"]]["stats"]
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
