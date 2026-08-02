import unittest
import pickle

from warframe_damage_calculator import Loadout, PLACEHOLDER, arsenal
from warframe_damage_calculator.domain.effects import Effect
from warframe_damage_calculator.domain.perks import Perk
from warframe_damage_calculator.domain.upgrades import Compatibility, Mod, UpgradeStats


class DomainTests(unittest.TestCase):
    def test_compatibility_rejects_non_boolean_aoe_values(self):
        with self.assertRaisesRegex(TypeError, "aoe must be a bool"): Compatibility.from_record({"aoe": "false"})

    def test_multiplicative_effects_scale_from_the_identity(self):
        upgrade = Mod(name="Multiplier", max_rank=5, stats=UpgradeStats(explosion_radius=Effect(0.2, mode="multiplicative")))
        self.assertAlmostEqual(upgrade.set(rank=0).resolve_manual()[0].value, 1 - 0.8 / 6)
        self.assertAlmostEqual(upgrade.set(rank=5).resolve_manual()[0].value, 0.2)
        with self.assertRaisesRegex(TypeError, "must be numeric"): Effect("invalid", mode="multiplicative")
        with self.assertRaisesRegex(ValueError, "damage_bonus does not support"): UpgradeStats(damage_bonus=Effect(2, mode="multiplicative"))

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

    def test_weapon_definitions_are_picklable_for_parallel_optimization(self):
        weapon = pickle.loads(pickle.dumps(arsenal.primary.get("Vectis Prime")))
        self.assertEqual((weapon.name, list(weapon.attacks), list(weapon.perk_choices)), ("Vectis Prime", ["normal_attack", "incarnon_form", "incarnon_form_aoe", "incarnon_form_embed"], [1, 2, 3, 4]))
        perk = next(iter(weapon.perks))
        self.assertTrue(any(effect.value is PLACEHOLDER for effects in perk.stats.values() for effect in effects))


if __name__ == "__main__": unittest.main()
