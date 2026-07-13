from __future__ import annotations

import unittest

from warframe_damage_calculator import Melee, Primary, Secondary, Upgrade, arsenal
from warframe_damage_calculator.data.loader import WarframeDatabase


class ArsenalTests(unittest.TestCase):
    def test_name_only_lookup_returns_one_item(self) -> None:
        self.assertIsInstance(arsenal.get("Braton"), Primary)
        self.assertIsInstance(arsenal.get("Critical Delay"), Upgrade)
        self.assertIsInstance(arsenal.get("Primary Blight"), Upgrade)
        self.assertIsNone(arsenal.get("Missing Item"))

    def test_every_database_name_resolves_without_type(self) -> None:
        for entry in arsenal._entries:
            with self.subTest(name=entry.name):
                expected = (Primary, Secondary, Melee) if entry.is_weapon else Upgrade
                self.assertIsInstance(arsenal.get(entry.name), expected)

    def test_duplicate_names_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Duplicate arsenal item name"):
            WarframeDatabase({"primary": {"Same Name": {}}}, {"mod": {"same name": {}}})

    def test_context_is_copied_onto_named_upgrade(self) -> None:
        context = {"rank": 2, "headshot": True}
        upgrade = arsenal.get("Critical Delay", context=context)
        self.assertIsInstance(upgrade, Upgrade)
        self.assertEqual(upgrade.context, context)
        self.assertIsNot(upgrade.context, context)
        context["rank"] = 0
        self.assertEqual(upgrade.context["rank"], 2)

    def test_context_applies_to_upgrade_collection(self) -> None:
        upgrades = arsenal.get(type="arcane", context={"rank": 1})
        self.assertTrue(upgrades)
        self.assertTrue(all(isinstance(upgrade, Upgrade) and upgrade.context == {"rank": 1} for upgrade in upgrades.values()))

    def test_context_is_rejected_for_weapons(self) -> None:
        with self.assertRaisesRegex(TypeError, "context can only be applied to upgrades"):
            arsenal.get("Braton", context={"rank": 1})

    def test_element_specific_arcane_conditions(self) -> None:
        expected = {"Conjunction Voltage": ("electricity proc", 40), "Primary Blight": ("toxin proc", 40), "Secondary Shiver": ("cold proc", 10)}
        for name, (condition, max_stacks) in expected.items():
            with self.subTest(name=name):
                upgrade = arsenal.get(name)
                self.assertIsInstance(upgrade, Upgrade)
                self.assertEqual(upgrade.max_stacks, max_stacks)
                self.assertEqual({value_condition for _, value_condition in upgrade.stacking_stats.values()}, {condition})


if __name__ == "__main__":
    unittest.main()
