from __future__ import annotations

from ..calculators import WeaponCalculator
from ..models import Weapon


class WeaponFormatter:
    def __init__(self, weapon: Weapon, calculator: WeaponCalculator) -> None:
        self.weapon = weapon
        self.calc = calculator

    def summary(self) -> str:
        raise NotImplementedError
