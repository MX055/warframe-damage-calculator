import importlib
import inspect
import pkgutil
import unittest

from warframe_damage_calculator import fields
from warframe_damage_calculator.core.data import Data
from warframe_damage_calculator.fields.calculated import CalculatedMultiplicativeFamilies, ModdedStats
from warframe_damage_calculator.fields.evolution import ResolvedEvolutionMultiplicativeFamilies, ResolvedEvolutionStat
from warframe_damage_calculator.fields.upgrade import ResolvedElements, ResolvedModeStats, ResolvedMultiplicativeFamilies, ResolvedStat, UpgradeCompatibility, UpgradeData, UpgradeRuntime
from warframe_damage_calculator.fields.weapon_data import WeaponAmmo, WeaponData, WeaponRuntime


class FieldDataTypeTests(unittest.TestCase):
    def test_no_field_attribute_uses_plain_data(self) -> None:
        for module_info in pkgutil.iter_modules(fields.__path__):
            module = importlib.import_module(f"{fields.__name__}.{module_info.name}")
            for _, field_type in inspect.getmembers(module, inspect.isclass):
                if field_type.__module__ == module.__name__ and issubclass(field_type, Data):
                    self.assertNotIn(Data, field_type.__annotations__.values(), f"{field_type.__name__} has a plain Data field")

    def test_structural_mappings_use_their_declared_data_types(self) -> None:
        weapon = WeaponData({"ammo": {"magazine_size": 10}, "runtime": {"attack": "Primary"}})
        upgrade = UpgradeData({"compatibility": {"type": ["Primary"]}, "runtime": {"rank": 5}})
        resolved_mode = ResolvedModeStats({"elements": {"heat": 0.9}})
        resolved = ResolvedStat({"multiplicative_families": {"bonus": {"damage": {"slash": 1.0}}}})
        evolution = ResolvedEvolutionStat({"multiplicative_families": {"bonus": {"damage": 1.0}}})
        modded = ModdedStats({"multiplicative_families": {"bonus": {"damage": {"slash": 1.0}}}})
        self.assertIsInstance(weapon.ammo, WeaponAmmo)
        self.assertIsInstance(weapon.runtime, WeaponRuntime)
        self.assertIsInstance(upgrade.compatibility, UpgradeCompatibility)
        self.assertIsInstance(upgrade.runtime, UpgradeRuntime)
        self.assertIsInstance(resolved_mode.elements, ResolvedElements)
        self.assertIsInstance(resolved.multiplicative_families, ResolvedMultiplicativeFamilies)
        self.assertIsInstance(evolution.multiplicative_families, ResolvedEvolutionMultiplicativeFamilies)
        self.assertIsInstance(modded.multiplicative_families, CalculatedMultiplicativeFamilies)


if __name__ == "__main__":
    unittest.main()
