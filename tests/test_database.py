import unittest
import warnings

from warframe_damage_calculator import Calculator, Loadout, arsenal
from warframe_damage_calculator.database.compatibility import is_upgrade_compatible
from warframe_damage_calculator.domain.damage import Dist
from warframe_damage_calculator.domain.effects import Effect, Source
from warframe_damage_calculator.domain.scaled_values import ScaledValue
from warframe_damage_calculator.domain.upgrades import Mod, UpgradeStats
from warframe_damage_calculator.domain.warnings import LoadoutCompatibilityWarning
from warframe_damage_calculator.domain.weapons import Attack, AttackStats, Melee, Secondary


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
        self.assertEqual(arsenal.database["schema_version"], 24)
        self.assertIn("Devouring Attrition", arsenal.database["upgrades"]["perks"])
        self.assertEqual(arsenal.database["upgrades"]["perks"]["Devouring Attrition"]["stats"]["damage_bonus"][0]["value"], {"source": "$values.damage_bonus[0]"})

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

    def test_upgrade_and_weapon_descriptions_are_loaded(self):
        serration = arsenal.mod.get("Serration")
        merciless = arsenal.arcane.get("Primary Merciless")
        boltor = arsenal.primary.get("Boltor")
        self.assertIsInstance(serration.description, str)
        self.assertIsInstance(merciless.description, str)
        self.assertIsInstance(boltor.description, str)
        self.assertEqual(serration.description, "+165% Damage")
        self.assertEqual(arsenal.mod.get("Malignant Force").description, "+60% Toxin\n+60% Status Chance")
        self.assertEqual(list(arsenal.mod.get("Maiming Strike").stats), ["slide_crit_chance"])
        self.assertEqual(arsenal.mod.get("Maiming Strike").stats["slide_crit_chance"][0].value.value, 1.5)
        influence = arsenal.arcane.get("Melee Influence")
        self.assertEqual(influence.description, "On Melee\nElectricity Status:\n20% chance for elemental Melee Status Effects to apply to enemies within 20m for 18s. Cannot refresh while active.")

    def test_perk_descriptions_resolve_from_weapon_evolutions(self):
        perk = arsenal.perk.get("Elemental Balance")
        self.assertEqual(perk.description_source.path, "$description")
        weapon = arsenal.primary.get("Telos Boltor")
        values = weapon.perks[perk]
        resolved = weapon.resolve_perk(perk)
        self.assertEqual(resolved.description, values.description)
        self.assertTrue(resolved.description)

    def test_attack_and_bodypart_keys_are_separate_from_display_names(self):
        attack = arsenal.primary.get("Coda Bassocyst").attacks["normal_attack"]
        self.assertEqual(attack.name, "Normal Attack")
        self.assertEqual(arsenal.enemy.get("Drudge Brazer").bodyparts["stealth_finisher"].name, "Stealth Finisher")

    def test_upgrade_repositories_filter_by_weapon_compatibility(self):
        vectis = arsenal.primary.get("Vectis Prime")
        filtered_mods = {mod.name for mod in arsenal.mod.filter(weapon=vectis, implemented=True)}
        filtered_arcanes = {arcane.name for arcane in arsenal.arcane.filter(weapon=vectis, implemented=True)}
        self.assertNotIn("Tainted Mag", filtered_mods)
        self.assertNotIn("Sinister Reach", filtered_mods)
        self.assertNotIn("Shotgun Vendetta", filtered_arcanes)
        self.assertIn("Primary Merciless", filtered_arcanes)
        self.assertNotIn("Primary Overcharge", filtered_arcanes)

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

    def test_nightwatch_napalm_only_generates_its_child_attack_when_equipped(self):
        weapon = arsenal.primary.get("Kuva Ogris")
        ogris = arsenal.primary.get("Ogris")
        napalm = arsenal.mod.get("Nightwatch Napalm")
        self.assertEqual(len(napalm.stats.generated_attack), 1)
        self.assertNotIn("nightwatch_napalm_linger", weapon.attacks)
        plain = Calculator(weapon).resolve(attack="rocket_impact")
        self.assertNotIn("nightwatch_napalm_linger", plain.attacks)
        with self.assertRaisesRegex(ValueError, "unknown attack"): Calculator(weapon).resolve(attack="nightwatch_napalm_linger")
        result = Calculator(weapon, loadout=Loadout(mods=[napalm])).resolve(attack="rocket_impact")
        self.assertIn("nightwatch_napalm_linger", result.attacks)
        self.assertAlmostEqual(result.attacks["nightwatch_napalm_linger"].effective.end_range, 7.11)
        self.assertAlmostEqual(result.attacks["nightwatch_napalm_linger"].effective.damage["heat"], 687 * 0.3)
        ogris_result = Calculator(ogris, loadout=Loadout(mods=[napalm])).resolve(attack="rocket_impact")
        self.assertAlmostEqual(ogris_result.attacks["nightwatch_napalm_linger"].effective.damage["heat"], 600 * 0.3)
        generated = Calculator(weapon, loadout=Loadout(mods=[napalm])).resolve(attack="nightwatch_napalm_linger")
        self.assertEqual(list(generated.attacks), ["nightwatch_napalm_linger"])

    def test_generated_child_attacks_ignore_other_upgrades_multiplicative_range(self):
        weapon = arsenal.primary.get("Kuva Ogris")
        napalm = arsenal.mod.get("Nightwatch Napalm")
        firestorm = arsenal.mod.get("Primed Firestorm")
        compression = arsenal.arcane.get("Primary Compression")
        expanded = Calculator(weapon, loadout=Loadout(mods=[napalm, firestorm])).resolve(attack="rocket_impact")
        compressed = Calculator(weapon, loadout=Loadout(mods=[napalm, firestorm], arcanes=[compression])).resolve(attack="rocket_impact")
        self.assertAlmostEqual(expanded.attacks["rocket_explosion"].effective.end_range, 7.9 * 1.44)
        self.assertAlmostEqual(compressed.attacks["rocket_explosion"].effective.end_range, 7.9 * 1.44 * 0.2)
        self.assertAlmostEqual(expanded.attacks["nightwatch_napalm_linger"].effective.end_range, 7.11 * 1.44)
        self.assertAlmostEqual(compressed.attacks["nightwatch_napalm_linger"].effective.end_range, 7.11 * 1.44)
        self.assertAlmostEqual(compressed.attacks["rocket_explosion"].upgrades.proportional["damage_bonus"], 7.9 * 1.44 * 0.8)
        self.assertAlmostEqual(compressed.attacks["rocket_explosion"].average.ammo_efficiency, 7.9 * 1.44 * 0.8 * 0.055)

    def test_generated_child_attacks_keep_multiplicative_range_from_their_generator(self):
        weapon = arsenal.primary.get("Kuva Ogris")
        generator = Mod(name="Nightwatch Napalm", max_rank=0, stats=UpgradeStats(explosion_radius=Effect(0.5, mode="multiplicative"), generated_attack=arsenal.mod.get("Nightwatch Napalm").stats.generated_attack))
        result = Calculator(weapon, loadout=Loadout(mods=[generator])).resolve(attack="rocket_impact")
        self.assertAlmostEqual(result.attacks["rocket_explosion"].effective.end_range, 7.9 * 0.5)
        self.assertAlmostEqual(result.attacks["nightwatch_napalm_linger"].effective.end_range, 7.11 * 0.5)

    def test_primary_compression_can_be_disabled_by_the_aim_condition(self):
        weapon = arsenal.primary.get("Kuva Ogris")
        compression = arsenal.arcane.get("Primary Compression").set(aim=False)
        result = Calculator(weapon, loadout=Loadout(arcanes=[compression])).resolve(attack="rocket_explosion")
        self.assertAlmostEqual(result.attacks["rocket_explosion"].effective.end_range, 7.9)
        self.assertNotIn("damage_bonus", result.attacks["rocket_explosion"].upgrades.proportional)

    def test_melee_influence_generates_a_status_only_aoe_for_electricity_status(self):
        influence = arsenal.arcane.get("Melee Influence")
        electric = Melee(name="Electric", subtype="sword", attacks=[Attack(name="normal", trigger="melee", delivery="melee", stats=AttackStats(damage=Dist(slash=10, electricity=10), status_chance=1, range=3, fire_rate=1))])
        physical = Melee(name="Physical", subtype="sword", attacks=[Attack(name="normal", trigger="melee", delivery="melee", stats=AttackStats(damage=Dist(slash=10), status_chance=1, range=3, fire_rate=1))])
        self.assertEqual(set(influence.stats), {"generated_attack"})
        influence_effect = influence.stats.generated_attack[0]
        self.assertEqual(influence_effect.automatic["when"], "electricity_status_proc")
        self.assertEqual(influence_effect.automatic["chance"], 0.2)
        self.assertEqual(influence_effect.automatic["on"][0], "heat_status_proc")
        self.assertEqual(influence_effect.automatic["refresh"], False)
        self.assertEqual(influence_effect.value["links"]["parents"], {"deliveries": ["melee"]})
        self.assertIn("stats.crit_chance", influence_effect.value["inheritance"]["include"])
        self.assertIn("stats.damage.electricity", influence_effect.value["inheritance"]["include"])
        self.assertNotIn("attacks", arsenal.database["upgrades"]["arcanes"]["Melee Influence"])
        result = Calculator(electric, loadout=Loadout(arcanes=[influence])).resolve()
        self.assertAlmostEqual(result.attacks["normal"].effective.range, 3)
        self.assertAlmostEqual(result.attacks["melee_influence"].effective.end_range, 20)
        self.assertEqual(result.attacks["melee_influence"].average.direct_dph, 0)
        self.assertGreater(result.attacks["melee_influence"].average.dot_dph, 0)
        self.assertEqual(result.attacks["melee_influence"].base.damage, Dist(electricity=10))
        self.assertIn("electricity", result.attacks["melee_influence"].status.sustained_procs)
        self.assertNotIn("slash", result.attacks["melee_influence"].status.sustained_procs)
        physical_result = Calculator(physical, loadout=Loadout(arcanes=[influence])).resolve()
        self.assertNotIn("melee_influence", physical_result.attacks)
        self.assertAlmostEqual(physical_result.attacks["normal"].effective.range, 3)
        modded_result = Calculator(physical, loadout=Loadout(mods=[arsenal.mod.get("Shocking Touch")], arcanes=[influence])).resolve()
        self.assertIn("electricity", modded_result.attacks["melee_influence"].status.sustained_procs)
        rank_zero = arsenal.arcane.get("Melee Influence").set(rank=0)
        self.assertAlmostEqual(Calculator(electric, loadout=Loadout(arcanes=[rank_zero])).resolve().attacks["melee_influence"].effective.end_range, 20)
        self.assertEqual(rank_zero.resolve_manual()[0].automatic["for"], 3)

    def test_melee_duplicate_is_an_inherited_automatic_child_attack(self):
        duplicate = arsenal.arcane.get("Melee Duplicate")
        self.assertEqual(set(duplicate.stats), {"generated_attack"})
        effect = duplicate.stats.generated_attack[0]
        self.assertEqual(effect.value, {"name": "Melee Duplicate", "inheritance": {"include": ["trigger", "delivery", "aoe", "form", "category", "stats"]}, "links": {"parents": {"deliveries": ["melee"]}}})
        self.assertEqual(effect.automatic["on"], "near_yellow_critical_hit")
        self.assertEqual(effect.automatic["chance"], ScaledValue(1, True))
        for rank, chance in enumerate([1 / 6, 2 / 6, 3 / 6, 4 / 6, 5 / 6, 1]):
            self.assertAlmostEqual(duplicate.set(rank=rank).resolve_manual()[0].automatic["chance"], chance)
        result = Calculator(arsenal.melee.get("Bo Prime"), loadout=Loadout(arcanes=[duplicate])).resolve()
        self.assertIn("melee_duplicate", result.attacks)
        self.assertGreater(result.attacks["melee_duplicate"].average.direct_dph, 0)

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
                                self.assertTrue(all(isinstance(value, (int, float, bool, str)) for value in record["values"][stat]))

    def test_every_weapon_perk_resolves_to_concrete_effects(self):
        for repository in (arsenal.primary, arsenal.secondary, arsenal.melee, arsenal.archgun):
            for weapon_name in repository:
                weapon = repository.get(weapon_name)
                for perk in weapon.perks:
                    with self.subTest(weapon=weapon_name, perk=perk.name):
                        resolved = weapon.resolve_perk(perk)
                        self.assertTrue(all(not isinstance(effect.value, Source) for effect in resolved.effects))


if __name__ == "__main__": unittest.main()
