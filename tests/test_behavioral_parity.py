import math
import unittest

from warframe_damage_calculator import Calculator, arsenal


EXPECTED = {
    "Braton": 175.43507176954193,
    "Corinth Prime": 987.4759701058817,
    "Phenmor": 542.0190740370043,
    "Bo Prime": 266.223919104,
}


def get_weapon(name: str):
    for repository in (arsenal.primary, arsenal.secondary, arsenal.melee, arsenal.archgun):
        if name in repository.names: return repository.get(name)
    raise KeyError(name)


class BehavioralParityTests(unittest.TestCase):
    def test_reference_outputs_remain_stable(self):
        for name, expected in EXPECTED.items():
            with self.subTest(name=name):
                actual = Calculator(get_weapon(name)).calculate().aggregate.average.total_dps
                self.assertTrue(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-9), (name, actual, expected))


if __name__ == "__main__": unittest.main()
