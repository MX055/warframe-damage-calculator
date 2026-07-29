import unittest
import warnings
from copy import deepcopy

from warframe_damage_calculator import arsenal
from warframe_damage_calculator.schema import validate_database


class DatabaseTests(unittest.TestCase):
    def test_catalog_counts(self):
        self.assertEqual((len(arsenal.weapon), len(arsenal.upgrade), len(arsenal.enemy)), (656, 779, 877))

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
