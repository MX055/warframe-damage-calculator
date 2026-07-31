import unittest

from warframe_damage_calculator import Effect, Loadout, Mod, Perk, UpgradeStats


class DomainTests(unittest.TestCase):
    def test_loadout_rejects_combined_upgrades_argument(self):
        with self.assertRaises(TypeError): Loadout(upgrades=[])

    def test_loadout_copies_upgrades(self):
        upgrade = Mod(name="Damage", stats=UpgradeStats(damage_bonus=Effect(1)))
        loadout = Loadout(mods=[upgrade])
        self.assertIsNot(loadout.upgrades[0], upgrade)

    def test_loadout_rejects_duplicate_perks(self):
        perk = Perk("Example")
        with self.assertRaises(ValueError): Loadout(evolutions=[perk, perk])

    def test_loadout_addition_preserves_evolutions(self):
        perk = Perk("Example")
        first = Loadout(evolutions=[perk])
        combined = first + Mod(name="Damage")
        self.assertEqual(combined.evolutions, [perk])
        self.assertEqual([upgrade.name for upgrade in combined.upgrades], ["Damage", "Example"])
        self.assertEqual([upgrade.name for upgrade in combined.ranked_upgrades], ["Damage"])

    def test_loadout_operators_support_perks(self):
        perk = Perk("Example")
        loadout = Loadout(mods=[Mod(name="Damage")]) + perk
        self.assertEqual(len(loadout), 2)
        self.assertEqual((loadout - perk).evolutions, [])


if __name__ == "__main__": unittest.main()
