import unittest

from warframe_damage_calculator import Effect, Loadout, Perk, Upgrade, UpgradeStats


class DomainTests(unittest.TestCase):
    def test_loadout_copies_upgrades(self):
        upgrade = Upgrade(name="Damage", stats=UpgradeStats(damage_bonus=Effect(1)))
        loadout = Loadout(upgrades=[upgrade])
        self.assertIsNot(loadout.upgrades[0], upgrade)

    def test_loadout_rejects_duplicate_perks(self):
        perk = Perk("Example")
        with self.assertRaises(ValueError): Loadout(evolutions=[perk, perk])

    def test_loadout_addition_preserves_evolutions(self):
        perk = Perk("Example")
        first = Loadout(evolutions=[perk])
        combined = first + Upgrade(name="Damage")
        self.assertEqual(combined.evolutions, [perk])
        self.assertEqual(combined.upgrades[0].name, "Damage")

    def test_loadout_operators_support_perks(self):
        perk = Perk("Example")
        loadout = Loadout(upgrades=[Upgrade(name="Damage")]) + perk
        self.assertEqual(len(loadout), 2)
        self.assertEqual((loadout - perk).evolutions, [])


if __name__ == "__main__": unittest.main()
