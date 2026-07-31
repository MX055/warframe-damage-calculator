import json
import math
import unittest
from pathlib import Path

from warframe_damage_calculator import Calculator, arsenal


REFERENCE_COMMIT = "c60ff0f"


class FullDatabaseParityTests(unittest.TestCase):
    def test_default_results_match_v140_reference(self):
        expected = json.loads((Path(__file__).parent / "data" / "parity_v140.json").read_text())
        fields = ("flat_dph", "flat_dotph", "total_dph", "flat_dps", "flat_dotps", "total_dps")
        for weapon_name, reference in expected.items():
            with self.subTest(weapon=weapon_name, reference=REFERENCE_COMMIT):
                calculation = Calculator(arsenal.weapon.get(weapon_name)).calculate()
                result = calculation.attacks[calculation.selected_attack]
                self.assertEqual(calculation.selected_attack, reference["attack"])
                for pool_name in ("average", "final"):
                    pool = result.average if pool_name == "average" else calculation.aggregate.average
                    for field in fields:
                        canonical = {"flat_dph": "direct_dph", "flat_dotph": "dot_dph", "flat_dps": "direct_dps", "flat_dotps": "dot_dps"}.get(field, field)
                        actual = getattr(pool, canonical)
                        target = reference[pool_name][field]
                        if math.isnan(float(target)):
                            self.assertTrue(math.isnan(float(actual)))
                        else:
                            self.assertTrue(math.isclose(float(actual), float(target), rel_tol=1e-12, abs_tol=1e-9), (weapon_name, pool_name, field, actual, target))


if __name__ == "__main__": unittest.main()
